from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = BASE_DIR / "artifacts"

MODEL_PATH = ARTIFACTS_DIR / "modelo_defasagem_pipeline.joblib"
SCHEMA_PATH = ARTIFACTS_DIR / "modelo_defasagem_schema.json"

AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
S3_PREFIX = os.getenv("S3_PREFIX", "datathon-defasagem/logs").strip("/")
