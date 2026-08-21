"""Object storage seam for moving files in/out of stateless GPU workers (S3 API)."""
from __future__ import annotations

import os
from typing import Protocol


class ObjectStore(Protocol):
    def put(self, key: str, local_path: str) -> None: ...
    def get(self, key: str, local_path: str) -> None: ...
    def list_prefix(self, prefix: str) -> list[str]: ...
    def delete_prefix(self, prefix: str) -> int: ...


_R2_ENV = ("R2_ENDPOINT", "R2_BUCKET", "R2_ACCESS_KEY", "R2_SECRET_KEY")
_DELETE_BATCH = 1000


def _make_client(*, endpoint_url: str, access_key: str, secret_key: str, region: str):
    import boto3  # lazy: only needed when a real S3 store is constructed
    from botocore.config import Config
    extra = {}
    style = os.environ.get("R2_ADDRESSING_STYLE", "").strip().lower()
    if style in ("virtual", "path"):
        extra["config"] = Config(s3={"addressing_style": style})
    return boto3.client(
        "s3", endpoint_url=endpoint_url, aws_access_key_id=access_key,
        aws_secret_access_key=secret_key, region_name=region, **extra,
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

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object under prefix. Empty prefix is refused (whole bucket)."""
        if not prefix:
            return 0
        keys = self.list_prefix(prefix)
        deleted = 0
        for i in range(0, len(keys), _DELETE_BATCH):
            batch = keys[i:i + _DELETE_BATCH]
            self._client.delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
            )
            deleted += len(batch)
        return deleted


def object_store_from_env(environ: dict | None = None) -> S3ObjectStore | None:
    """Build an S3/R2 store when R2_* env is complete; otherwise None (local runner)."""
    env = os.environ if environ is None else environ
    if not all((env.get(k) or "").strip() for k in _R2_ENV):
        return None
    return S3ObjectStore(
        endpoint_url=env["R2_ENDPOINT"], bucket=env["R2_BUCKET"],
        access_key=env["R2_ACCESS_KEY"], secret_key=env["R2_SECRET_KEY"],
    )
