from __future__ import annotations

from typing import Any
import re
import unicodedata

import numpy as np
import pandas as pd

IDADE_IDEAL_POR_FASE = {
    "ALFA": 8,
    "FASE 1": 10,
    "FASE 2": 12,
    "FASE 3": 14,
    "FASE 4": 15,
    "FASE 5": 16,
    "FASE 6": 17,
    "FASE 7": 18,
    "FASE 8": 18,
    "FASE 9": 18,
}

FASE_DIGIT_MAP = {
    "0": "ALFA",
    "1": "FASE 1",
    "2": "FASE 2",
    "3": "FASE 3",
    "4": "FASE 4",
    "5": "FASE 5",
    "6": "FASE 6",
    "7": "FASE 7",
    "8": "FASE 8",
    "9": "FASE 9",
}

REQUIRED_INPUT_FIELDS = ["serie", "idade", "ipv", "portugues", "ingles", "matematica", "ieg"]

ALIAS_MAP = {
    "serie": ["serie", "fase", "fase_adj"],
    "idade": ["idade"],
    "ipv": ["ipv", "feat_ipv"],
    "portugues": ["portugues", "por", "nota_portugues", "nota_port"],
    "ingles": ["ingles", "ing", "nota_ingles"],
    "matematica": ["matematica", "mat", "nota_matematica", "nota_mat"],
    "ieg": ["ieg"],
}


def _normalize_colname(col: Any) -> str:
    text = str(col).strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _map_serie_to_fase(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip().upper()
    digit_match = re.search(r"(\d)", text)
    if digit_match:
        digit = digit_match.group(1)
        return FASE_DIGIT_MAP.get(digit, text)
    if text in IDADE_IDEAL_POR_FASE:
        return text
    return text


def _to_numeric(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype("string")
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _zscore_group(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - series.mean()) / std


def standardize_input(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    normalized_cols = {_normalize_colname(c): c for c in df.columns}

    missing_fields: list[str] = []
    extracted: dict[str, pd.Series] = {}

    for canonical, aliases in ALIAS_MAP.items():
        original_col = None
        for alias in aliases:
            if alias in normalized_cols:
                original_col = normalized_cols[alias]
                break
        if original_col is None:
            missing_fields.append(canonical)
            continue
        extracted[canonical] = df[original_col]

    if missing_fields:
        raise ValueError(
            "CSV sem colunas obrigatorias. Faltando: "
            + ", ".join(missing_fields)
            + ". Esperado: "
            + ", ".join(REQUIRED_INPUT_FIELDS)
        )

    out = pd.DataFrame(extracted)

    out["Fase_adj"] = out["serie"].apply(_map_serie_to_fase)
    out["idade"] = _to_numeric(out["idade"])
    out["feat_IPV"] = _to_numeric(out["ipv"])
    out["portugues"] = _to_numeric(out["portugues"])
    out["ingles"] = _to_numeric(out["ingles"])
    out["matematica"] = _to_numeric(out["matematica"])
    out["IEG"] = _to_numeric(out["ieg"])

    out["idade_ideal"] = out["Fase_adj"].map(IDADE_IDEAL_POR_FASE)
    gap_base = (out["idade"] - out["idade_ideal"]).clip(lower=0)
    out["gap_idade"] = np.where(out["Fase_adj"].isin(["FASE 8", "FASE 9"]), 0, gap_base)

    out["media_notas"] = out[["portugues", "ingles", "matematica"]].mean(axis=1)
    out["z_notas_fase"] = out.groupby("Fase_adj")["media_notas"].transform(_zscore_group)
    out["z_ieg_fase"] = out.groupby("Fase_adj")["IEG"].transform(_zscore_group)

    return out


def build_model_features(preprocessed_df: pd.DataFrame, required_columns: list[str]) -> pd.DataFrame:
    features = pd.DataFrame(index=preprocessed_df.index)
    for col in required_columns:
        if col not in preprocessed_df.columns:
            raise ValueError(f"Feature obrigatoria ausente apos preprocessamento: {col}")
        features[col] = preprocessed_df[col]
    return features
