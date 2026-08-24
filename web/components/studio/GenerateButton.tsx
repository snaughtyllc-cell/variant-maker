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
      className="studio-generate-button"
    >
      {busy ? "Generating…" : jobId ? (complete ? "New run first" : "Generating…") : "Generate"}
      <small>
        {busy || (jobId && !complete)
          ? "in progress — Cancel on the live run if this was a mistake"
          : jobId && complete
            ? "New run clears this pack"
            : generatePackLabel(fileCount, perVideo)}
      </small>
    </button>
  );
}
