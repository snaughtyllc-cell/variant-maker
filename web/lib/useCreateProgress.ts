"use client";
import { useEffect, useRef, useState } from "react";
import { createEventsUrl, getCreateJob } from "./createApi";
import {
  applyCreateJobDetail,
  CreateRunProgress,
  initCreateRun,
  reduceCreateEvent,
} from "./createProgress";
import { CreateEvent } from "./createTypes";

/**
 * Own progress hook for Create jobs — do not share with Spoof useJobProgress.
 * SSE when available; 1s poll fallback (RunPod proxies often buffer SSE).
 */
export function useCreateProgress(
  jobId: string | null,
  count: number,
): CreateRunProgress {
  const [run, setRun] = useState<CreateRunProgress>(() => initCreateRun(count));
  const runRef = useRef(run);
  runRef.current = run;

  useEffect(() => {
    if (!jobId || count < 1) return;
    const fresh = initCreateRun(count);
    runRef.current = fresh;
    setRun(fresh);

    const es = new EventSource(createEventsUrl(jobId));
    es.onmessage = (e) => {
      let ev: CreateEvent;
      try {
        ev = JSON.parse(e.data) as CreateEvent;
      } catch {
        return;
      }
      // Fill file_url / handoff_url for still-done if server only sent filenames
      if ((ev.state === "still-done" || (ev.state === "done" && ev.filename)) && ev.filename) {
        const handoff =
          ev.handoff_filename ||
          (ev.filename.endsWith(".png")
            ? ev.filename.replace(/\.png$/i, ".mp4")
            : `${ev.filename}.mp4`);
        ev = {
          ...ev,
          file_url: ev.file_url || `/api/create/jobs/${jobId}/files/${ev.filename}`,
          handoff_filename: handoff,
          handoff_url: ev.handoff_url || `/api/create/jobs/${jobId}/files/${handoff}`,
        };
      }
      const next = reduceCreateEvent(runRef.current, ev);
      runRef.current = next;
      setRun(next);
      if (ev.state === "job-done" || ev.state === "failed" || ev.state === "error") es.close();
    };

    let cancelled = false;
    const poll = async () => {
      try {
        const detail = await getCreateJob(jobId);
        if (cancelled) return;
        const next = applyCreateJobDetail(runRef.current, detail);
        runRef.current = next;
        setRun(next);
        if (detail.state === "done" || detail.state === "failed" || detail.phase === "failed" || detail.error) es.close();
      } catch {
        // ignore transient proxy errors
      }
    };
    poll();
    const pollId = setInterval(poll, 1000);

    return () => {
      cancelled = true;
      clearInterval(pollId);
      es.close();
    };
  }, [jobId, count]);

  return run;
}
