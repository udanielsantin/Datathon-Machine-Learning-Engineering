from pathlib import Path
from io import StringIO
import sys

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_csv_with_2022_input():
    csv_path = Path("test_inputs/pede2022_api_input.csv")
    assert csv_path.exists(), f"CSV de teste nao encontrado: {csv_path}"

    client = TestClient(app)

    with csv_path.open("rb") as f:
        response = client.post(
            "/predict-csv",
            files={"file": (csv_path.name, f, "text/csv")},
        )

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/csv")

    result_df = pd.read_csv(StringIO(response.text))

    expected_cols = {
        "Fase_adj",
        "gap_idade",
        "z_notas_fase",
        "z_ieg_fase",
        "score_previsto_proximo_ano",
    }

    missing = expected_cols - set(result_df.columns)
    assert not missing, f"Colunas esperadas ausentes no retorno: {missing}"
    assert len(result_df) > 0
    assert result_df["score_previsto_proximo_ano"].notna().all()
