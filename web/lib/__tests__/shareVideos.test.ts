import { describe, it, expect, vi, afterEach } from "vitest";
import {
  canShareVideoFiles,
  downloadVideoFiles,
  fetchVariantFiles,
  isShareableVideo,
  phoneShareHintCopy,
  readyShareableVariants,
  shareEmptyCopy,
  shareVideoFiles,
  shareVideosLabel,
  zipSecondaryCopy,
} from "@/lib/shareVideos";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

describe("canShareVideoFiles", () => {
  it("is false in jsdom when nothing is injected", () => {
    expect(canShareVideoFiles()).toBe(false);
    expect(canShareVideoFiles(undefined)).toBe(false);
    expect(canShareVideoFiles({})).toBe(false);
  });

  it("uses injected canShare with a File probe and does not throw", () => {
    const canShare = vi.fn((data?: { files?: File[] }) => {
      expect(data?.files).toHaveLength(1);
      expect(data?.files?.[0]).toBeInstanceOf(File);
      expect(data?.files?.[0].name).toMatch(/\.mp4$/);
      return true;
    });
    expect(canShareVideoFiles({ canShare })).toBe(true);
    expect(canShare).toHaveBeenCalledTimes(1);
  });

  it("is false when canShare returns false or throws", () => {
    expect(canShareVideoFiles({ canShare: () => false })).toBe(false);
    expect(
      canShareVideoFiles({
        canShare: () => {
          throw new Error("TypeError: cannot share");
        },
      }),
    ).toBe(false);
  });

  it("probes the real files when they are passed", () => {
    const files = [new File(["a"], "v01.mp4", { type: "video/mp4" })];
    const canShare = vi.fn(() => true);
    expect(canShareVideoFiles({ canShare }, files)).toBe(true);
    expect(canShare).toHaveBeenCalledWith({ files });
  });
});

describe("shareVideoFiles", () => {
  it("returns unsupported without a share function or files", async () => {
    const file = new File(["x"], "v01.mp4", { type: "video/mp4" });
    expect(await shareVideoFiles([file])).toBe("unsupported");
    expect(await shareVideoFiles([], async () => {})).toBe("unsupported");
  });

  it("returns shared when shareFn resolves", async () => {
    const file = new File(["x"], "v01.mp4", { type: "video/mp4" });
    const shareFn = vi.fn(async (data: { files: File[] }) => {
      expect(data.files).toEqual([file]);
    });
    expect(await shareVideoFiles([file], shareFn)).toBe("shared");
    expect(shareFn).toHaveBeenCalledTimes(1);
  });

  it("returns aborted on AbortError", async () => {
    const file = new File(["x"], "v01.mp4", { type: "video/mp4" });
    const abort = new DOMException("Share canceled", "AbortError");
    expect(
      await shareVideoFiles([file], async () => {
        throw abort;
      }),
    ).toBe("aborted");
    expect(
      await shareVideoFiles([file], async () => {
        throw { name: "AbortError" };
      }),
    ).toBe("aborted");
  });

  it("returns unsupported on other share failures", async () => {
    const file = new File(["x"], "v01.mp4", { type: "video/mp4" });
    expect(
      await shareVideoFiles([file], async () => {
        throw new Error("NotAllowedError");
      }),
    ).toBe("unsupported");
  });
});

describe("ready shareable variants", () => {
  it("keeps file_ready omitted/true and status ok or omitted", () => {
    expect(isShareableVideo({ file_url: "/a", filename: "a.mp4" })).toBe(true);
    expect(isShareableVideo({ file_url: "/a", filename: "a.mp4", file_ready: true, status: "ok" })).toBe(true);
    expect(isShareableVideo({ file_url: "/a", filename: "a.mp4", file_ready: false })).toBe(false);
    expect(isShareableVideo({ file_url: "/a", filename: "a.mp4", status: "best_effort" })).toBe(false);
    expect(isShareableVideo({ filename: "a.mp4", status: "ok" })).toBe(false);
  });

  it("filters a pack down to ready mp4s", () => {
    const ready = readyShareableVariants([
      { filename: "v01.mp4", file_url: "/v01.mp4", status: "ok" as const },
      { filename: "v02.mp4", file_url: "/v02.mp4", file_ready: false, status: "ok" as const },
      { filename: "v03.mp4", file_url: "/v03.mp4", status: "corrupt" as const },
    ]);
    expect(ready.map((v) => v.filename)).toEqual(["v01.mp4"]);
  });
});

describe("fetchVariantFiles", () => {
  it("fetches each url as a File named after the variant", async () => {
    const fetchFn = vi.fn(async (url: string) => {
      expect(url).toBe("/api/variants/s1/v01.mp4");
      return new Response(new Blob(["mp4bytes"], { type: "video/mp4" }), { status: 200 });
    });
    const files = await fetchVariantFiles(
      [{ file_url: "/api/variants/s1/v01.mp4", filename: "v01.mp4" }],
      fetchFn as unknown as typeof fetch,
    );
    expect(files).toHaveLength(1);
    expect(files[0].name).toBe("v01.mp4");
    expect(files[0].type).toBe("video/mp4");
    expect(await files[0].text()).toBe("mp4bytes");
  });

  it("skips failed fetches", async () => {
    const fetchFn = vi.fn(async () => new Response("", { status: 404 }));
    const files = await fetchVariantFiles(
      [{ file_url: "/missing.mp4", filename: "v01.mp4" }],
      fetchFn as unknown as typeof fetch,
    );
    expect(files).toEqual([]);
  });
});

describe("downloadVideoFiles", () => {
  it("triggers an <a download> per file", () => {
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test-1");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clicks: string[] = [];
    const files = [
      new File(["a"], "v01.mp4", { type: "video/mp4" }),
      new File(["b"], "v02.mp4", { type: "video/mp4" }),
    ];
    downloadVideoFiles(files, (a) => {
      clicks.push(`${a.download}@${a.href}`);
    });
    expect(clicks).toEqual(["v01.mp4@blob:test-1", "v02.mp4@blob:test-1"]);
  });
});

describe("copy", () => {
  it("labels Share when canShare is true", () => {
    expect(shareVideosLabel(true)).toBe("Share videos");
    expect(shareVideosLabel(false)).toBe("Save videos");
  });

  it("keeps ZIP as a secondary desktop action and skips Files-app unzip", () => {
    expect(zipSecondaryCopy()).toMatch(/ZIP/i);
    expect(zipSecondaryCopy()).toMatch(/desktop/i);
    expect(phoneShareHintCopy()).toMatch(/unzip/i);
    expect(phoneShareHintCopy()).toMatch(/Files/i);
    expect(zipSecondaryCopy() + phoneShareHintCopy() + shareEmptyCopy()).not.toMatch(/Diagnostics/i);
  });
});
