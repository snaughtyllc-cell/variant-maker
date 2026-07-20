"use client";
import { useState, type MouseEvent } from "react";
import { useRouter } from "next/navigation";
import { CreateJobDetail, CreateStillOut } from "@/lib/createTypes";
import { spoofCreateHandoff } from "@/lib/spoofHandoff";

interface CreateStillGroupProps {
  job: CreateJobDetail;
}

export function CreateStillGroup({ job }: CreateStillGroupProps) {
  const stills = job.stills.filter((s) => s.status === "ok" && s.handoff_url);
  if (stills.length === 0) return null;

  const title = job.brief.trim() || `Create ${job.job_id}`;

  return (
    <div
      style={{
        background: "var(--color-panel)",
        border: "1px solid var(--color-line)",
        borderRadius: 14,
        marginBottom: 16,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 13,
          padding: "14px 16px",
          borderBottom: "1px solid var(--color-line)",
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: "var(--color-text)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {title}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--color-muted)", marginTop: 1 }}>
            Create · {job.aspect} · {stills.length} still
            {stills.length !== 1 ? "s" : ""} · ready for Spoof
          </div>
        </div>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 999,
            color: "#c7b8ff",
            background: "#1e1740",
            border: "1px solid #362a68",
            flexShrink: 0,
          }}
        >
          Create
        </span>
      </div>

      <div style={{ padding: 16 }}>
        <div className="grid grid-cols-3 min-[700px]:grid-cols-5 min-[1100px]:grid-cols-8 gap-2.5">
          {stills.map((still) => (
            <CreateStillCard key={still.index} still={still} />
          ))}
        </div>
      </div>
    </div>
  );
}

function CreateStillCard({ still }: { still: CreateStillOut }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSpoof(e: MouseEvent) {
    e.stopPropagation();
    if (busy || !still.handoff_url) return;
    setErr(null);
    setBusy(true);
    try {
      await spoofCreateHandoff({
        handoffUrl: still.handoff_url,
        handoffFilename: still.handoff_filename || `still_${String(still.index).padStart(2, "0")}.mp4`,
      });
      router.push("/");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Spoof handoff failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        aspectRatio: "9 / 16",
        borderRadius: 9,
        position: "relative",
        overflow: "hidden",
        border: "1px solid var(--color-line)",
        background: "#14141d",
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={still.file_url}
        alt={still.filename}
        style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
      />
      <span
        style={{
          position: "absolute",
          top: 5,
          left: 6,
          fontSize: 9,
          color: "#fff",
          opacity: 0.85,
          fontWeight: 700,
          textShadow: "0 1px 3px #000",
        }}
      >
        s{String(still.index).padStart(2, "0")}
      </span>
      <div
        style={{
          position: "absolute",
          inset: "auto 0 0 0",
          padding: 6,
          background: "linear-gradient(transparent, #000000cc)",
        }}
      >
        <button
          type="button"
          onClick={handleSpoof}
          disabled={busy}
          style={{
            width: "100%",
            fontSize: 11,
            fontWeight: 700,
            padding: "7px 8px",
            borderRadius: 8,
            border: "none",
            color: "#fff",
            cursor: busy ? "not-allowed" : "pointer",
            background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
            boxShadow: "0 4px 14px #ff4d8d33",
            opacity: busy ? 0.7 : 1,
          }}
        >
          {busy ? "Loading…" : "Spoof this"}
        </button>
        {err && (
          <div style={{ marginTop: 4, fontSize: 9, color: "#f87171", lineHeight: 1.3 }}>
            {err}
          </div>
        )}
      </div>
    </div>
  );
}
