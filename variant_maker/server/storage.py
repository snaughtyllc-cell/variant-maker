"""Object storage seam for moving files in/out of stateless GPU workers (S3 API)."""
from __future__ import annotations

import os
from typing import Protocol


class ObjectStore(Protocol):
    def put(self, key: str, local_path: str) -> None: ...
    def get(self, key: str, local_path: str) -> None: ...
    def list_prefix(self, prefix: str) -> list[str]: ...


def _make_client(*, endpoint_url: str, access_key: str, secret_key: str, region: str):
    import boto3  # lazy: only needed when a real S3 store is constructed
    return boto3.client(
        "s3", endpoint_url=endpoint_url, aws_access_key_id=access_key,
        aws_secret_access_key=secret_key, region_name=region,
    )


class S3ObjectStore:
    """S3-compatible store (Cloudflare R2 by default; also AWS S3 / RunPod S3)."""

    def __init__(self, *, endpoint_url: str, bucket: str, access_key: str,
                 secret_key: str, region: str = "auto") -> None:
        self._bucket = bucket
        self._client = _make_client(endpoint_url=endpoint_url, access_key=access_key,
                                    secret_key=secret_key, region=region)

    def put(self, key: str, local_path: str) -> None:
        self._client.upload_file(local_path, self._bucket, key)

    def get(self, key: str, local_path: str) -> None:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self._client.download_file(self._bucket, key, local_path)

    def list_prefix(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for page in self._client.get_paginator("list_objects_v2").paginate(
                Bucket=self._bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys
