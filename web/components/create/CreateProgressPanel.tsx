"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ProgressBar } from "@/components/common/ProgressBar";
import { Badge } from "@/components/common/Badge";
import { useCreateRun } from "@/lib/createStore";
import { phaseLabel } from "@/lib/createProgress";
import { spoofCreateHandoff } from "@/lib/spoofHandoff";

export function CreateProgressPanel() {
  const { jobId, brief, progress, complete } = useCreateRun();
  const router = useRouter();
  const [spoofBusy, setSpoofBusy] = useState<number | null>(null);
  const [spoofErr, setSpoofErr] = useState<string | null>(null);

  if (!jobId) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 10,
          padding: "0 32px",
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            background: "linear-gradient(135deg, #1c1430, #241a44)",
            border: "1px solid #2e2350",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 20,
            marginBottom: 4,
          }}
        >
          ✦
        </div>
        <p
          style={{
            fontSize: 14,
            fontWeight: 700,
            color: "var(--color-text)",
            margin: 0,
          }}
        >
          No create run yet
        </p>
        <p
          style={{
            fontSize: 12,
            color: "var(--color-muted2)",
            margin: 0,
            lineHeight: 1.5,
            maxWidth: 220,
          }}
        >
          Add a brief + face refs and hit Generate — progress shows here
        </p>
      </div>
    );
  }

  const done = progress.stills.length;
  const total = progress.stillsTotal || 1;
  const ratio = Math.min(1, done / total);
  const failed =
    progress.failed ||
    progress.phase === "failed" ||
    !!progress.error;
  const errorMessage =
    progress.error ||
    (failed ? "Create job failed — check Comfy / Prompt LLM env and try again." : null);

  async function handleSpoof(index: number, handoffUrl: string, handoffFilename: string) {
    if (spoofBusy != null) return;
    setSpoofErr(null);
    setSpoofBusy(index);
    try {
      await spoofCreateHandoff({ handoffUrl, handoffFilename });
      router.push("/");
    } catch (e) {
      setSpoofErr(e instanceof Error ? e.message : "Spoof handoff failed");
    } finally {
      setSpoofBusy(null);
    }
  }

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 14,
          flexShrink: 0,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)" }}>
            {failed ? "Failed" : complete ? "Complete" : phaseLabel(progress.phase)}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--color-muted)", marginTop: 2 }}>
            {failed
              ? "Generation stopped — fix the issue below and retry"
              : progress.message ||
                (complete
                  ? "Stills ready — Spoof this or open Gallery"
                  : "Live status updates every second")}
          </div>
        </div>

        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 10px",
            borderRadius: 999,
            background: "#14141d",
            border: "1px solid var(--color-line)",
            fontSize: 11.5,
            color: "var(--color-muted)",
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: failed
                ? "var(--color-red)"
                : complete
                  ? "var(--color-green)"
                  : "var(--color-cyan)",
              boxShadow: failed
                ? "0 0 8px #f8717188"
                : complete
                  ? "0 0 8px #22c55e88"
                  : "0 0 8px #22d3ee99",
              display: "inline-block",
              flexShrink: 0,
            }}
          />
          {failed ? "failed" : complete ? "done" : "live"}
        </span>
      </div>

      {failed && errorMessage && (
        <div
          role="alert"
          style={{
            marginBottom: 13,
            padding: "12px 14px",
            borderRadius: 11,
            background: "#2a0e0e",
            border: "1px solid #5a1a1a",
            color: "#fca5a5",
            fontSize: 13,
            lineHeight: 1.45,
            fontWeight: 600,
          }}
        >
          {errorMessage}
        </div>
      )}

      <div
        style={{
          background: "var(--color-panel)",
          border: `1px solid ${!complete && !failed ? "#2f2a52" : failed ? "#5a1a1a" : "var(--color-line)"}`,
          borderRadius: 13,
          padding: 14,
          marginBottom: 13,
          boxShadow:
            !complete && !failed ? "0 0 0 1px #7c5cff22, 0 8px 26px #00000040" : "none",
        }}
      >
        {brief && (
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--color-text)",
              marginBottom: 10,
              lineHeight: 1.4,
            }}
          >
            {brief}
          </div>
        )}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 8,
          }}
        >
          <span style={{ fontSize: 11.5, color: "var(--color-muted)" }}>
            {done} / {total} stills
          </span>
          <span style={{ fontSize: 13, fontWeight: 800 }}>
            <span style={{ color: "var(--color-violet-l)" }}>{done}</span>
            <span style={{ color: "var(--color-muted)", fontWeight: 600 }}> / {total}</span>
          </span>
        </div>

        <ProgressBar value={failed ? 0 : ratio} />

        {progress.stills.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 8,
              marginTop: 14,
            }}
          >
            {progress.stills.map((s) => (
              <div
                key={s.index}
                style={{
                  aspectRatio: "9 / 16",
                  borderRadius: 8,
                  overflow: "hidden",
                  background: "#14141d",
                  border: "1px solid var(--color-line2)",
                  position: "relative",
                }}
              >
                {s.file_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={s.file_url}
                    alt={s.filename}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                ) : null}
                <div style={{ position: "absolute", top: 4, left: 4 }}>
                  <Badge color={s.status === "ok" ? "green" : "red"}>
                    {String(s.index).padStart(2, "0")}
                  </Badge>
                </div>
                {complete && !failed && s.status === "ok" && s.handoff_url && (
                  <button
                    type="button"
                    onClick={() =>
                      handleSpoof(
                        s.index,
                        s.handoff_url,
                        s.handoff_filename || `still_${String(s.index).padStart(2, "0")}.mp4`,
                      )
                    }
                    disabled={spoofBusy != null}
                    style={{
                      position: "absolute",
                      left: 4,
                      right: 4,
                      bottom: 4,
                      fontSize: 10,
                      fontWeight: 700,
                      padding: "5px 4px",
                      borderRadius: 6,
                      border: "none",
                      color: "#fff",
                      cursor: spoofBusy != null ? "not-allowed" : "pointer",
                      background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
                      opacity: spoofBusy != null && spoofBusy !== s.index ? 0.55 : 1,
                    }}
                  >
                    {spoofBusy === s.index ? "…" : "Spoof"}
                  </button>
                )}
              </div>
            ))}

            {!complete && !failed && done < total && (
              <div
                style={{
                  aspectRatio: "9 / 16",
                  borderRadius: 8,
                  background: "#14141d",
                  border: "1px dashed var(--color-line2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <span style={{ fontSize: 10, color: "var(--color-muted2)" }}>
                  {progress.phase === "directing" ? "direct" : "gen…"}
                </span>
              </div>
            )}
          </div>
        )}

        {spoofErr && (
          <div style={{ marginTop: 10, fontSize: 12, color: "var(--color-red)" }}>
            {spoofErr}
          </div>
        )}
      </div>

      {complete && !failed && (
        <Link
          href="/gallery"
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "10px 14px",
            borderRadius: 10,
            background: "#15101f",
            border: "1px solid #2c2748",
            color: "var(--color-violet-l)",
            fontSize: 13,
            fontWeight: 700,
            textDecoration: "none",
            alignSelf: "flex-start",
          }}
        >
          Open Gallery →
        </Link>
      )}
    </div>
  );
}
