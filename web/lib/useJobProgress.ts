"use client";
import { useEffect, useRef, useState } from "react";
import { eventsUrl, getJob } from "./api";
import { initRun, reduceEvent, RunProgress } from "./progress";
import { VariantEvent } from "./types";

function applyJobDetail(run: RunProgress, detail: Awaited<ReturnType<typeof getJob>>): RunProgress {
  let next = run;
  for (const s of detail.sources) {
    for (const v of s.variants) {
      const ev: VariantEvent = {
        source_id: s.source_id,
        index: v.index,
        state: "done",
        attempt: 0,
        max_attempts: 0,
        status: v.status,
        quality: v.quality,
        filename: v.filename,
        uniqueness: v.uniqueness ?? null,
        escalated: v.escalated ?? false,
        platform_result: v.platform_result ?? null,
      };
      next = reduceEvent(next, ev);
    }
  }
  if (detail.state === "done") next = reduceEvent(next, { state: "job-done" });
  return next;
}

export function useJobProgress(
  jobId: string | null,
  sources: { source_id: string; filename: string; requested: number }[],
): RunProgress {
  const [run, setRun] = useState<RunProgress>(() => initRun(sources));
  const runRef = useRef(run);
  runRef.current = run;
  const sourcesKey = sources.map((s) => s.source_id).join(",");
  useEffect(() => {
    if (!jobId || sources.length === 0) return; // wait for sources (fresh start: immediate; reload: after job detail seeds them)
    const fresh = initRun(sources);
    runRef.current = fresh;
    setRun(fresh);

    // Primary: SSE (works locally; often buffered behind RunPod's HTTP proxy).
    const es = new EventSource(eventsUrl(jobId));
    es.onmessage = (e) => {
      let ev: ReturnType<typeof JSON.parse>;
      try {
        ev = JSON.parse(e.data);
      } catch {
        return;
      }
      const next = reduceEvent(runRef.current, ev);
      runRef.current = next;
      setRun(next);
      if (ev.state === "job-done") es.close();
    };

    // Fallback: poll job detail every 2s so progress still moves when SSE is buffered.
    let cancelled = false;
    const poll = async () => {
      try {
        const detail = await getJob(jobId);
        if (cancelled) return;
        const next = applyJobDetail(runRef.current, detail);
        runRef.current = next;
        setRun(next);
        if (detail.state === "done") es.close();
      } catch {
        // ignore transient proxy errors
      }
    };
    poll();
    const pollId = setInterval(poll, 2000);

    return () => {
      cancelled = true;
      clearInterval(pollId);
      es.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, sourcesKey]);
  return run;
}
