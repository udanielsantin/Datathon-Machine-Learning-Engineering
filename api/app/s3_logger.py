from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class S3Logger:
    def __init__(self, bucket: str, prefix: str, region: str | None = None) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.enabled = bool(bucket)
        self.client = boto3.client("s3", region_name=region) if self.enabled else None

    def upload_json(self, key_suffix: str, payload: dict[str, Any]) -> tuple[bool, str]:
        if not self.enabled or self.client is None:
            return False, "S3 desabilitado: bucket nao configurado"

        key = f"{self.prefix}/{key_suffix}" if self.prefix else key_suffix
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType="application/json",
            )
            return True, key
        except (BotoCoreError, ClientError) as exc:
            return False, str(exc)
