"use client";
import { useEffect, useState, type CSSProperties } from "react";
import { ensureDropLedger, getDropLedgerStatus, syncDropLedger } from "@/lib/api";
import type { DropLedgerStatus, DropLedgerSync } from "@/lib/types";

function needsGoogleConnect(status: DropLedgerStatus | null): boolean {
  return Boolean(status && /connect google/i.test(status.message));
}

export function DropLedgerPanel() {
  const [status, setStatus] = useState<DropLedgerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [ensuring, setEnsuring] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<DropLedgerSync | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      const next = await getDropLedgerStatus();
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Drop Ledger status");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const googleMissing = needsGoogleConnect(status);
  const busy = ensuring || syncing;
  const actionsDisabled = loading || busy || googleMissing;
  const sheetUrl = status?.spreadsheet_url;

  async function handleEnsure() {
    if (actionsDisabled) return;
    setEnsuring(true);
    setError(null);
    try {
      const out = await ensureDropLedger();
      setStatus({
        configured: true,
        spreadsheet_id: out.spreadsheet_id,
        spreadsheet_url: out.spreadsheet_url,
        message: out.created
          ? "Created VaryForge Drop Ledger"
          : "Drop Ledger is ready",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create the Drop Ledger sheet");
    } finally {
      setEnsuring(false);
    }
  }

  async function handleSync() {
    if (actionsDisabled) return;
    setSyncing(true);
    setError(null);
    try {
      const out = await syncDropLedger({ ensure: true });
      setSyncResult(out);
      setStatus({
        configured: true,
        spreadsheet_id: out.spreadsheet_id,
        spreadsheet_url: out.spreadsheet_url,
        message: "Drop Ledger is ready",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sync from Studio");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div>
      <div style={{ fontSize: 16, fontWeight: 800, color: "var(--color-text)" }}>Drop Ledger</div>
      <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2, maxWidth: 640, lineHeight: 1.45 }}>
        A Google Sheet of Passed / Duplicate rejected / Flagged for each clip, so labels
        survive a wipe. Mark results in the Gallery — unlabeled clips count as pass.
        You do not need to live in the sheet. This does not change uniqueness.
      </div>

      <div
        style={{
          marginTop: 14,
          background: "var(--color-panel)",
          border: "1px solid var(--color-line)",
          borderRadius: 14,
          padding: 16,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)" }}>Status</div>
        <div style={{ fontSize: 12.5, color: "var(--color-muted)", marginTop: 4, lineHeight: 1.45 }}>
          {loading ? "Loading…" : status?.message || "No status yet."}
        </div>

        {googleMissing && (
          <div
            role="status"
            style={{
              marginTop: 10,
              padding: "10px 12px",
              background: "#1c1608",
              border: "1px solid #3a2c10",
              borderRadius: 10,
              color: "#ffd08a",
              fontSize: 12.5,
              lineHeight: 1.45,
            }}
          >
            Connect Google above first. Then tap Ensure sheet to create VaryForge Drop Ledger.
          </div>
        )}

        {error && (
          <div
            role="alert"
            style={{
              marginTop: 10,
              padding: "10px 12px",
              background: "#1c1608",
              border: "1px solid #3a2c10",
              borderRadius: 10,
              color: "#ffd08a",
              fontSize: 12.5,
            }}
          >
            {error}
          </div>
        )}

        {syncResult && (
          <div
            role="status"
            style={{
              marginTop: 10,
              fontSize: 12.5,
              color: "var(--color-text)",
              lineHeight: 1.45,
            }}
          >
            Synced {syncResult.rows} clips — {syncResult.inserted} new, {syncResult.updated}{" "}
            updated, {syncResult.unchanged} unchanged. Existing labels were kept.
          </div>
        )}

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14, alignItems: "center" }}>
          <button
            type="button"
            onClick={() => void handleEnsure()}
            disabled={actionsDisabled}
            style={primaryBtn(actionsDisabled)}
          >
            {ensuring ? "Creating sheet…" : "Ensure sheet"}
          </button>
          <button
            type="button"
            onClick={() => void handleSync()}
            disabled={actionsDisabled}
            style={secondaryBtn(actionsDisabled)}
          >
            {syncing ? "Syncing…" : "Sync from Studio"}
          </button>
          {sheetUrl && (
            <a
              href={sheetUrl}
              target="_blank"
              rel="noreferrer"
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#c7b8ff",
                padding: "7px 12px",
              }}
            >
              Open sheet
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function primaryBtn(disabled: boolean): CSSProperties {
  return {
    fontSize: 12.5,
    fontWeight: 700,
    color: "#fff",
    background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
    border: "none",
    padding: "8px 14px",
    borderRadius: 9,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.7 : 1,
  };
}

function secondaryBtn(disabled: boolean): CSSProperties {
  return {
    fontSize: 12,
    fontWeight: 600,
    color: "var(--color-text)",
    background: "var(--color-panel2)",
    border: "1px solid var(--color-line)",
    padding: "7px 12px",
    borderRadius: 9,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.7 : 1,
  };
}
