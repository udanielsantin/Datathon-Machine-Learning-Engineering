from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Monitor de Inferencia - Defasagem", layout="wide")
st.title("Monitor de Inferencia - Modelo de Defasagem")
st.caption("Acompanhamento de saude da API, historico de inferencia e medias por fase.")


def _to_history_df(history: list[dict]) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            {
                "request_id": row.get("request_id"),
                "created_at_utc": row.get("created_at_utc"),
                "input_filename": row.get("input_filename"),
                "rows_received": row.get("rows_received"),
                "rows_scored": row.get("rows_scored"),
                "api_return_mean": row.get("api_return_mean"),
                "api_current_score_mean": row.get("api_current_score_mean"),
                "s3_status": row.get("s3_status", "n/a"),
            }
            for row in history
        ]
    )
    df["created_at_utc"] = pd.to_datetime(df["created_at_utc"], errors="coerce", utc=True)
    return df.sort_values("created_at_utc")


def _to_phase_df(history: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for row in history:
        for phase in row.get("phase_summary", []):
            rows.append(
                {
                    "request_id": row.get("request_id"),
                    "created_at_utc": row.get("created_at_utc"),
                    "Fase_adj": phase.get("Fase_adj"),
                    "total_alunos": phase.get("total_alunos"),
                    "media_prevista": phase.get("media_prevista"),
                    "media_gap_idade": phase.get("media_gap_idade"),
                    "media_z_notas": phase.get("media_z_notas"),
                    "media_z_ieg": phase.get("media_z_ieg"),
                }
            )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["created_at_utc"] = pd.to_datetime(df["created_at_utc"], errors="coerce", utc=True)
    return df.sort_values(["created_at_utc", "Fase_adj"])


def _check_api_health(base_url: str) -> tuple[bool, str | None]:
    health_url = f"{base_url.rstrip('/')}/health"
    try:
        response = requests.get(health_url, timeout=10)
        data = response.json() if response.content else {}
        is_ok = response.ok and data.get("status") == "ok"
        if is_ok:
            return True, None
        return False, f"status inesperado: {data}"
    except Exception as exc:
        return False, str(exc)


def _fetch_summary(base_url: str, limit: int) -> dict:
    summary_url = f"{base_url.rstrip('/')}/monitor/summary-s3"
    response = requests.get(summary_url, params={"limit": limit}, timeout=20)
    response.raise_for_status()
    return response.json()


def main() -> None:
    default_api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    api_base_url = st.sidebar.text_input("API base URL", value=default_api_base_url)
    limit = st.sidebar.slider("Ultimas requisicoes", min_value=5, max_value=200, value=50, step=5)
    alert_threshold = st.sidebar.slider(
        "Alerta: media prevista acima de", min_value=0.0, max_value=10.0, value=6.0, step=0.1
    )
    auto_refresh = st.sidebar.checkbox("Auto atualizar", value=False)
    refresh_seconds = st.sidebar.slider("Intervalo (segundos)", min_value=10, max_value=120, value=30, step=5)

    if auto_refresh:
        st.markdown(f"<meta http-equiv='refresh' content='{refresh_seconds}'>", unsafe_allow_html=True)

    if st.sidebar.button("Atualizar"):
        st.rerun()

    api_ok, api_error = _check_api_health(api_base_url)

    try:
        payload = _fetch_summary(api_base_url, limit)
    except Exception as exc:
        st.error(f"Falha ao consultar monitor da API: {exc}")
        st.stop()

    history = payload.get("history", [])
    history_df = _to_history_df(history)
    phase_global = payload.get("phase_global_mean", [])

    if api_ok:
        st.success("API saudavel: /health retornou status ok")
    else:
        st.warning(f"API sem confirmacao de saude. Erro: {api_error or 'desconhecido'}")

    last_mean = float(history_df["api_return_mean"].iloc[-1]) if not history_df.empty else 0.0
    prev_mean = float(history_df["api_return_mean"].iloc[-2]) if len(history_df) > 1 else last_mean
    delta_mean = round(last_mean - prev_mean, 4)
    total_scored = int(history_df["rows_scored"].fillna(0).sum()) if not history_df.empty else 0
    last_s3_status = str(history_df["s3_status"].iloc[-1]) if not history_df.empty else "n/a"

    st.subheader("Resumo Geral")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total de requisicoes gravadas", payload.get("total_requests", 0))
    with c2:
        st.metric("Requisicoes exibidas", len(history))
    with c3:
        st.metric("Media prevista (ultima req)", f"{last_mean:.4f}", delta=f"{delta_mean:+.4f}")
    with c4:
        st.metric("Total de linhas processadas", total_scored)

    st.caption(f"Ultimo status de envio S3: {last_s3_status}")

    if not history_df.empty and last_mean >= alert_threshold:
        st.error(
            f"Alerta: media prevista da ultima requisicao ({last_mean:.4f}) acima do limiar {alert_threshold:.1f}."
        )

    st.subheader("Medias Globais por Fase")
    if phase_global:
        phase_df = pd.DataFrame(phase_global)
        st.dataframe(phase_df, use_container_width=True)

        if {"Fase_adj", "media_prevista"}.issubset(phase_df.columns):
            st.subheader("Media Prevista por Fase")
            st.bar_chart(phase_df[["Fase_adj", "media_prevista"]].set_index("Fase_adj"))
    else:
        st.info("Sem dados de fase ainda.")

    st.subheader("Historico de Retorno da API")
    if history_df.empty:
        st.info("Ainda nao ha historico de inferencia.")
        return

    timeline_df = history_df[["created_at_utc", "api_return_mean", "api_current_score_mean"]].set_index("created_at_utc")
    st.line_chart(timeline_df)

    rows_timeline_df = history_df[["created_at_utc", "rows_scored"]].set_index("created_at_utc")
    st.area_chart(rows_timeline_df)

    table_df = history_df.copy()
    table_df["created_at_utc"] = table_df["created_at_utc"].dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(table_df, use_container_width=True)

    st.subheader("Detalhe por Fase (requisicoes recentes)")
    phase_detail_df = _to_phase_df(history)
    if phase_detail_df.empty:
        st.info("Sem detalhe por fase no recorte atual.")
        return

    st.dataframe(phase_detail_df, use_container_width=True)

    trend_phase_df = (
        phase_detail_df[["created_at_utc", "Fase_adj", "media_prevista"]]
        .dropna(subset=["created_at_utc"])
        .pivot_table(index="created_at_utc", columns="Fase_adj", values="media_prevista", aggfunc="mean")
        .sort_index()
    )
    if not trend_phase_df.empty:
        st.subheader("Tendencia de Media Prevista por Fase")
        st.line_chart(trend_phase_df)


if __name__ == "__main__":
    main()
