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
  const inProgress = Boolean(busy || (jobId && !complete));
  const label = busy || (jobId && !complete)
    ? "Generating…"
    : complete
      ? "Generate another"
      : "Generate";
  const support = inProgress
    ? "in progress — Cancel on the live run if this was a mistake"
    : complete
      ? "Starts a new pack from the clips on this page"
      : generatePackLabel(fileCount, perVideo);

  return (
    <button
      onClick={onClick}
      disabled={isDisabled}
      className="studio-generate-button"
      data-complete={complete || undefined}
    >
      <span className="studio-generate-button__copy">
        <span className="studio-generate-button__title">{label}</span>
        <small>{support}</small>
      </span>
      <span className="studio-generate-button__arrow" aria-hidden="true">
        <span className="material-symbols-rounded" style={{ fontSize: 19 }}>arrow_forward</span>
      </span>
    </button>
  );
}
