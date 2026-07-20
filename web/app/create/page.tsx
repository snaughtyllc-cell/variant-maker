"use client";
import { useCallback, useState } from "react";
import { FaceDropZone } from "@/components/create/FaceDropZone";
import { FaceRefList } from "@/components/create/FaceRefList";
import { AspectPicker } from "@/components/create/AspectPicker";
import { CountStepper } from "@/components/create/CountStepper";
import { CreateGenerateButton } from "@/components/create/CreateGenerateButton";
import { CreateProgressPanel } from "@/components/create/CreateProgressPanel";
import { createCreateJob } from "@/lib/createApi";
import { useCreateRun } from "@/lib/createStore";
import {
  CREATE_FACE_REF_MAX,
  CreateAspect,
} from "@/lib/createTypes";

export default function CreatePage() {
  const { start, jobId, complete, progress } = useCreateRun();
  const [brief, setBrief] = useState("");
  const [faceRefs, setFaceRefs] = useState<File[]>([]);
  const [aspect, setAspect] = useState<CreateAspect>("9:16");
  const [count, setCount] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const failed =
    progress.failed || progress.phase === "failed" || !!progress.error;
  // Don't treat failed jobs as "still running" just because state was once done.
  const runActive = !!jobId && !complete && !failed;
  const briefOk = brief.trim().length >= 3;

  const handleFaces = useCallback((incoming: File[]) => {
    setFaceRefs((prev) => {
      const room = CREATE_FACE_REF_MAX - prev.length;
      if (room <= 0) return prev;
      return [...prev, ...incoming.slice(0, room)];
    });
  }, []);

  function handleRemove(index: number) {
    setFaceRefs((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleGenerate() {
    if (busy || runActive || !briefOk || faceRefs.length === 0) return;
    setError(null);
    setBusy(true);
    try {
      const resp = await createCreateJob({
        brief: brief.trim(),
        aspect,
        count,
        faceRefs,
      });
      start(resp);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create job failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      style={{
        display: "grid",
        gridTemplateColumns: "0.95fr 1.05fr",
        minHeight: "calc(100vh - 49px)",
        background: "var(--color-bg)",
      }}
    >
      {/* LEFT — cockpit */}
      <div
        style={{
          padding: "22px",
          borderRight: "1px solid var(--color-line)",
        }}
      >
        <p
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: ".7px",
            color: "var(--color-muted2)",
            margin: "0 0 8px",
            fontWeight: 700,
          }}
        >
          1 · Brief
        </p>
        <textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="creator in hotel bathroom mirror selfie, soft flash, phone vertical"
          rows={3}
          disabled={runActive}
          style={{
            width: "100%",
            boxSizing: "border-box",
            resize: "vertical",
            minHeight: 84,
            borderRadius: 11,
            border: "1px solid var(--color-line)",
            background: "var(--color-panel2)",
            color: "var(--color-text)",
            padding: "12px 14px",
            fontSize: 13,
            lineHeight: 1.45,
            outline: "none",
            fontFamily: "inherit",
          }}
        />

        <p
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: ".7px",
            color: "var(--color-muted2)",
            margin: "20px 0 8px",
            fontWeight: 700,
          }}
        >
          2 · Face refs
        </p>
        <FaceDropZone onFiles={handleFaces} currentCount={faceRefs.length} />
        <FaceRefList files={faceRefs} onRemove={handleRemove} />

        <div style={{ marginTop: 20 }}>
          <AspectPicker value={aspect} onChange={setAspect} disabled={runActive} />
        </div>

        <div
          style={{
            display: "flex",
            gap: 12,
            alignItems: "stretch",
            marginTop: 12,
          }}
        >
          <CountStepper value={count} onChange={setCount} disabled={runActive} />
          <CreateGenerateButton
            faceCount={faceRefs.length}
            stillCount={count}
            briefOk={briefOk}
            onClick={handleGenerate}
            disabled={runActive}
            busy={busy}
          />
        </div>

        {error && (
          <div
            style={{
              marginTop: 12,
              padding: "8px 12px",
              background: "#2a0e0e",
              border: "1px solid #5a1a1a",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--color-red)",
            }}
          >
            {error}
          </div>
        )}
      </div>

      {/* RIGHT — live progress */}
      <div
        style={{
          padding: "18px 20px",
          background: "#0c0c11",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
        <CreateProgressPanel />
      </div>
    </main>
  );
}
