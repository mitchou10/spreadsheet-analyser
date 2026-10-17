import json
import os

import boto3
from botocore.config import Config


class S3Reader:
    """Read-only S3/RustFS access (same AWS_* settings as the backend): the agent only reads analyse.json files."""

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

    def get_json(self, key: str, max_bytes: int | None = None):
        """Reads a (small) JSON object; refuses objects over `max_bytes` instead of loading them."""
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        if max_bytes is not None and response.get("ContentLength", 0) > max_bytes:
            response["Body"].close()
            raise ValueError(f"{key} is {response['ContentLength']} bytes, over the {max_bytes} bytes limit")
        return json.loads(response["Body"].read())
