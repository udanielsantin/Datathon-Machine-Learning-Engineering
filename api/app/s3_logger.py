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

    def read_recent_json(self, limit: int = 50) -> tuple[bool, list[dict[str, Any]], str]:
        if not self.enabled or self.client is None:
            return False, [], "S3 desabilitado: bucket nao configurado"

        if limit <= 0:
            return False, [], "limit deve ser maior que 0"

        try:
            response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=f"{self.prefix}/" if self.prefix else "")
            contents = response.get("Contents", [])

            json_objects = [obj for obj in contents if str(obj.get("Key", "")).endswith(".json")]
            json_objects.sort(key=lambda x: x.get("LastModified"), reverse=True)

            rows: list[dict[str, Any]] = []
            for obj in json_objects[:limit]:
                key = obj.get("Key")
                if not key:
                    continue

                body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
                try:
                    rows.append(json.loads(body.decode("utf-8")))
                except json.JSONDecodeError:
                    continue

            return True, rows, "ok"
        except (BotoCoreError, ClientError) as exc:
            return False, [], str(exc)
