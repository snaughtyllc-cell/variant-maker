"use client";
import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import { getCreateJob } from "./createApi";
import { CreateRunProgress } from "./createProgress";
import { CreateJobResponse } from "./createTypes";
import { useCreateProgress } from "./useCreateProgress";

const STORAGE_KEY = "vm.create.job";

interface CreateCtx {
  jobId: string | null;
  count: number;
  brief: string;
  progress: CreateRunProgress;
  complete: boolean;
  start: (resp: CreateJobResponse) => void;
  clear: () => void;
}

const Ctx = createContext<CreateCtx | null>(null);

export function CreateProvider({ children }: { children: React.ReactNode }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const [brief, setBrief] = useState("");
  const hydratedRef = useRef(false);

  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    setJobId(saved);
    getCreateJob(saved)
      .then((detail) => {
        setCount(detail.count);
        setBrief(detail.brief);
      })
      .catch(() => {
        sessionStorage.removeItem(STORAGE_KEY);
        setJobId(null);
        setCount(0);
        setBrief("");
      });
  }, []);

  const progress = useCreateProgress(jobId, count);
  const complete = progress.complete;

  function start(resp: CreateJobResponse) {
    sessionStorage.setItem(STORAGE_KEY, resp.job_id);
    setBrief(resp.brief);
    setCount(resp.count);
    setJobId(resp.job_id);
  }

  function clear() {
    sessionStorage.removeItem(STORAGE_KEY);
    setJobId(null);
    setCount(0);
    setBrief("");
  }

  return (
    <Ctx.Provider value={{ jobId, count, brief, progress, complete, start, clear }}>
      {children}
    </Ctx.Provider>
  );
}

export function useCreateRun(): CreateCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCreateRun() must be used inside <CreateProvider>");
  return ctx;
}
