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

    def size(self, key: str) -> int:
        return self._client.head_object(Bucket=self.bucket, Key=key)["ContentLength"]

    def read_json(self, key: str, max_bytes: int = 64 * 1024 * 1024):
        """A small JSON object (analyse.json), refused if it is unexpectedly large."""
        if self.size(key) > max_bytes:
            raise ValueError(f"{key} is larger than {max_bytes} bytes")
        return json.loads(self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read())

    def upload_file(self, key: str, source: Path, content_type: str = "application/octet-stream") -> None:
        """Streams a file from disk (boto3 multipart transfer)."""
        self._client.upload_file(str(source), self.bucket, key, ExtraArgs={"ContentType": content_type})

    def upload_json(self, key: str, payload: bytes) -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=payload, ContentType="application/json")
