"use client";
import { useEffect, useState } from "react";
import { getDriveStatus } from "@/lib/api";
import type { DriveStatus } from "@/lib/types";

export function DriveTopbar() {
  const [status, setStatus] = useState<DriveStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await getDriveStatus();
        if (!cancelled) setStatus(next);
      } catch {
        if (!cancelled) setStatus(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = status?.status === "ready";
  const label =
    status == null
      ? "Checking Google…"
      : ready
        ? "Google connected"
        : "Google not connected";

  return (
    <div className="drive-topbar">
      <span className="drive-topbar__section">DRIVE</span>
      <span className="drive-topbar__sep">/</span>
      <span className="drive-topbar__crumb">Delivery setup</span>
      <div className="drive-topbar__spacer" />
      <div
        className="drive-topbar__status"
        data-ready={ready ? "true" : "false"}
        data-testid="drive-topbar-status"
      >
        <span className="drive-topbar__dot" data-ready={ready ? "true" : "false"} />
        {label}
      </div>
    </div>
  );
}
