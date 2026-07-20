"use client";
import { useEffect, useState } from "react";

interface FaceRefListProps {
  files: File[];
  onRemove: (index: number) => void;
}

export function FaceRefList({ files, onRemove }: FaceRefListProps) {
  if (files.length === 0) return null;

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 10,
        marginTop: 12,
      }}
    >
      {files.map((f, i) => (
        <FaceThumb key={`${f.name}-${f.size}-${i}`} file={f} onRemove={() => onRemove(i)} />
      ))}
    </div>
  );
}

function FaceThumb({ file, onRemove }: { file: File; onRemove: () => void }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  return (
    <div
      style={{
        position: "relative",
        width: 72,
        height: 72,
        borderRadius: 10,
        overflow: "hidden",
        border: "1px solid var(--color-line2)",
        background: "#14141d",
        flex: "none",
      }}
    >
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt={file.name}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : null}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        aria-label={`Remove ${file.name}`}
        style={{
          position: "absolute",
          top: 4,
          right: 4,
          width: 20,
          height: 20,
          borderRadius: 6,
          border: "1px solid #3a3a4a",
          background: "#0c0c12cc",
          color: "var(--color-text)",
          fontSize: 12,
          lineHeight: 1,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 0,
        }}
      >
        ×
      </button>
    </div>
  );
}
