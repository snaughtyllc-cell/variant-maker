"use client";

import { useRef, useState, DragEvent } from "react";
import { Upload } from "lucide-react";
import { dropZoneBrowse, dropZoneHint, dropZoneSubcopy, dropZoneTitle } from "@/lib/dropZoneCopy";
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

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const files = filter(event.dataTransfer.files);
    if (files.length) onFiles(files);
  }

  return (
    <div
      className="studio-drop-zone"
      data-dragging={dragging}
      onDrop={handleDrop}
      onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}
    >
      <span className="studio-drop-zone__icon"><Upload size={21} strokeWidth={1.8} /></span>
      <strong>{dropZoneTitle()}</strong>
      <span className="studio-drop-zone__copy">{dropZoneSubcopy()}</span>
      <span className="studio-drop-zone__hint">{dropZoneHint()}</span>
      <span className="studio-drop-zone__browse">{dropZoneBrowse()}</span>
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        multiple
        style={{ display: "none" }}
        onChange={(event) => {
          const files = filter(event.target.files);
          if (files.length) onFiles(files);
          event.target.value = "";
        }}
      />
    </div>
  );
}
