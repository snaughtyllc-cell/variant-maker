"use client";
import { FormEvent, useEffect, useState, type CSSProperties } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { KeyRound } from "lucide-react";
import {
  createWorkspaceApiKey,
  getWorkspaceApiKeys,
  revokeWorkspaceApiKey,
} from "@/lib/api";
import { useAuthMe } from "@/lib/useAuthMe";
import { showIntegrationsNav } from "@/lib/navAccess";
import type { WorkspaceApiKey, WorkspaceApiKeysPage } from "@/lib/types";

const COPY_BTN: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: "var(--color-text)",
  background: "var(--color-panel2)",
  border: "1px solid var(--color-line)",
  padding: "7px 12px",
  borderRadius: 9,
  cursor: "pointer",
  flexShrink: 0,
};

export default function IntegrationsPage() {
  const router = useRouter();
  const { data: me, isLoading: meLoading } = useAuthMe();
  const allowed = showIntegrationsNav(me);
  const [page, setPage] = useState<WorkspaceApiKeysPage | null>(null);
  const [label, setLabel] = useState("Agency bot");
  const [preset, setPreset] = useState<"full" | "read">("full");
  const [expiresDays, setExpiresDays] = useState(90);
  const [token, setToken] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [origin, setOrigin] = useState("https://your-studio.example");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);

  useEffect(() => {
    if (meLoading) return;
    if (!allowed) router.replace("/");
  }, [meLoading, allowed, router]);

  useEffect(() => {
    setOrigin(window.location.origin);
  }, []);

  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    (async () => {
      try {
        const next = await getWorkspaceApiKeys();
        if (!cancelled) setPage(next);
      } catch (err) {
        if (!cancelled) {
          setFormError(err instanceof Error ? err.message : "Failed to load keys");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [allowed]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setFormError(null);
    setCopied(null);
    setSubmitting(true);
    try {
      const created = await createWorkspaceApiKey({
        label: label.trim(),
        preset,
        expires_days: expiresDays,
      });
      const { token: revealed, ...row } = created;
      setToken(revealed);
      setPage((prev) =>
        prev
          ? { ...prev, keys: [row, ...prev.keys.filter((k) => k.key_id !== row.key_id)] }
          : prev,
      );
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create key");
    } finally {
      setSubmitting(false);
    }
  }

  async function copyText(text: string, which: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
    } catch {
      setFormError("Copy failed — select the text and copy it yourself.");
    }
  }

  async function handleRevoke(key: WorkspaceApiKey) {
    if (revoking) return;
    const ok = window.confirm(
      `Revoke ${key.label}? Integrations using this key will stop on the next request.`,
    );
    if (!ok) return;
    setRevoking(key.key_id);
    setFormError(null);
    try {
      await revokeWorkspaceApiKey(key.key_id);
      setPage((prev) =>
        prev
          ? {
              ...prev,
              keys: prev.keys.map((k) =>
                k.key_id === key.key_id
                  ? { ...k, revoked_utc: k.revoked_utc || new Date().toISOString() }
                  : k,
              ),
            }
          : prev,
      );
      if (token && token.startsWith(key.prefix)) setToken(null);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to revoke key");
    } finally {
      setRevoking(null);
    }
  }

  if (meLoading || !allowed) {
    return (
      <main className="team-page integrations-page">
        <div style={{ color: "var(--color-muted)", fontSize: 13 }}>
          {meLoading ? "Loading…" : "Owner only"}
        </div>
      </main>
    );
  }

  const studioName = page?.workspace_name || me?.workspace_name || "this studio";
  const machineSnippet = [
    `export VARIMO_BASE_URL="${origin}"`,
    `export VARIMO_API_KEY="paste-the-key-you-copied"`,
    `pip install -e ".[mcp]"`,
    "varimo-mcp",
  ].join("\n");

  return (
    <main className="team-page integrations-page">
      <div className="workspace-heading">
        <span className="workspace-heading__icon"><KeyRound size={19} /></span>
        <div>
          <p className="workspace-heading__eyebrow">Workspace access</p>
          <h1>Integrations</h1>
          <p className="workspace-heading__copy">
            Issue a key so your own automation can make Fast packs in{" "}
            <strong style={{ color: "var(--color-text)", fontWeight: 700 }}>{studioName}</strong>,
            read Gallery metadata, and send ready copies to a Drive folder you already connected.
            Review still happens in Gallery. We do not post.
          </p>
        </div>
      </div>

      <div>
        {formError && (
          <div className="vf-alert" role="alert">{formError}</div>
        )}

        <p style={{ fontSize: 12.5, color: "var(--color-muted)", lineHeight: 1.45, marginBottom: 18 }}>
          A key can generate billable Fast work and read the packs in this workspace.
          Connect folders on <Link href="/settings/drive">Drive</Link> first.
          Lost token? Revoke it and create another — we only show the secret once.
        </p>

        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)", marginBottom: 10 }}>
          Create key
        </div>
        <form
          onSubmit={handleCreate}
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <input
            type="text"
            required
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label"
            aria-label="Key label"
            style={{
              background: "var(--color-panel2)",
              border: "1px solid var(--color-line)",
              borderRadius: 9,
              padding: "8px 12px",
              fontSize: 13,
              color: "var(--color-text)",
              minWidth: 180,
            }}
          />
          <select
            value={preset}
            onChange={(e) => setPreset(e.target.value as "full" | "read")}
            aria-label="Key preset"
            style={{
              background: "var(--color-panel2)",
              border: "1px solid var(--color-line)",
              borderRadius: 9,
              padding: "8px 12px",
              fontSize: 13,
              color: "var(--color-text)",
            }}
          >
            <option value="full">Packs + Gallery + export</option>
            <option value="read">Read only</option>
          </select>
          <select
            value={expiresDays}
            onChange={(e) => setExpiresDays(Number(e.target.value))}
            aria-label="Expiry"
            style={{
              background: "var(--color-panel2)",
              border: "1px solid var(--color-line)",
              borderRadius: 9,
              padding: "8px 12px",
              fontSize: 13,
              color: "var(--color-text)",
            }}
          >
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
          </select>
          <button
            type="submit"
            disabled={submitting}
            className="vf-primary-button"
            style={{ cursor: submitting ? "wait" : "pointer" }}
          >
            {submitting ? "Creating…" : "Create key"}
          </button>
        </form>

        {token && (
          <div
            role="status"
            style={{
              background: "var(--color-panel2)",
              border: "1px solid var(--color-line)",
              borderRadius: 14,
              padding: 14,
              marginBottom: 22,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
              Copy this now. We cannot show it again.
            </div>
            <code
              style={{
                display: "block",
                fontSize: 12,
                wordBreak: "break-all",
                marginBottom: 10,
              }}
            >
              {token}
            </code>
            <button
              type="button"
              className="vf-primary-button"
              onClick={() => { if (token) void copyText(token, "token"); }}
            >
              {copied === "token" ? "Copied" : "Copy"}
            </button>
            <button
              type="button"
              onClick={() => setToken(null)}
              style={{
                marginLeft: 8,
                fontSize: 12,
                fontWeight: 600,
                color: "var(--color-muted)",
                background: "transparent",
                border: 0,
                cursor: "pointer",
              }}
            >
              Dismiss
            </button>
          </div>
        )}

        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)", marginBottom: 8 }}>
          Same folders as Drive
        </div>
        <p style={{ fontSize: 12.5, color: "var(--color-muted)", lineHeight: 1.45, marginBottom: 10 }}>
          Not a second Drive. These are the folders you already added on{" "}
          <Link href="/settings/drive">Drive</Link>. Your bot cannot tap that screen, so
          copy the <code>dst_…</code> id when it asks which folder to use.
        </p>
        <div
          style={{
            background: "var(--color-panel)",
            border: "1px solid var(--color-line)",
            borderRadius: 14,
            marginBottom: 28,
            overflow: "hidden",
          }}
        >
          {(page?.destinations ?? []).length === 0 ? (
            <div style={{ padding: 14, fontSize: 12.5, color: "var(--color-muted)" }}>
              No folders yet. Add them on <Link href="/settings/drive">Drive</Link>.
            </div>
          ) : (
            (page?.destinations ?? []).map((d) => (
              <div
                key={d.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--color-line)",
                  fontSize: 12.5,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700 }}>{d.name}</div>
                  <div style={{ color: "var(--color-muted)", marginTop: 2, fontFamily: "var(--font-geist-mono), monospace" }}>
                    {d.id}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void copyText(d.id, `dest:${d.id}`)}
                  aria-label={`Copy ${d.name} folder id`}
                  style={COPY_BTN}
                >
                  {copied === `dest:${d.id}` ? "Copied" : "Copy"}
                </button>
              </div>
            ))
          )}
        </div>

        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)", marginBottom: 10 }}>
          Keys
        </div>
        <div
          style={{
            background: "var(--color-panel)",
            border: "1px solid var(--color-line)",
            borderRadius: 14,
            overflow: "hidden",
          }}
        >
          {(page?.keys ?? []).length === 0 ? (
            <div style={{ padding: 14, fontSize: 12.5, color: "var(--color-muted)" }}>No keys yet.</div>
          ) : (
            (page?.keys ?? []).map((key) => (
              <div
                key={key.key_id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--color-line)",
                  fontSize: 12.5,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700 }}>{key.label}</div>
                  <div style={{ color: "var(--color-muted)", marginTop: 2 }}>
                    {key.prefix} · {key.scopes.join(", ")}
                    {key.revoked_utc ? " · revoked" : ""}
                  </div>
                </div>
                {!key.revoked_utc && (
                  <button
                    type="button"
                    onClick={() => handleRevoke(key)}
                    disabled={revoking === key.key_id}
                    aria-label={`Revoke ${key.label}`}
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--color-red)",
                      background: "var(--color-panel2)",
                      border: "1px solid var(--color-line)",
                      padding: "7px 12px",
                      borderRadius: 9,
                      cursor: revoking === key.key_id ? "wait" : "pointer",
                    }}
                  >
                    {revoking === key.key_id ? "Revoking…" : "Revoke"}
                  </button>
                )}
              </div>
            ))
          )}
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginTop: 28,
            marginBottom: 10,
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)", flex: 1 }}>
            On your machine
          </div>
          <button
            type="button"
            onClick={() => void copyText(machineSnippet, "mcp")}
            aria-label="Copy on-your-machine setup"
            style={COPY_BTN}
          >
            {copied === "mcp" ? "Copied" : "Copy"}
          </button>
        </div>
        <p style={{ fontSize: 12.5, color: "var(--color-muted)", lineHeight: 1.45, marginBottom: 12 }}>
          This runs on the agency computer (or paste it into your AI app). Same Fast pack /
          Gallery metadata / Drive export loop. We do not host it, and we do not post.
        </p>
        <pre
          style={{
            background: "var(--color-panel2)",
            border: "1px solid var(--color-line)",
            borderRadius: 14,
            padding: 14,
            fontSize: 12,
            overflowX: "auto",
            marginBottom: 18,
          }}
        >{machineSnippet}</pre>
      </div>
    </main>
  );
}
