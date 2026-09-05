"""Per-workspace JobStore + Drive/caption files. Request-scoped via request.state.tenant."""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any

from .captions import CaptionStore
from .destinations import DestinationStore
from .drive_config import resolve_drive_status
from .drive_exports import ExportStore
from .drive_oauth import OAuthPendingStore, OAuthTokenStore
from .fast_occupancy import FastOccupancy, occupancy_from_env
from .instagram_oauth import InstagramAccountStore
from .jobs import JobStore
from .occupancy_journal import JOURNAL_NAME, OccupancyJournal
from .runner import Runner
from .tenants import tenant_root
from .workflows import WorkflowStore
from .workspace import Workspace


@dataclass
class TenantBundle:
    workspace_id: str
    ws: Workspace
    store: JobStore
    destinations: DestinationStore
    captions: CaptionStore
    workflows: WorkflowStore
    exports: ExportStore
    oauth_token_store: OAuthTokenStore
    oauth_pending: OAuthPendingStore
    instagram_accounts: InstagramAccountStore
    instagram_pending: OAuthPendingStore
    drive: Any = None
    sheets: Any = None


class TenantHub:
    """Lazy JobStore per workspace_id. Same runner (Fast/HQ) for every tenant."""

    def __init__(self, data_dir: str, runner: Runner,
                 object_store=None, gallery_keep_jobs: int | None = None,
                 gallery_keep_hours: float | None = None,
                 occupancy: FastOccupancy | None = None,
                 occupancy_journal: OccupancyJournal | None = None) -> None:
        self.data_dir = os.path.abspath(data_dir)
        self._runner = runner
        self._object_store = object_store
        self._gallery_keep_jobs = gallery_keep_jobs
        self._gallery_keep_hours = gallery_keep_hours
        self._occupancy = occupancy if occupancy is not None else occupancy_from_env()
        if occupancy_journal is not None:
            self._journal = occupancy_journal
        else:
            self._journal = OccupancyJournal(os.path.join(self.data_dir, JOURNAL_NAME))
        self._journal.on_process_start()
        self._lock = threading.Lock()
        self._bundles: dict[str, TenantBundle] = {}

    def bundle(self, workspace_id: str) -> TenantBundle:
        with self._lock:
            existing = self._bundles.get(workspace_id)
            if existing is not None:
                return existing
            root = tenant_root(self.data_dir, workspace_id)
            ws = Workspace(root)
            store = JobStore(
                ws, self._runner,
                object_store=self._object_store,
                gallery_keep_jobs=self._gallery_keep_jobs,
                gallery_keep_hours=self._gallery_keep_hours,
                workspace_id=workspace_id,
                drive_token_fn=getattr(self, "_drive_token_fn", None),
                occupancy=self._occupancy,
                occupancy_journal=self._journal,
            )
            store.hydrate_from_disk()
            built = TenantBundle(
                workspace_id=workspace_id,
                ws=ws,
                store=store,
                destinations=DestinationStore(ws.destinations_path()),
                captions=CaptionStore(ws.captions_path()),
                workflows=WorkflowStore(ws.workflows_path()),
                exports=ExportStore(ws.exports_dir()),
                oauth_token_store=OAuthTokenStore(ws.oauth_token_path()),
                oauth_pending=OAuthPendingStore(ws.oauth_pending_path()),
                instagram_accounts=InstagramAccountStore(ws.instagram_dir()),
                instagram_pending=OAuthPendingStore(ws.instagram_pending_path()),
            )
            self._bundles[workspace_id] = built
            return built

    def hydrate_all(self, workspace_ids: list[str]) -> None:
        for ws_id in workspace_ids:
            self.bundle(ws_id)
        self.finish_boot()

    def finish_boot(self) -> None:
        """Reconcile the Fast slot journal after hydrating in-flight jobs."""
        running_ids: set[str] = set()
        with self._lock:
            bundles = list(self._bundles.values())
        for bundle in bundles:
            for job in bundle.store._jobs.values():
                pid = (job.telemetry or {}).get("runpod_job_id")
                if pid:
                    running_ids.add(str(pid))
        self._journal.reconcile(running_ids)


def drive_ready(bundle: TenantBundle, *, sa_json_path: str | None, environ: dict):
    return resolve_drive_status(
        sa_json_path,
        oauth_token_path=bundle.ws.oauth_token_path(),
        environ=environ,
    )
