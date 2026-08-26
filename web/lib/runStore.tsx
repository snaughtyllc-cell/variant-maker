"use client";
import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import { CreateJobResponse, SourceOut } from "./types";
import { getJob } from "./api";
import { useJobProgress } from "./useJobProgress";
import { RunProgress } from "./progress";
import { QualityMode } from "./hqWaitCopy";

type RunSource = { source_id: string; filename: string; requested: number };

const QUALITY_KEY = "vm.quality";

function readStoredQuality(): QualityMode {
  return "fast";
}

interface RunCtx {
  jobId: string | null;
  sources: RunSource[];
  progress: RunProgress;
  complete: boolean;
  qualityMode: QualityMode;
  start: (resp: CreateJobResponse, qualityMode?: QualityMode) => void;
  clear: () => void;
}

const Ctx = createContext<RunCtx | null>(null);

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [sources, setSources] = useState<RunSource[]>([]);
  const [qualityMode, setQualityMode] = useState<QualityMode>("fast");
  const hydratedRef = useRef(false);

  // Hydrate jobId from sessionStorage on mount; if sources are empty, fetch job detail once
  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    const saved = sessionStorage.getItem("vm.job");
    if (!saved) return;
    setJobId(saved);
    setQualityMode(readStoredQuality());
    // sources will be empty after a hard reload — fetch once to seed them
    getJob(saved)
      .then((detail) => {
        setSources(
          detail.sources.map((s: SourceOut) => ({
            source_id: s.source_id,
            filename: s.filename,
            requested: s.requested,
          }))
        );
      })
      .catch(() => {
        // 404 or old/cleared job — full reset via clear()
        sessionStorage.removeItem("vm.job");
        sessionStorage.removeItem(QUALITY_KEY);
        setJobId(null);
        setSources([]);
        setQualityMode("fast");
      });
  }, []);

  const progress = useJobProgress(jobId, sources);
  const complete = progress.complete;

  function start(resp: CreateJobResponse, _qualityMode: QualityMode = "fast") {
    const id = resp.job_id;
    const srcs: RunSource[] = resp.sources.map((s) => ({
      source_id: s.source_id,
      filename: s.filename,
      requested: s.requested,
    }));
    sessionStorage.setItem("vm.job", id);
    sessionStorage.setItem(QUALITY_KEY, "fast");
    setSources(srcs);
    setJobId(id);
    setQualityMode("fast");
  }

  function clear() {
    sessionStorage.removeItem("vm.job");
    sessionStorage.removeItem(QUALITY_KEY);
    setJobId(null);
    setSources([]);
    setQualityMode("fast");
  }

  return (
    <Ctx.Provider value={{ jobId, sources, progress, complete, qualityMode, start, clear }}>
      {children}
    </Ctx.Provider>
  );
}

export function useRun(): RunCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useRun() must be used inside <RunProvider>");
  return ctx;
}
