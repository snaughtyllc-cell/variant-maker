"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import {
  deleteLora,
  listLoras,
  requestLoraTrain,
  uploadLora,
} from "@/lib/createApi";
import { LoraOut } from "@/lib/createTypes";

interface LoraIdentityPanelProps {
  selectedId: string | null;
  strength: number;
  onSelect: (lora: LoraOut | null) => void;
  onStrengthChange: (v: number) => void;
  disabled?: boolean;
}

export function LoraIdentityPanel({
  selectedId,
  strength,
  onSelect,
  onStrengthChange,
  disabled,
}: LoraIdentityPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [loras, setLoras] = useState<LoraOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState("");
  const [trainMsg, setTrainMsg] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      const rows = await listLoras();
      setLoras(rows);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load LoRAs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleUpload(file: File) {
    const label = name.trim() || file.name.replace(/\.safetensors$/i, "");
    setUploading(true);
    setError(null);
    try {
      const rec = await uploadLora({
        name: label,
        file,
        triggerWord: trigger.trim() || undefined,
        defaultStrength: strength,
      });
      setLoras((prev) => [rec, ...prev.filter((l) => l.id !== rec.id)]);
      onSelect(rec);
      onStrengthChange(rec.default_strength);
      setName("");
      setTrigger("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteLora(id);
      setLoras((prev) => prev.filter((l) => l.id !== id));
      if (selectedId === id) onSelect(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  async function handleTrainStub() {
    setTrainMsg(null);
    try {
      const status = await requestLoraTrain({ name: name.trim() || "creator", photos: [] });
      setTrainMsg(status.message);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Train request failed");
    }
  }

  const selected = loras.find((l) => l.id === selectedId) ?? null;

  return (
    <div>
      {loading ? (
        <p style={{ fontSize: 12, color: "var(--color-muted)", margin: "0 0 10px" }}>
          Loading LoRAs…
        </p>
      ) : loras.length === 0 ? (
        <p style={{ fontSize: 12, color: "var(--color-muted)", margin: "0 0 10px" }}>
          No LoRAs yet — upload a trained SDXL <code>.safetensors</code>.
        </p>
      ) : (
        <ul
          style={{
            listStyle: "none",
            margin: "0 0 12px",
            padding: 0,
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {loras.map((l) => {
            const active = l.id === selectedId;
            return (
              <li
                key={l.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 10px",
                  borderRadius: 9,
                  border: active
                    ? "1px solid var(--color-violet)"
                    : "1px solid var(--color-line)",
                  background: active ? "#16122a" : "var(--color-panel2)",
                }}
              >
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    onSelect(l);
                    onStrengthChange(l.default_strength);
                  }}
                  style={{
                    flex: 1,
                    textAlign: "left",
                    background: "transparent",
                    border: "none",
                    color: "var(--color-text)",
                    cursor: disabled ? "not-allowed" : "pointer",
                    padding: 0,
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{l.name}</div>
                  <div style={{ fontSize: 11, color: "var(--color-muted)", marginTop: 2 }}>
                    {l.trigger_word
                      ? `trigger “${l.trigger_word}” · default ${l.default_strength.toFixed(2)}`
                      : `default strength ${l.default_strength.toFixed(2)}`}
                  </div>
                </button>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => void handleDelete(l.id)}
                  aria-label={`Delete ${l.name}`}
                  style={{
                    border: "1px solid var(--color-line)",
                    background: "transparent",
                    color: "var(--color-muted)",
                    borderRadius: 6,
                    fontSize: 11,
                    padding: "4px 8px",
                    cursor: disabled ? "not-allowed" : "pointer",
                  }}
                >
                  Delete
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {selected && (
        <label
          style={{
            display: "block",
            marginBottom: 12,
            fontSize: 12,
            color: "var(--color-muted)",
          }}
        >
          Strength · {strength.toFixed(2)}
          <input
            type="range"
            min={0}
            max={1.5}
            step={0.05}
            value={strength}
            disabled={disabled}
            onChange={(e) => onStrengthChange(Number(e.target.value))}
            style={{ display: "block", width: "100%", marginTop: 6 }}
          />
        </label>
      )}

      <div
        style={{
          display: "grid",
          gap: 8,
          padding: 12,
          borderRadius: 11,
          border: "1px dashed var(--color-line2)",
          background: "#101018",
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-muted2)" }}>
          Upload trained LoRA
        </div>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name (e.g. Creator A)"
          disabled={disabled || uploading}
          style={fieldStyle}
        />
        <input
          value={trigger}
          onChange={(e) => setTrigger(e.target.value)}
          placeholder="Trigger word (optional)"
          disabled={disabled || uploading}
          style={fieldStyle}
        />
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            disabled={disabled || uploading}
            onClick={() => fileRef.current?.click()}
            style={btnStyle}
          >
            {uploading ? "Uploading…" : "Choose .safetensors"}
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => void handleTrainStub()}
            style={{ ...btnStyle, opacity: 0.85 }}
          >
            Train LoRA…
          </button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".safetensors,application/octet-stream"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (f) void handleUpload(f);
          }}
        />
        {trainMsg && (
          <p style={{ margin: 0, fontSize: 11, color: "var(--color-muted)", lineHeight: 1.4 }}>
            {trainMsg}
          </p>
        )}
      </div>

      {error && (
        <div
          style={{
            marginTop: 10,
            padding: "8px 10px",
            borderRadius: 8,
            background: "#2a0e0e",
            border: "1px solid #5a1a1a",
            fontSize: 12,
            color: "var(--color-red)",
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}

const fieldStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  borderRadius: 8,
  border: "1px solid var(--color-line)",
  background: "var(--color-panel2)",
  color: "var(--color-text)",
  padding: "8px 10px",
  fontSize: 12,
  outline: "none",
  fontFamily: "inherit",
};

const btnStyle: CSSProperties = {
  border: "1px solid #2c2748",
  background: "#15101f",
  color: "var(--color-violet-l)",
  borderRadius: 8,
  padding: "7px 12px",
  fontSize: 12,
  fontWeight: 600,
  cursor: "pointer",
};
