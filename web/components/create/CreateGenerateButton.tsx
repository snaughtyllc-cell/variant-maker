"use client";

interface CreateGenerateButtonProps {
  faceCount: number;
  stillCount: number;
  briefOk: boolean;
  identityOk: boolean;
  identityHint: string;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
}

export function CreateGenerateButton({
  faceCount,
  stillCount,
  briefOk,
  identityOk,
  identityHint,
  onClick,
  disabled,
  busy,
}: CreateGenerateButtonProps) {
  const isDisabled = disabled || busy || !identityOk || !briefOk;

  return (
    <button
      type="button"
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
      {busy ? "Generating…" : "Generate"}
      <small style={{ fontSize: 10.5, fontWeight: 600, opacity: 0.85 }}>
        {busy
          ? "in progress"
          : `${stillCount} still${stillCount !== 1 ? "s" : ""} · ${identityHint}${
              faceCount > 0 ? ` · ${faceCount} ref${faceCount !== 1 ? "s" : ""}` : ""
            }`}
      </small>
    </button>
  );
}
