"""Filesystem layout for the local control plane. One directory tree per job."""
from __future__ import annotations

import os


class Workspace:
    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)

    def _source_dir(self, job_id: str, source_id: str) -> str:
        return os.path.join(self.root, "jobs", job_id, source_id)

    def source_in_path(self, job_id: str, source_id: str, filename: str) -> str:
        return os.path.join(self._source_dir(job_id, source_id), "in", filename)

    def source_out_dir(self, job_id: str, source_id: str) -> str:
        out = os.path.join(self._source_dir(job_id, source_id), "out")
        os.makedirs(out, exist_ok=True)
        return out

    def variant_path(self, job_id: str, source_id: str, filename: str) -> str:
        return os.path.join(self.source_out_dir(job_id, source_id), filename)

    def save_upload(self, job_id: str, source_id: str, filename: str, data: bytes) -> str:
        path = self.source_in_path(job_id, source_id, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def upload_staging_dir(self, upload_id: str) -> str:
        d = os.path.join(self.root, "uploads", upload_id)
        os.makedirs(d, exist_ok=True)
        return d

    def upload_blob_path(self, upload_id: str, filename: str) -> str:
        return os.path.join(self.upload_staging_dir(upload_id), filename)

    def drive_dir(self) -> str:
        d = os.path.join(self.root, "drive")
        os.makedirs(d, exist_ok=True)
        return d

    def destinations_path(self) -> str:
        return os.path.join(self.drive_dir(), "destinations.json")

    def oauth_token_path(self) -> str:
        return os.path.join(self.drive_dir(), "oauth_token.json")

    def exports_dir(self) -> str:
        d = os.path.join(self.drive_dir(), "exports")
        os.makedirs(d, exist_ok=True)
        return d
