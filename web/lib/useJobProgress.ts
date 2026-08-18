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
        uniqueness_status: v.uniqueness_status ?? null,
        uniqueness_target: v.uniqueness_target ?? null,
        escalated: v.escalated ?? false,
        platform_result: v.platform_result ?? null,
      };
      next = reduceEvent(next, ev);
    }
    // Mid-flight state rides on JobDetail so RunPod-buffered SSE is not required.
    if (s.in_flight) {
      next = reduceEvent(next, {
        source_id: s.source_id,
        index: s.in_flight.index,
        state: s.in_flight.state,
        attempt: s.in_flight.attempt,
        max_attempts: s.in_flight.max_attempts,
        status: null,
        quality: null,
        filename: null,
      });
    } else {
      const prev = next.bySource[s.source_id];
      if (prev?.inFlight) {
        next = {
          ...next,
          bySource: {
            ...next.bySource,
            [s.source_id]: { ...prev, inFlight: undefined },
          },
        };
      }
    }
  }
  if (detail.state === "done") {
    const cleared: RunProgress = {
      ...next,
      complete: true,
      failed: detail.error || next.failed || null,
      bySource: Object.fromEntries(
        Object.entries(next.bySource).map(([id, s]) => [id, { ...s, inFlight: undefined }]),
      ),
    };
    next = reduceEvent(cleared, { state: "job-done" });
  }
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
    if (!jobId || sources.length === 0) return;
    const fresh = initRun(sources);
    runRef.current = fresh;
    setRun(fresh);

    // SSE still helps locally; RunPod's HTTP proxy often buffers it forever.
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

    let cancelled = false;
    const poll = async () => {
      try {
        const detail = await getJob(jobId);
        if (cancelled) return;
        const next = applyJobDetail(runRef.current, detail);
        runRef.current = next;
        setRun(next);
        if (detail.state === "done") es.close();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "";
        if (msg.startsWith("404")) {
          const next: RunProgress = {
            ...runRef.current,
            complete: true,
            failed: "This run is gone (Studio restarted or the job never saved). Generate again.",
          };
          runRef.current = next;
          setRun(next);
          es.close();
        }
      }
    };
    poll();
    const pollId = setInterval(poll, 1000);

    return () => {
      cancelled = true;
      clearInterval(pollId);
      es.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, sourcesKey]);
  return run;
}
