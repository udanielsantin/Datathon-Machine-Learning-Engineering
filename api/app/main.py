from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO, StringIO
import uuid

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from .config import (
    AWS_REGION,
    MODEL_PATH,
    S3_BUCKET,
    S3_PREFIX,
    SCHEMA_PATH,
)
from .model_runtime import ModelRuntime
from .preprocessing import ALIAS_MAP, REQUIRED_INPUT_FIELDS, build_model_features, standardize_input
from .s3_logger import S3Logger


app = FastAPI(
    title="API de Previsao de Defasagem",
    description="Recebe CSV, calcula features do modelo e retorna CSV com predicoes.",
    version="1.0.0",
)

runtime = ModelRuntime(MODEL_PATH, SCHEMA_PATH)
s3_logger = S3Logger(bucket=S3_BUCKET, prefix=S3_PREFIX, region=AWS_REGION)


def _compute_current_defasagem_score(prepared_df: pd.DataFrame) -> pd.Series:
    score_idade = prepared_df["gap_idade"]
    score_notas = (-prepared_df["z_notas_fase"]).clip(lower=0) * 2.0
    score_engajamento = (-prepared_df["z_ieg_fase"]).clip(lower=0) * 1.0
    return (score_idade + score_notas + score_engajamento).clip(0, 10)


def _build_monitor_summary(rows: list[dict], limit: int) -> dict:
    if not rows:
        return {"total_requests": 0, "history": [], "phase_global_mean": []}

    sorted_rows = sorted(rows, key=lambda row: str(row.get("created_at_utc", "")))
    history = sorted_rows[-limit:]

    phase_rows = []
    for entry in history:
        for phase_entry in entry.get("phase_summary", []):
            phase_rows.append(
                {
                    "request_id": entry.get("request_id"),
                    "created_at_utc": entry.get("created_at_utc"),
                    "Fase_adj": phase_entry.get("Fase_adj"),
                    "media_prevista": phase_entry.get("media_prevista"),
                    "media_gap_idade": phase_entry.get("media_gap_idade"),
                    "media_z_notas": phase_entry.get("media_z_notas"),
                    "media_z_ieg": phase_entry.get("media_z_ieg"),
                    "total_alunos": phase_entry.get("total_alunos"),
                }
            )

    if phase_rows:
        phase_df = pd.DataFrame(phase_rows)
        phase_global = (
            phase_df.groupby("Fase_adj", dropna=False)
            .agg(
                requests=("request_id", "nunique"),
                total_alunos=("total_alunos", "sum"),
                media_prevista=("media_prevista", "mean"),
                media_gap_idade=("media_gap_idade", "mean"),
                media_z_notas=("media_z_notas", "mean"),
                media_z_ieg=("media_z_ieg", "mean"),
            )
            .reset_index()
            .sort_values("Fase_adj")
        )
        for col in ["media_prevista", "media_gap_idade", "media_z_notas", "media_z_ieg"]:
            phase_global[col] = phase_global[col].astype(float).round(4)
        phase_global_mean = phase_global.to_dict(orient="records")
    else:
        phase_global_mean = []

    return {
        "total_requests": len(rows),
        "history": history,
        "phase_global_mean": phase_global_mean,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/schema")
def get_schema() -> dict:
    return {
        "csv_input_required_columns": REQUIRED_INPUT_FIELDS,
        "csv_input_example_header": ",".join(REQUIRED_INPUT_FIELDS),
        "csv_input_aliases": ALIAS_MAP,
        "model_schema": runtime.schema,
    }


@app.post("/predict-csv")
async def predict_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Envie um arquivo CSV valido")

    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(status_code=400, detail="Arquivo CSV vazio")

    try:
        raw_df = pd.read_csv(BytesIO(raw_content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao ler CSV: {exc}") from exc

    request_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        prepared_df = standardize_input(raw_df)
        features_df = build_model_features(prepared_df, runtime.required_columns)
        predictions = runtime.pipeline.predict(features_df)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro na inferencia: {exc}") from exc

    output_df = raw_df.copy()
    output_df["Fase_adj"] = prepared_df["Fase_adj"].values
    output_df["gap_idade"] = prepared_df["gap_idade"].values
    output_df["z_notas_fase"] = prepared_df["z_notas_fase"].values
    output_df["z_ieg_fase"] = prepared_df["z_ieg_fase"].values
    output_df["score_de_defasagem_atual"] = _compute_current_defasagem_score(prepared_df).values
    output_df["score_previsto_proximo_ano"] = predictions

    phase_summary_df = (
        output_df.groupby("Fase_adj", dropna=False)
        .agg(
            total_alunos=("score_previsto_proximo_ano", "size"),
            media_prevista=("score_previsto_proximo_ano", "mean"),
            media_gap_idade=("gap_idade", "mean"),
            media_z_notas=("z_notas_fase", "mean"),
            media_z_ieg=("z_ieg_fase", "mean"),
        )
        .reset_index()
    )

    for col in ["media_prevista", "media_gap_idade", "media_z_notas", "media_z_ieg"]:
        phase_summary_df[col] = phase_summary_df[col].astype(float).round(4)

    summary_record = {
        "request_id": request_id,
        "created_at_utc": created_at,
        "input_filename": file.filename,
        "rows_received": int(len(raw_df)),
        "rows_scored": int(len(output_df)),
        "api_return_mean": float(np.nanmean(output_df["score_previsto_proximo_ano"])),
        "api_current_score_mean": float(np.nanmean(output_df["score_de_defasagem_atual"])),
        "phase_summary": phase_summary_df.to_dict(orient="records"),
        "required_model_columns": runtime.required_columns,
    }

    s3_ok, s3_info = s3_logger.upload_json(f"{request_id}.json", summary_record)
    summary_record["s3_status"] = "ok" if s3_ok else "not_uploaded"
    summary_record["s3_info"] = s3_info

    csv_buffer = StringIO()
    output_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    headers = {
        "X-Request-Id": request_id,
        "X-S3-Status": summary_record["s3_status"],
    }

    return StreamingResponse(
        iter([csv_buffer.getvalue()]),
        media_type="text/csv",
        headers=headers,
    )


@app.get("/monitor/summary")
def monitor_summary(limit: int = 50):
    """Endpoint de monitor local desabilitado. Use /monitor/summary-s3"""
    raise HTTPException(
        status_code=410,
        detail="Monitor local desabilitado. Use /monitor/summary-s3 para consultar logs do S3"
    )


@app.get("/monitor/summary-s3")
def monitor_summary_s3(limit: int = 50):
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit deve ser maior que 0")

    ok, rows, info = s3_logger.read_recent_json(limit=limit)
    if not ok:
        raise HTTPException(status_code=400, detail=info)

    payload = _build_monitor_summary(rows, limit)
    payload["source"] = "s3"
    payload["s3_bucket"] = S3_BUCKET
    payload["s3_prefix"] = S3_PREFIX
    return JSONResponse(payload)


@app.get("/monitor/dashboard", response_class=HTMLResponse)
def monitor_dashboard() -> str:
        return """
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Painel de Monitoramento - Defasagem</title>
    <style>
        :root {
            --bg: #f4f8fb;
            --card: #ffffff;
            --ink: #12334a;
            --muted: #5f7383;
            --line: #d6e2ea;
            --accent: #0f766e;
            --warn: #b45309;
        }
        body {
            margin: 0;
            font-family: "Trebuchet MS", "Segoe UI", sans-serif;
            background: linear-gradient(160deg, #eff6ff 0%, #f4f8fb 40%, #eaf7f4 100%);
            color: var(--ink);
        }
        .wrap {
            max-width: 1100px;
            margin: 24px auto;
            padding: 0 16px;
        }
        h1 { margin: 0 0 8px; }
        .sub { color: var(--muted); margin-bottom: 16px; }
        .controls {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 12px;
        }
        .kpis {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 10px;
            margin-top: 14px;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 12px;
        }
        .label { color: var(--muted); font-size: 12px; }
        .value { font-size: 24px; font-weight: 700; }
        .grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 12px;
            margin-top: 12px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        th, td {
            border-bottom: 1px solid var(--line);
            padding: 8px;
            text-align: left;
        }
        th { background: #f8fbfd; }
        .status-ok { color: var(--accent); font-weight: 700; }
        .status-warn { color: var(--warn); font-weight: 700; }
        .error {
            display: none;
            margin-top: 12px;
            padding: 10px;
            border-radius: 10px;
            border: 1px solid #fecaca;
            background: #fef2f2;
            color: #991b1b;
        }
    </style>
</head>
<body>
    <div class="wrap">
        <h1>Painel de Monitoramento</h1>
        <div class="sub">Acompanhamento simples de inferencias e medias por fase (dados do S3).</div>

        <div class="controls">
            <label>Ultimas requisicoes: <input id="limit" type="number" value="50" min="5" max="200" step="5" /></label>
            <label>Alerta media >= <input id="threshold" type="number" value="6" min="0" max="10" step="0.1" /></label>
            <button id="refreshBtn">Atualizar</button>
            <label><input id="auto" type="checkbox" checked /> Auto atualizar (30s)</label>
            <span id="apiStatus" class="label">checando saude da API...</span>
        </div>

        <div id="kpis" class="kpis"></div>
        <div id="alertBox" class="error"></div>

        <div class="grid">
            <div class="card">
                <h3>Medias Globais por Fase</h3>
                <div id="phaseTable"></div>
            </div>
            <div class="card">
                <h3>Historico de Requisicoes</h3>
                <div id="historyTable"></div>
            </div>
        </div>
    </div>

    <script>
        const byId = (id) => document.getElementById(id);
        let timer = null;

        function tableFromRows(rows) {
            if (!rows || rows.length === 0) return '<div class="label">Sem dados.</div>';
            const cols = Object.keys(rows[0]);
            const thead = '<tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr>';
            const tbody = rows.map(r => '<tr>' + cols.map(c => `<td>${r[c] ?? ''}</td>`).join('') + '</tr>').join('');
            return `<table><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
        }

        async function checkHealth() {
            const statusEl = byId('apiStatus');
            try {
                const r = await fetch('/health');
                const j = await r.json();
                if (r.ok && j.status === 'ok') {
                    statusEl.innerHTML = '<span class="status-ok">API saudavel</span>';
                } else {
                    statusEl.innerHTML = '<span class="status-warn">API sem confirmacao de saude</span>';
                }
            } catch (_) {
                statusEl.innerHTML = '<span class="status-warn">Falha ao consultar /health</span>';
            }
        }

        async function loadData() {
            const limit = Number(byId('limit').value || 50);
            const threshold = Number(byId('threshold').value || 6);
            const alertBox = byId('alertBox');

            await checkHealth();
            const r = await fetch(`/monitor/summary-s3?limit=${limit}`);
            if (!r.ok) {
                const msg = await r.text();
                throw new Error(msg);
            }
            const payload = await r.json();

            const history = payload.history || [];
            const last = history.length ? history[history.length - 1] : null;
            const lastMean = last && last.api_return_mean != null ? Number(last.api_return_mean) : 0;

            const kpis = [
                { label: 'Total de requisicoes', value: payload.total_requests ?? 0 },
                { label: 'Requisicoes exibidas', value: history.length },
                { label: 'Media ultima requisicao', value: lastMean.toFixed(4) },
                { label: 'Ultimo status S3', value: last?.s3_status ?? 'n/a' },
            ];
            byId('kpis').innerHTML = kpis.map(k => `
                <div class="card">
                    <div class="label">${k.label}</div>
                    <div class="value">${k.value}</div>
                </div>
            `).join('');

            if (history.length && lastMean >= threshold) {
                alertBox.style.display = 'block';
                alertBox.textContent = `Alerta: media prevista da ultima requisicao (${lastMean.toFixed(4)}) >= limiar (${threshold.toFixed(1)}).`;
            } else {
                alertBox.style.display = 'none';
                alertBox.textContent = '';
            }

            byId('phaseTable').innerHTML = tableFromRows(payload.phase_global_mean || []);

            const historyRows = history.slice().reverse().map(x => ({
                created_at_utc: x.created_at_utc,
                input_filename: x.input_filename,
                rows_scored: x.rows_scored,
                api_return_mean: x.api_return_mean,
                s3_status: x.s3_status,
            }));
            byId('historyTable').innerHTML = tableFromRows(historyRows);
        }

        async function refresh() {
            try {
                await loadData();
            } catch (err) {
                const alertBox = byId('alertBox');
                alertBox.style.display = 'block';
                alertBox.textContent = `Erro ao carregar monitor: ${err}`;
            }
        }

        byId('refreshBtn').addEventListener('click', refresh);
        byId('auto').addEventListener('change', (e) => {
            if (timer) clearInterval(timer);
            if (e.target.checked) timer = setInterval(refresh, 30000);
        });

        refresh();
        timer = setInterval(refresh, 30000);
    </script>
</body>
</html>
        """
