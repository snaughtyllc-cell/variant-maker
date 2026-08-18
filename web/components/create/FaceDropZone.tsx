"use client";
import { useRef, useState, DragEvent } from "react";
import { CREATE_FACE_REF_MAX } from "@/lib/createTypes";

const IMAGE_RE = /\.(jpe?g|png|webp)$/i;

function acceptsImage(f: File): boolean {
  if (f.type.startsWith("image/")) return true;
  return IMAGE_RE.test(f.name);
}

interface FaceDropZoneProps {
  onFiles: (files: File[]) => void;
  currentCount: number;
}

export function FaceDropZone({ onFiles, currentCount }: FaceDropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const remaining = Math.max(0, CREATE_FACE_REF_MAX - currentCount);
  const full = remaining === 0;

  function filter(files: FileList | null): File[] {
    return Array.from(files ?? [])
      .filter(acceptsImage)
      .slice(0, remaining);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    if (full) return;
    const files = filter(e.dataTransfer.files);
    if (files.length) onFiles(files);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (!full) setDragging(true);
  }

  function handleDragLeave() {
    setDragging(false);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = filter(e.target.files);
    if (files.length) onFiles(files);
    e.target.value = "";
  }

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      style={{
        border: `1.6px dashed ${dragging ? "var(--color-violet)" : "var(--color-line2)"}`,
        borderRadius: "14px",
        padding: "26px 18px",
        textAlign: "center",
        background: dragging
          ? "radial-gradient(120% 120% at 50% 0%, #1a1430, #0e0e15)"
          : "radial-gradient(120% 120% at 50% 0%, #14141e, #0e0e15)",
        transition: "border-color 0.15s, background 0.15s",
        cursor: full ? "not-allowed" : "pointer",
        opacity: full ? 0.55 : 1,
      }}
      onClick={() => {
        if (!full) inputRef.current?.click();
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          margin: "0 auto 10px",
          background: "linear-gradient(135deg,#1c1430,#241a44)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 20,
          border: "1px solid #2e2350",
        }}
      >
        ◈
      </div>
      <b style={{ fontSize: 14 }}>
        {full ? "Face ref limit reached" : "Drop face ref(s) here"}
      </b>
      <span
        style={{
          display: "block",
          fontSize: 12,
          color: "var(--color-muted)",
          marginTop: 4,
        }}
      >
        JPG / PNG / WebP — up to {CREATE_FACE_REF_MAX} creator photos
        {currentCount > 0 ? ` · ${remaining} left` : ""}
      </span>
      {!full && (
        <div
          style={{
            marginTop: 12,
            display: "inline-block",
            fontSize: 12,
            color: "var(--color-violet-l)",
            border: "1px solid #2c2748",
            padding: "6px 12px",
            borderRadius: 8,
            background: "#15101f",
          }}
        >
          or browse files
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/*"
        multiple
        style={{ display: "none" }}
        onChange={handleChange}
      />
    </div>
  );
}
