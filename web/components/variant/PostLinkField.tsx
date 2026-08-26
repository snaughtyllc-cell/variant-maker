"use client";
import { useEffect, useState } from "react";
import { VariantOut } from "@/lib/types";
import { setPostUrl } from "@/lib/api";
import {
  hostFromPostUrl,
  postLinkClearLabel,
  postLinkHint,
  postLinkLabel,
  postLinkOpenLabel,
  postLinkSaveLabel,
} from "@/lib/postUrl";

interface PostLinkFieldProps {
  sourceId: string;
  variant: VariantOut;
  onSaved: () => void;
}

export function PostLinkField({ sourceId, variant, onSaved }: PostLinkFieldProps) {
  const saved = variant.post_url?.trim() || "";
  const [draft, setDraft] = useState(saved);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(saved);
  }, [saved]);

  async function save(url: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await setPostUrl(sourceId, variant.index, url);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save link");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        marginBottom: 12,
        padding: "12px 12px 10px",
        background: "#12121a",
        border: "1px solid var(--color-line)",
        borderRadius: 10,
      }}
    >
      <div
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.7px",
          color: "var(--color-muted2)",
          fontWeight: 700,
          marginBottom: 6,
        }}
      >
        {postLinkLabel()}
      </div>
      <p
        style={{
          margin: "0 0 10px",
          fontSize: 11.5,
          lineHeight: 1.45,
          color: "var(--color-muted)",
        }}
      >
        {postLinkHint()}
      </p>
      {saved && (
        <a
          href={saved}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-block",
            marginBottom: 8,
            fontSize: 12.5,
            fontWeight: 700,
            color: "var(--color-cyan)",
            wordBreak: "break-all",
          }}
        >
          {postLinkOpenLabel()} · {hostFromPostUrl(saved)}
        </a>
      )}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input
          type="url"
          inputMode="url"
          autoComplete="url"
          placeholder="https://www.instagram.com/reel/…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={busy}
          aria-label={postLinkLabel()}
          style={{
            flex: "1 1 160px",
            minWidth: 0,
            background: "#f3f8f9",
            color: "var(--color-text)",
            border: "1px solid var(--color-line)",
            borderRadius: 8,
            padding: "10px 10px",
            fontSize: 16,
          }}
        />
        <button
          type="button"
          onClick={() => save(draft)}
          disabled={busy}
          style={{
            fontSize: 12.5,
            fontWeight: 700,
            padding: "10px 12px",
            borderRadius: 8,
            background: "#f3f8f9",
            border: "1px solid var(--color-line)",
            color: busy ? "var(--color-muted)" : "var(--color-text)",
            cursor: busy ? "not-allowed" : "pointer",
          }}
        >
          {busy ? "Saving…" : postLinkSaveLabel()}
        </button>
        {saved && (
          <button
            type="button"
            onClick={() => {
              setDraft("");
              void save("");
            }}
            disabled={busy}
            style={{
              fontSize: 12.5,
              fontWeight: 700,
              padding: "10px 12px",
              borderRadius: 8,
              background: "transparent",
              border: "1px solid var(--color-line)",
              color: "var(--color-muted)",
              cursor: busy ? "not-allowed" : "pointer",
            }}
          >
            {postLinkClearLabel()}
          </button>
        )}
      </div>
      {error && (
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--color-red)" }}>{error}</div>
      )}
    </div>
  );
}
