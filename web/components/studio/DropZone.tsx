"use client";
import { useRef, useState, DragEvent } from "react";
import { dropZoneBrowse, dropZoneSubcopy, dropZoneTitle } from "@/lib/dropZoneCopy";
import { accepts } from "@/lib/files";

interface DropZoneProps {
  onFiles: (files: File[]) => void;
}

export function DropZone({ onFiles }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function filter(files: FileList | null): File[] {
    return Array.from(files ?? []).filter(accepts);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const files = filter(e.dataTransfer.files);
    if (files.length) onFiles(files);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(true);
  }

  function handleDragLeave() {
    setDragging(false);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = filter(e.target.files);
    if (files.length) onFiles(files);
    // reset so same file can be re-added
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
        cursor: "pointer",
      }}
      onClick={() => inputRef.current?.click()}
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
        ⬆
      </div>
      <b style={{ fontSize: 14 }}>{dropZoneTitle()}</b>
      <span
        style={{
          display: "block",
          fontSize: 12,
          color: "var(--color-muted)",
          marginTop: 4,
          lineHeight: 1.45,
          padding: "0 8px",
        }}
      >
        {dropZoneSubcopy()}
      </span>
      <div
        style={{
          marginTop: 12,
          display: "inline-block",
          fontSize: 13,
          fontWeight: 600,
          color: "var(--color-violet-l)",
          border: "1px solid #2c2748",
          padding: "10px 16px",
          borderRadius: 8,
          background: "#15101f",
        }}
      >
        {dropZoneBrowse()}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        multiple
        style={{ display: "none" }}
        onChange={handleChange}
      />
    </div>
  );
}
