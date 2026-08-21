"use client";
import { generatePackLabel } from "@/lib/variantStepperCopy";

interface GenerateButtonProps {
  fileCount: number;
  perVideo: number;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  jobId?: string | null;
  complete?: boolean;
}

export function GenerateButton({
  fileCount,
  perVideo,
  onClick,
  disabled,
  busy,
  jobId,
  complete,
}: GenerateButtonProps) {
  const isDisabled = disabled || busy || fileCount === 0;

  return (
    <button
      onClick={onClick}
      disabled={isDisabled}
      style={{
        flex: 1,
        border: "none",
        borderRadius: 11,
        color: "#fff",
        fontSize: 15,
        fontWeight: 800,
        cursor: isDisabled ? "not-allowed" : "pointer",
        background: isDisabled
          ? "#2a2a3a"
          : "linear-gradient(135deg,var(--color-violet),var(--color-pink))",
        boxShadow: isDisabled
          ? "none"
          : "0 6px 22px #ff4d8d33, 0 2px 10px #7c5cff44",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 2,
        minHeight: 72,
        opacity: isDisabled ? 0.5 : 1,
        transition: "opacity 0.15s, background 0.15s, box-shadow 0.15s",
      }}
    >
      {busy ? "Generating…" : jobId ? (complete ? "New run first" : "Generating…") : "Generate"}
      <small style={{ fontSize: 10.5, fontWeight: 600, opacity: 0.85 }}>
        {busy || (jobId && !complete)
          ? "in progress — Cancel on the live run if this was a mistake"
          : jobId && complete
            ? "New run clears this pack"
            : generatePackLabel(fileCount, perVideo)}
      </small>
    </button>
  );
}
