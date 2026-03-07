from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Monitor de Inferencia - Defasagem", layout="wide")
st.title("Monitor de Inferencia - Modelo de Defasagem")
st.caption("Acompanhamento das medias por fase e historico de retorno da API.")

default_api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
api_base_url = st.sidebar.text_input("API base URL", value=default_api_base_url)
data_source = st.sidebar.selectbox("Fonte de historico", ["local", "s3"], index=0)
limit = st.sidebar.slider("Ultimas requisicoes", min_value=5, max_value=200, value=50, step=5)

if st.sidebar.button("Atualizar"):
    st.rerun()

monitor_path = "/monitor/summary-s3" if data_source == "s3" else "/monitor/summary"
summary_url = f"{api_base_url.rstrip('/')}{monitor_path}"

try:
    response = requests.get(summary_url, params={"limit": limit}, timeout=15)
    response.raise_for_status()
    payload = response.json()
except Exception as exc:
    st.error(f"Falha ao consultar API em {summary_url}: {exc}")
    st.stop()

st.subheader("Resumo Geral")
col1, col2 = st.columns(2)
with col1:
    st.metric("Total de requisicoes gravadas", payload.get("total_requests", 0))
with col2:
    history = payload.get("history", [])
    st.metric("Requisicoes exibidas", len(history))

st.subheader("Medias Globais por Fase")
phase_global = payload.get("phase_global_mean", [])
if phase_global:
    df_phase = pd.DataFrame(phase_global)
    st.dataframe(df_phase, use_container_width=True)
else:
    st.info("Sem dados de fase ainda.")

st.subheader("Historico de Retorno da API")
if history:
    history_df = pd.DataFrame(
        [
            {
                "request_id": row.get("request_id"),
                "created_at_utc": row.get("created_at_utc"),
                "input_filename": row.get("input_filename"),
                "rows_received": row.get("rows_received"),
                "rows_scored": row.get("rows_scored"),
                "api_return_mean": row.get("api_return_mean"),
                "s3_status": row.get("s3_status", "n/a"),
            }
            for row in history
        ]
    )
    st.dataframe(history_df, use_container_width=True)

    st.subheader("Detalhe por Fase (requisicoes recentes)")
    phase_rows = []
    for row in history:
        for p in row.get("phase_summary", []):
            phase_rows.append(
                {
                    "request_id": row.get("request_id"),
                    "created_at_utc": row.get("created_at_utc"),
                    "Fase_adj": p.get("Fase_adj"),
                    "total_alunos": p.get("total_alunos"),
                    "media_prevista": p.get("media_prevista"),
                    "media_gap_idade": p.get("media_gap_idade"),
                    "media_z_notas": p.get("media_z_notas"),
                    "media_z_ieg": p.get("media_z_ieg"),
                }
            )

    if phase_rows:
        st.dataframe(pd.DataFrame(phase_rows), use_container_width=True)
else:
    st.info("Ainda nao ha historico de inferencia.")
