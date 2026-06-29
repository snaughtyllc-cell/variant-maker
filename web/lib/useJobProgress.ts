"use client";
import { useEffect, useRef, useState } from "react";
import { eventsUrl } from "./api";
import { initRun, reduceEvent, RunProgress } from "./progress";

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
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, sourcesKey]);
  return run;
}
