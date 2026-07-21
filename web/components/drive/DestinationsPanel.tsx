"use client";
import { useEffect, useState } from "react";
import {
  createDestination,
  deleteDestination,
  getDriveStatus,
  listDestinations,
  testDestination,
  updateDestination,
} from "@/lib/api";
import { truncateFolderId } from "@/lib/drive";
import type { Destination, DriveStatus } from "@/lib/types";

type TestResult = { ok: boolean; message: string };

export function DestinationsPanel() {
  const [status, setStatus] = useState<DriveStatus | null>(null);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [name, setName] = useState("");
  const [folderUrl, setFolderUrl] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editFolderUrl, setEditFolderUrl] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [testingId, setTestingId] = useState<string | null>(null);

  async function refresh() {
    setIsLoading(true);
    try {
      const [s, d] = await Promise.all([getDriveStatus(), listDestinations()]);
      setStatus(s);
      setDestinations(d);
    } catch (e) {
      console.error("Failed to load Drive status", e);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setFormError(null);
    setSubmitting(true);
    try {
      const created = await createDestination(name.trim(), folderUrl.trim());
      setDestinations((prev) => [...prev, created]);
      setName("");
      setFolderUrl("");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to add destination");
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(dest: Destination) {
    setEditingId(dest.id);
    setEditName(dest.name);
    setEditFolderUrl("");
    setEditError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditError(null);
  }

  async function handleSaveEdit(id: string) {
    setEditError(null);
    try {
      const patch: { name?: string; folder_url?: string } = { name: editName.trim() };
      if (editFolderUrl.trim()) patch.folder_url = editFolderUrl.trim();
      const updated = await updateDestination(id, patch);
      setDestinations((prev) => prev.map((d) => (d.id === id ? updated : d)));
      setEditingId(null);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Failed to update destination");
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Delete this destination?")) return;
    try {
      await deleteDestination(id);
      setDestinations((prev) => prev.filter((d) => d.id !== id));
      setTestResults((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      console.error("Failed to delete destination", err);
    }
  }

  async function handleTest(id: string) {
    setTestingId(id);
    try {
      const res = await testDestination(id);
      setTestResults((prev) => ({
        ...prev,
        [id]: res.ok ? { ok: true, message: "Access confirmed" } : { ok: false, message: "Access failed" },
      }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [id]: { ok: false, message: err instanceof Error ? err.message : "Access failed" },
      }));
    } finally {
      setTestingId(null);
    }
  }

  const driveNotReady = status != null && status.status !== "ready";

  return (
    <div>
      {/* Banner when Drive is not ready */}
      {driveNotReady && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 6,
            padding: "12px 16px",
            marginBottom: 18,
            background: "#1c1608",
            border: "1px solid #3a2c10",
            borderRadius: 12,
            fontSize: 12.5,
            color: "#ffd08a",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>⚠</span>
            <b>{status!.message}</b>
          </div>
          {status!.sa_email && (
            <div style={{ color: "var(--color-muted)", fontSize: 12 }}>
              Share folders as Editor with {status!.sa_email}
            </div>
          )}
        </div>
      )}

      {/* Add destination form */}
      <form
        onSubmit={handleCreate}
        style={{
          background: "var(--color-panel)",
          border: "1px solid var(--color-line)",
          borderRadius: 14,
          padding: 16,
          marginBottom: 18,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)" }}>
          Add destination
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name"
            required
            style={inputStyle}
          />
          <input
            value={folderUrl}
            onChange={(e) => setFolderUrl(e.target.value)}
            placeholder="Paste Drive folder link"
            required
            style={{ ...inputStyle, flex: 1, minWidth: 220 }}
          />
          <button
            type="submit"
            disabled={submitting}
            style={{
              fontSize: 12.5,
              fontWeight: 700,
              color: "#fff",
              background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
              border: "none",
              padding: "9px 16px",
              borderRadius: 9,
              cursor: submitting ? "not-allowed" : "pointer",
              opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? "Adding…" : "Add"}
          </button>
        </div>
        {formError && (
          <div style={{ fontSize: 12, color: "var(--color-red)" }}>{formError}</div>
        )}
      </form>

      {/* Destinations list */}
      {isLoading && (
        <div style={{ padding: "40px 0", textAlign: "center", color: "var(--color-muted)", fontSize: 13 }}>
          Loading destinations…
        </div>
      )}

      {!isLoading && destinations.length === 0 && (
        <div
          style={{
            padding: "14px 16px",
            border: "1px dashed var(--color-line2)",
            borderRadius: 12,
            color: "var(--color-muted)",
            fontSize: 12.5,
            background: "#0d0d13",
          }}
        >
          No destinations yet — add a Drive folder above.
        </div>
      )}

      {destinations.map((dest) => {
        const isEditing = editingId === dest.id;
        const testResult = testResults[dest.id];
        return (
          <div
            key={dest.id}
            style={{
              background: "var(--color-panel)",
              border: "1px solid var(--color-line)",
              borderRadius: 14,
              padding: "14px 16px",
              marginBottom: 10,
            }}
          >
            {isEditing ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="Name"
                    style={inputStyle}
                  />
                  <input
                    value={editFolderUrl}
                    onChange={(e) => setEditFolderUrl(e.target.value)}
                    placeholder="New Drive folder link (optional)"
                    style={{ ...inputStyle, flex: 1, minWidth: 220 }}
                  />
                </div>
                {editError && (
                  <div style={{ fontSize: 12, color: "var(--color-red)" }}>{editError}</div>
                )}
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => handleSaveEdit(dest.id)} style={primaryBtnStyle}>
                    Save
                  </button>
                  <button onClick={cancelEdit} style={secondaryBtnStyle}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)" }}>
                    {dest.name}
                  </div>
                  <div style={{ fontSize: 11.5, color: "var(--color-muted)", marginTop: 2 }}>
                    {truncateFolderId(dest.folder_id)} · {dest.auth_mode}
                  </div>
                  {testResult && (
                    <div
                      style={{
                        fontSize: 11.5,
                        marginTop: 4,
                        color: testResult.ok ? "#7bf2a8" : "var(--color-red)",
                      }}
                    >
                      {testResult.ok ? "✓ " : "✕ "}
                      {testResult.message}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                  <button
                    onClick={() => handleTest(dest.id)}
                    disabled={testingId === dest.id}
                    style={secondaryBtnStyle}
                  >
                    {testingId === dest.id ? "Testing…" : "Test access"}
                  </button>
                  <button onClick={() => startEdit(dest)} style={secondaryBtnStyle}>
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(dest.id)}
                    style={{ ...secondaryBtnStyle, color: "var(--color-red)" }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "var(--color-panel2)",
  border: "1px solid var(--color-line)",
  borderRadius: 9,
  padding: "8px 12px",
  fontSize: 12.5,
  color: "var(--color-text)",
  outline: "none",
};

const secondaryBtnStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: "var(--color-text)",
  background: "var(--color-panel2)",
  border: "1px solid var(--color-line)",
  padding: "7px 12px",
  borderRadius: 9,
  cursor: "pointer",
};

const primaryBtnStyle: React.CSSProperties = {
  fontSize: 12.5,
  fontWeight: 700,
  color: "#fff",
  background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
  border: "none",
  padding: "8px 14px",
  borderRadius: 9,
  cursor: "pointer",
};
