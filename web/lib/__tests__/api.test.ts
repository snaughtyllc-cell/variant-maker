import { describe, it, expect, vi, beforeEach } from "vitest";
import * as api from "@/lib/api";

beforeEach(() => { vi.restoreAllMocks(); });

describe("url builders use relative /api", () => {
  it("variantUrl / sourceUrl / eventsUrl", () => {
    expect(api.variantUrl("s1", "v01.mp4")).toBe("/api/variants/s1/v01.mp4");
    expect(api.sourceUrl("s1")).toBe("/api/sources/s1/source");
    expect(api.eventsUrl("j1")).toBe("/api/jobs/j1/events");
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
    expect(body.getAll("files").length).toBe(1);
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
