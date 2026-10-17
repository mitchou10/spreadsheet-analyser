import json
import os
from pathlib import Path

import boto3
from botocore.config import Config


class AnalysisStorage:
    """S3/RustFS access with the same AWS_* settings as the backend. Files go through disk, never memory."""

    def __init__(self, client=None, bucket: str | None = None) -> None:
        self.bucket = bucket or os.environ.get("AWS_S3_BUCKET", "spreadsheet-analyser")
        self._client = client or boto3.client(
            "s3",
            endpoint_url=os.environ.get("AWS_ENDPOINT_URL_S3") or None,
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
        )

    def download(self, key: str, destination: Path) -> None:
        """Streams the object to `destination` in chunks (boto3 multipart transfer)."""
        self._client.download_file(self.bucket, key, str(destination))

    def upload_json(self, key: str, payload: bytes) -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=payload, ContentType="application/json")

    def get_bytes(self, key: str) -> bytes | None:
        """Reads an object, or None if it does not exist."""
        try:
            return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self._client.exceptions.NoSuchKey:
            return None

    def get_json(self, key: str):
        data = self.get_bytes(key)
        if data is None:
            raise FileNotFoundError(key)
        return json.loads(data)

    def put_bytes(self, key: str, payload: bytes, content_type: str = "application/octet-stream") -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=payload, ContentType=content_type)

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)
