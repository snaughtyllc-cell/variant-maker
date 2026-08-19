"use client";
import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from "react";
import {
  bulkCaptions,
  createCaption,
  deleteCaption,
  listCaptions,
  updateCaption,
} from "@/lib/api";
import { captionBankChatPrompt, captionFilenamePreview, splitCaptionBank } from "@/lib/captions";
import type { Caption } from "@/lib/types";

export function CaptionBankPanel() {
  const [items, setItems] = useState<Caption[]>([]);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState("");
  const [paste, setPaste] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [count, setCount] = useState(20);
  const [topic, setTopic] = useState("");
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    setLoading(true);
    try {
      const bank = await listCaptions();
      setItems(bank.items);
    } catch (e) {
      console.error("Failed to load captions", e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const created = await createCaption(text.trim());
      setItems((prev) => [...prev, created]);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add caption");
    } finally {
      setSaving(false);
    }
  }

  async function importRaw(raw: string, emptyMsg: string) {
    if (saving) return;
    const blocks = splitCaptionBank(raw);
    if (!blocks.length) {
      setError(emptyMsg);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const bank = await bulkCaptions(raw);
      setItems(bank.items);
      setPaste("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import captions");
    } finally {
      setSaving(false);
    }
  }

  async function handlePaste(e: FormEvent) {
    e.preventDefault();
    await importRaw(paste, "Nothing to paste — need captions separated by --- or a blank line.");
  }

  async function handleCopyPrompt() {
    const prompt = captionBankChatPrompt({ count, topic });
    try {
      await navigator.clipboard.writeText(prompt);
    } catch {
      setPaste(prompt);
      setError("Clipboard blocked — prompt is in the paste box. Copy it from there.");
      return;
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  async function handleImportFile(file: File | undefined) {
    if (!file) return;
    const raw = await file.text();
    await importRaw(raw, "That file had no captions. Use --- between them, or a blank line.");
    if (fileRef.current) fileRef.current.value = "";
  }

  async function handleSaveEdit(id: string) {
    if (!editText.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateCaption(id, editText.trim());
      setItems((prev) => prev.map((c) => (c.id === id ? updated : c)));
      setEditingId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save caption");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Remove this caption from the bank?")) return;
    try {
      await deleteCaption(id);
      setItems((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      console.error("Failed to delete caption", err);
    }
  }

  return (
    <div>
      <div style={{ fontSize: 16, fontWeight: 800, color: "var(--color-text)" }}>Caption bank</div>
      <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2, maxWidth: 640, lineHeight: 1.45 }}>
        Repurpose.io uses the Drive filename as the post caption. Paste captions here, then turn
        auto-caption on for a workflow — or edit them on Gallery Send to Drive before export.
        Copy the ChatGPT prompt, paste the reply (or a .txt), and import.
      </div>

      <div
        style={{
          marginTop: 14,
          padding: 12,
          border: "1px solid var(--color-line)",
          borderRadius: 12,
          background: "var(--color-panel)",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 700 }}>Generate in ChatGPT / Claude</div>
        <div style={{ fontSize: 12, color: "var(--color-muted)", lineHeight: 1.45 }}>
          Copy the prompt, paste it in a chat, then import the reply here (paste box or .txt file).
        </div>
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="What's the page about? (dating POV, gym, etc.)"
          style={{ ...areaStyle, resize: "none" }}
        />
        <label style={{ fontSize: 12, color: "var(--color-muted)" }}>
          How many{" "}
          <input
            type="number"
            min={1}
            max={100}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            style={{
              width: 64,
              marginLeft: 6,
              background: "var(--color-panel2)",
              border: "1px solid var(--color-line)",
              borderRadius: 8,
              padding: "6px 8px",
              color: "var(--color-text)",
            }}
          />
        </label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <button type="button" onClick={handleCopyPrompt} style={primaryBtn(false)}>
            {copied ? "Copied" : "Copy chat prompt"}
          </button>
          <button type="button" onClick={() => fileRef.current?.click()} style={secondaryBtn(saving)}>
            Import .txt
          </button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".txt,.md,text/plain"
          style={{ display: "none" }}
          onChange={(e) => void handleImportFile(e.target.files?.[0])}
        />
      </div>

      <form onSubmit={handleAdd} style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="One caption (hashtags welcome)"
          rows={3}
          style={areaStyle}
        />
        {text.trim() && (
          <div style={{ fontSize: 11, color: "var(--color-muted2)" }}>
            Drive name: {captionFilenamePreview(text)}
          </div>
        )}
        <button type="submit" disabled={saving || !text.trim()} style={primaryBtn(saving || !text.trim())}>
          {saving ? "Saving…" : "Add caption"}
        </button>
      </form>

      <form onSubmit={handlePaste} style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
        <textarea
          value={paste}
          onChange={(e) => setPaste(e.target.value)}
          placeholder={"Paste several captions\n---\nNext caption"}
          rows={5}
          style={areaStyle}
        />
        <button
          type="submit"
          disabled={saving || splitCaptionBank(paste).length === 0}
          style={secondaryBtn(saving || splitCaptionBank(paste).length === 0)}
        >
          Paste bank ({splitCaptionBank(paste).length})
        </button>
      </form>

      {error && <div style={{ fontSize: 12, color: "var(--color-red)", marginTop: 10 }}>{error}</div>}

      {loading && (
        <div style={{ padding: "24px 0", color: "var(--color-muted)", fontSize: 13 }}>Loading captions…</div>
      )}

      {!loading && items.length === 0 && (
        <div style={{ marginTop: 14, fontSize: 12.5, color: "var(--color-muted)" }}>
          Bank is empty — workflows keep v01.mp4 names until you add captions and turn auto-caption on.
        </div>
      )}

      <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((cap, i) => (
          <div
            key={cap.id}
            style={{
              background: "var(--color-panel)",
              border: "1px solid var(--color-line)",
              borderRadius: 12,
              padding: "10px 12px",
            }}
          >
            <div style={{ fontSize: 11, color: "var(--color-muted2)", marginBottom: 6 }}>#{i + 1}</div>
            {editingId === cap.id ? (
              <>
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  rows={3}
                  style={areaStyle}
                />
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <button type="button" onClick={() => handleSaveEdit(cap.id)} style={primaryBtn(saving)}>
                    Save
                  </button>
                  <button type="button" onClick={() => setEditingId(null)} style={secondaryBtn(false)}>
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 13, color: "var(--color-text)", whiteSpace: "pre-wrap" }}>{cap.text}</div>
                <div style={{ fontSize: 11, color: "var(--color-muted2)", marginTop: 6 }}>
                  {captionFilenamePreview(cap.text)}
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <button
                    type="button"
                    onClick={() => { setEditingId(cap.id); setEditText(cap.text); }}
                    style={secondaryBtn(false)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(cap.id)}
                    style={{ ...secondaryBtn(false), color: "var(--color-red)" }}
                  >
                    Delete
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

const areaStyle: CSSProperties = {
  background: "var(--color-panel2)",
  border: "1px solid var(--color-line)",
  borderRadius: 9,
  padding: "9px 12px",
  fontSize: 13,
  color: "var(--color-text)",
  outline: "none",
  width: "100%",
  resize: "vertical",
};

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
    alignSelf: "flex-start",
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
    borderRadius: 8,
    cursor: disabled ? "not-allowed" : "pointer",
  };
}
