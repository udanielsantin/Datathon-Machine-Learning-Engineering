import json
from pathlib import Path
from typing import Any

import joblib


class ModelRuntime:
    def __init__(self, model_path: Path, schema_path: Path) -> None:
        if not model_path.exists():
            raise FileNotFoundError(f"Modelo nao encontrado: {model_path}")
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema nao encontrado: {schema_path}")

        self.pipeline = joblib.load(model_path)
        with schema_path.open("r", encoding="utf-8") as f:
            self.schema: dict[str, Any] = json.load(f)

    @property
    def required_columns(self) -> list[str]:
        cols = self.schema.get("required_columns", [])
        if not isinstance(cols, list) or not cols:
            raise ValueError("Schema invalido: required_columns ausente ou vazio")
        return cols
