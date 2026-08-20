import { describe, it, expect, vi, beforeEach } from "vitest";
import * as api from "@/lib/api";

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("url builders use relative /api", () => {
  it("variantUrl / sourceUrl / eventsUrl", () => {
    expect(api.variantUrl("s1", "v01.mp4")).toBe("/api/variants/s1/v01.mp4");
    expect(api.sourceUrl("s1")).toBe("/api/sources/s1/source");
    expect(api.eventsUrl("j1")).toBe("/api/jobs/j1/events");
  });
});

describe("getQueue", () => {
  it("GETs /api/queue", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ running: 0, fast: 0, hq: 0, jobs: [] }), { status: 200 }),
    );
    const out = await api.getQueue();
    expect(out.running).toBe(0);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/queue");
  });
});

describe("cancelJob", () => {
  it("POSTs /api/jobs/:id/cancel", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        job_id: "j1", count: 1, created_utc: "", state: "cancelled",
        error: "Cancelled — New run when you want another pack.",
        sources: [],
      }), { status: 200 }),
    );
    const out = await api.cancelJob("j1");
    expect(out.state).toBe("cancelled");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/jobs/j1/cancel");
    expect((init as RequestInit).method).toBe("POST");
  });
});

describe("createJob posts multipart with files + count", () => {
  it("sends FormData to /api/jobs", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ job_id: "j1", sources: [] }), { status: 201 }));
    const f = new File([new Uint8Array([1, 2])], "a.mp4", { type: "video/mp4" });
    const out = await api.createJob([f], 3);
    expect(out.job_id).toBe("j1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/jobs");
    expect((init as RequestInit).method).toBe("POST");
    expect((init as RequestInit).body).toBeInstanceOf(FormData);
    const body = (init as RequestInit).body as FormData;
    expect(body.get("count")).toBe("3");
    expect(body.get("quality_mode")).toBe("fast");
    expect(body.getAll("files").length).toBe(1);
  });

  it("sends quality_mode hq when requested", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ job_id: "j1", sources: [] }), { status: 201 }));
    const f = new File([new Uint8Array([1, 2])], "a.mp4", { type: "video/mp4" });
    await api.createJob([f], 2, true, "hq");
    const body = (fetchMock.mock.calls[0][1] as RequestInit).body as FormData;
    expect(body.get("quality_mode")).toBe("hq");
  });

  it("retries a dropped chunked upload then starts the job", async () => {
    const f = new File([new Uint8Array(4_000_000)], "a.mp4", { type: "video/mp4" });
    let offset0 = 0;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u === "/api/uploads") {
        return new Response(JSON.stringify({ upload_id: "up1", chunk_hint: 2_000_000 }), { status: 200 });
      }
      if (u.includes("/api/uploads/up1?offset=0")) {
        offset0 += 1;
        if (offset0 === 1) {
          return new Response("Bad Gateway", { status: 502, statusText: "Bad Gateway" });
        }
        return new Response(JSON.stringify({ received: 2000000 }), { status: 200 });
      }
      if (u.includes("/api/uploads/up1?offset=2000000")) {
        return new Response(JSON.stringify({ received: 4000000 }), { status: 200 });
      }
      if (u === "/api/jobs/from-uploads") {
        return new Response(JSON.stringify({ job_id: "j1", sources: [] }), { status: 201 });
      }
      return new Response("nope", { status: 500, statusText: "Internal Server Error" });
    });
    const out = await api.createJob([f], 20);
    expect(out.job_id).toBe("j1");
    expect(offset0).toBe(2);
    expect(fetchMock.mock.calls.some((c) => String(c[0]) === "/api/jobs/from-uploads")).toBe(true);
  });
});

describe("regenerate posts form n", () => {
  it("sends n to the regenerate route", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ source_id: "s1", filename: "a.mp4", requested: 2, delivered: 2, shortfall: 0, variants: [] }), { status: 200 }));
    await api.regenerate("s1", 2);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sources/s1/regenerate");
    const body = (init as RequestInit).body as FormData;
    expect(body.get("n")).toBe("2");
  });
});

describe("retryCopy", () => {
  it("POSTs /api/sources/:id/retry-copy", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        source_id: "s1", filename: "a.mp4", requested: 1, delivered: 1, shortfall: 0,
        files_ready: 1, copy_status: "ok", variants: [],
      }), { status: 200 }),
    );
    await api.retryCopy("s1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sources/s1/retry-copy");
    expect((init as RequestInit).method).toBe("POST");
  });
});

describe("removeSource", () => {
  it("DELETEs /api/sources/:id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    await api.removeSource("s1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sources/s1");
    expect((init as RequestInit).method).toBe("DELETE");
  });
});

it("createDriveExport posts destination, variants, consume_bank, and caption folder", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ export_id: "exp_1", state: "pending", files: [] }), { status: 200 }),
  );
  await api.createDriveExport("dst_1", [{ source_id: "s1", index: 1, caption: "POV #reels" }], true, "bank_gym");
  const [, init] = fetchMock.mock.calls[0];
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({
    destination_id: "dst_1",
    variants: [{ source_id: "s1", index: 1, caption: "POV #reels" }],
    consume_bank: true,
    caption_bank_id: "bank_gym",
  });
});

it("createDriveExportSplit posts job_id, selected, destinations, consume_bank, and caption folder", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ ok: true, jobs: [], split: [] }), { status: 201 }),
  );
  await api.createDriveExportSplit({
    job_id: "j1",
    selected: [{ source_id: "s1", index: 1, caption: "POV #reels" }],
    destinations: [
      { destination_id: "dst_main", label: "main" },
      { destination_id: "dst_trial", label: "trial" },
      { destination_id: "dst_growth", label: "growth" },
    ],
    consume_bank: true,
    caption_bank_id: "bank_gym",
  });
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/drive/exports/split");
  expect((init as RequestInit).method).toBe("POST");
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({
    job_id: "j1",
    selected: [{ source_id: "s1", index: 1, caption: "POV #reels" }],
    destinations: [
      { destination_id: "dst_main", label: "main" },
      { destination_id: "dst_trial", label: "trial" },
      { destination_id: "dst_growth", label: "growth" },
    ],
    consume_bank: true,
    caption_bank_id: "bank_gym",
  });
});

describe("captions API", () => {
  it("listCaptions GETs /api/captions", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ cursor: 0, items: [] }), { status: 200 }),
    );
    await api.listCaptions();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/captions");
  });

  it("listCaptions and previewCaptions pass bank_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ cursor: 0, items: [], captions: [] }), { status: 200 })),
    );
    await api.listCaptions("bank_gym");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/captions?bank_id=bank_gym");
    await api.previewCaptions(3, "bank_gym");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/captions/preview?n=3&bank_id=bank_gym");
  });

  it("listCaptionBanks GETs /api/caption-banks", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    await api.listCaptionBanks();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/caption-banks");
  });
});

describe("listDestinationVideos", () => {
  it("GETs /api/drive/destinations/:id/videos", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ videos: [{ id: "f1", name: "clip.mp4", mime_type: "video/mp4", md5: null }] }), { status: 200 }),
    );
    const out = await api.listDestinationVideos("dst_1");
    expect(out.videos).toHaveLength(1);
    expect(out.videos[0].name).toBe("clip.mp4");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/drive/destinations/dst_1/videos");
  });
});

describe("createJobFromDrive", () => {
  it("POSTs JSON to /api/jobs/from-drive", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ job_id: "j1", sources: [] }), { status: 201 }),
    );
    await api.createJobFromDrive({
      destinationId: "dst_1",
      fileIds: ["f1", "f2"],
      count: 20,
      qualityMode: "hq",
      allowCreativeEscalate: false,
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/jobs/from-drive");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      destination_id: "dst_1",
      file_ids: ["f1", "f2"],
      count: 20,
      quality_mode: "hq",
      allow_creative_escalate: false,
    });
  });
});

describe("workflows API", () => {
  const sampleWorkflow = {
    id: "wf_1",
    name: "Inbox → Out",
    inbox_destination_id: "dst_in",
    output_destination_id: "dst_out",
    count: 20,
    quality_mode: "fast" as const,
    allow_creative_escalate: true,
    enabled: true,
    poll_seconds: 120,
    last_sweep_at: null,
    last_summary: null,
    auto_caption: false,
    caption_bank_id: null,
  };

  it("listWorkflows GETs /api/workflows", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([sampleWorkflow]), { status: 200 }),
    );
    const out = await api.listWorkflows();
    expect(out).toHaveLength(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/workflows");
  });

  it("createWorkflow POSTs JSON", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(sampleWorkflow), { status: 201 }),
    );
    await api.createWorkflow({
      name: "Inbox → Out",
      inbox_destination_id: "dst_in",
      output_destination_id: "dst_out",
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/workflows");
    expect((init as RequestInit).method).toBe("POST");
  });

  it("updateWorkflow PATCHes /api/workflows/:id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ...sampleWorkflow, enabled: false }), { status: 200 }),
    );
    await api.updateWorkflow("wf_1", { enabled: false });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/workflows/wf_1");
    expect((init as RequestInit).method).toBe("PATCH");
  });

  it("deleteWorkflow DELETEs /api/workflows/:id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await api.deleteWorkflow("wf_1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/workflows/wf_1");
    expect((init as RequestInit).method).toBe("DELETE");
  });

  it("runWorkflow POSTs /api/workflows/:id/run", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(sampleWorkflow), { status: 200 }),
    );
    await api.runWorkflow("wf_1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/workflows/wf_1/run");
    expect((init as RequestInit).method).toBe("POST");
  });
});

describe("error responses surface FastAPI `detail`", () => {
  it("throws the detail string from a JSON error body", async () => {
    const detail = "Cannot write to this folder — share it as Editor with sa@example.iam.gserviceaccount.com";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail }), { status: 400, statusText: "Bad Request" }),
    );
    await expect(api.getDriveStatus()).rejects.toThrow(detail);
  });

  it("joins array-style validation `detail` entries", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: [{ msg: "no ok videos in selection" }, { msg: "destination required" }] }),
        { status: 422, statusText: "Unprocessable Entity" },
      ),
    );
    await expect(api.getDriveStatus()).rejects.toThrow("no ok videos in selection; destination required");
  });

  it("maps 502 to a Generate-again upload drop", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>502</html>", { status: 502, statusText: "Bad Gateway" }),
    );
    await expect(api.getDriveStatus()).rejects.toThrow(/Generate again/i);
  });

  it("falls back to status text when the body isn't JSON", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>not json</html>", { status: 500, statusText: "Internal Server Error" }),
    );
    await expect(api.getDriveStatus()).rejects.toThrow("500 Internal Server Error");
  });
});
