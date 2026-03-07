from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO, StringIO
import uuid

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from .config import (
    AWS_REGION,
    LOCAL_HISTORY_PATH,
    MODEL_PATH,
    S3_BUCKET,
    S3_PREFIX,
    SCHEMA_PATH,
)
from .logging_store import append_local_history, read_local_history
from .model_runtime import ModelRuntime
from .preprocessing import build_model_features, standardize_input
from .s3_logger import S3Logger


app = FastAPI(
    title="API de Previsao de Defasagem",
    description="Recebe CSV, calcula features do modelo e retorna CSV com predicoes.",
    version="1.0.0",
)

runtime = ModelRuntime(MODEL_PATH, SCHEMA_PATH)
s3_logger = S3Logger(bucket=S3_BUCKET, prefix=S3_PREFIX, region=AWS_REGION)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/schema")
def get_schema() -> dict:
    return runtime.schema


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
        "phase_summary": phase_summary_df.to_dict(orient="records"),
        "required_model_columns": runtime.required_columns,
    }

    append_local_history(LOCAL_HISTORY_PATH, summary_record)
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
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit deve ser maior que 0")

    rows = read_local_history(LOCAL_HISTORY_PATH)
    if not rows:
        return {"total_requests": 0, "history": [], "phase_global_mean": []}

    history = rows[-limit:]

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

    return JSONResponse(
        {
            "total_requests": len(rows),
            "history": history,
            "phase_global_mean": phase_global_mean,
        }
    )
