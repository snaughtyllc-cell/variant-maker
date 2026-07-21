import { describe, expect, it } from "vitest";
import * as createApi from "@/lib/createApi";
import {
  applyCreateJobDetail,
  initCreateRun,
  reduceCreateEvent,
} from "@/lib/createProgress";
import { CreateJobDetail } from "@/lib/createTypes";

describe("createApi helpers", () => {
  it("builds still and events URLs against /files/", () => {
    expect(createApi.createStillUrl("c1", "still_01.png")).toBe(
      "/api/create/jobs/c1/files/still_01.png",
    );
    expect(createApi.createEventsUrl("c1")).toBe("/api/create/jobs/c1/events");
  });

  it("createCreateJob FormData includes lora fields when set", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    const orig = globalThis.fetch;
    globalThis.fetch = (async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(url), init });
      return new Response(
        JSON.stringify({
          job_id: "j1",
          state: "running",
          brief: "x",
          aspect: "9:16",
          count: 1,
          created_utc: "2026-07-21T00:00:00Z",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      );
    }) as typeof fetch;
    try {
      const face = new File([new Uint8Array([1, 2])], "face.jpg", {
        type: "image/jpeg",
      });
      await createApi.createCreateJob({
        brief: "mirror",
        aspect: "9:16",
        count: 1,
        faceRefs: [face],
        loraId: "lora123",
        loraStrength: 0.85,
      });
      expect(calls).toHaveLength(1);
      const fd = calls[0].init?.body as FormData;
      expect(fd.get("lora_id")).toBe("lora123");
      expect(fd.get("lora_strength")).toBe("0.85");
      expect(fd.getAll("face_refs")).toHaveLength(1);
    } finally {
      globalThis.fetch = orig;
    }
  });
});

describe("createProgress reducer", () => {
  it("tracks phases and stills idempotently (backend event vocab)", () => {
    let run = initCreateRun(2);
    run = reduceCreateEvent(run, { state: "expanding" });
    expect(run.phase).toBe("directing");

    run = reduceCreateEvent(run, {
      state: "done",
      index: 1,
      filename: "still_01.png",
      file_url: "/api/create/jobs/c1/files/still_01.png",
      status: "ok",
    });
    expect(run.stills).toHaveLength(1);
    expect(run.phase).toBe("generating");

    // idempotent upsert
    run = reduceCreateEvent(run, {
      state: "done",
      index: 1,
      filename: "still_01.png",
      file_url: "/api/create/jobs/c1/files/still_01.png",
      status: "ok",
    });
    expect(run.stills).toHaveLength(1);

    run = reduceCreateEvent(run, { state: "job-done" });
    expect(run.phase).toBe("done");
    expect(run.complete).toBe(true);
  });

  it("applyCreateJobDetail merges poll payload", () => {
    const detail: CreateJobDetail = {
      job_id: "c1",
      brief: "mirror selfie",
      aspect: "9:16",
      count: 1,
      created_utc: "2026-07-20T00:00:00Z",
      state: "done",
      phase: "done",
      message: null,
      stills: [
        {
          index: 1,
          filename: "still_01.png",
          handoff_filename: "still_01.mp4",
          file_url: "/api/create/jobs/c1/files/still_01.png",
          handoff_url: "/api/create/jobs/c1/files/still_01.mp4",
          status: "ok",
        },
      ],
      error: null,
    };
    const run = applyCreateJobDetail(initCreateRun(1), detail);
    expect(run.complete).toBe(true);
    expect(run.stills).toHaveLength(1);
    expect(run.phase).toBe("done");
  });

  it("maps error events to failed", () => {
    const run = reduceCreateEvent(initCreateRun(1), {
      state: "error",
      error: "comfy down",
    });
    expect(run.failed).toBe(true);
    expect(run.phase).toBe("failed");
    expect(run.error).toBe("comfy down");
  });

  it("job-done after error keeps failed (does not treat as success)", () => {
    let run = reduceCreateEvent(initCreateRun(1), {
      state: "error",
      error: "director timeout",
    });
    run = reduceCreateEvent(run, { state: "job-done" });
    expect(run.complete).toBe(true);
    expect(run.failed).toBe(true);
    expect(run.phase).toBe("failed");
    expect(run.error).toBe("director timeout");
  });

  it("applyCreateJobDetail treats state/phase failed + error", () => {
    const detail: CreateJobDetail = {
      job_id: "c2",
      brief: "broken",
      aspect: "9:16",
      count: 1,
      created_utc: "2026-07-20T00:00:00Z",
      state: "failed",
      phase: "failed",
      message: null,
      stills: [],
      error: "PROMPT_LLM_API_KEY missing",
    };
    const run = applyCreateJobDetail(initCreateRun(1), detail);
    expect(run.failed).toBe(true);
    expect(run.complete).toBe(true);
    expect(run.phase).toBe("failed");
    expect(run.error).toContain("PROMPT_LLM");
  });
});

describe("spoofHandoff queue", () => {
  it("round-trips pending handoff via sessionStorage", async () => {
    const { queueSpoofHandoff, consumeSpoofHandoff } = await import(
      "@/lib/spoofHandoff"
    );
    queueSpoofHandoff({
      url: "/api/create/jobs/c1/files/still_01.mp4",
      filename: "still_01.mp4",
    });
    expect(consumeSpoofHandoff()).toEqual({
      url: "/api/create/jobs/c1/files/still_01.mp4",
      filename: "still_01.mp4",
    });
    expect(consumeSpoofHandoff()).toBeNull();
  });
});
