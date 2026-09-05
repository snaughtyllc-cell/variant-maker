"use client";
import { useEffect, useState } from "react";
import { captureVideoPoster } from "@/lib/videoPoster";

export function SourceThumb({
  file,
  src,
  label,
}: {
  file?: File;
  src?: string;
  label?: string;
}) {
  const [poster, setPoster] = useState("");
  const thumbLabel = label ? `${label} thumbnail` : "Source thumbnail";

  useEffect(() => {
    if (!file) {
      setPoster("");
      return;
    }
    let cancelled = false;
    captureVideoPoster(file)
      .then((dataUrl) => {
        if (!cancelled) setPoster(dataUrl);
      })
      .catch(() => {
        if (cancelled) return;
        return captureVideoPoster(file).then((dataUrl) => {
          if (!cancelled) setPoster(dataUrl);
        });
      })
      .catch(() => {
        /* leave the striped placeholder — a blob <video> stays black on iOS */
      });
    return () => {
      cancelled = true;
    };
  }, [file]);

  return (
    <div className="studio-source-thumb">
      {poster ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={poster} alt={thumbLabel} />
      ) : src && !file ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={thumbLabel} />
      ) : (
        <div
          className="studio-source-thumb__ph"
          role={file ? undefined : "img"}
          aria-label={file ? undefined : thumbLabel}
          aria-hidden={file ? true : undefined}
        >
          {file ? "" : label || ""}
        </div>
      )}
    </div>
  );
}
