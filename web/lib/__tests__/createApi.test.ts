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
});
