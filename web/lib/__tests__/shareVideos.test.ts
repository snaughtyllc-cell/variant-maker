import { describe, it, expect, vi, afterEach } from "vitest";
import {
  cacheHasAll,
  canShareVideoFiles,
  cloneShareFiles,
  downloadVideoFiles,
  fetchVariantFiles,
  filesReadyNow,
  fillFileCache,
  isAppleMobile,
  isShareableVideo,
  peekCachedFiles,
  phoneShareHintCopy,
  preparingClipsCopy,
  readyShareableVariants,
  saveNoneSelectedCopy,
  saveOrShareVideoFiles,
  selectedShareableVariants,
  shareEmptyCopy,
  shareLoadingCopy,
  shareRetryCopy,
  shouldOfferPhotosSave,
  shareVideoFiles,
  shareVideosBusyLabel,
  shareVideosLabel,
  zipSecondaryCopy,
  zipVisibleOnDevice,
} from "@/lib/shareVideos";

const SAFARI_IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
const CHROME_IPHONE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1";

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
      expect(data.files).toHaveLength(1);
      expect(data.files[0].name).toBe("v01.mp4");
      expect(data.files[0].type).toBe("video/mp4");
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
    expect(isShareableVideo({ file_url: "/a", filename: "a.mp4", status: "uniqueness_fail" })).toBe(false);
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
      return new Response("mp4bytes", {
        status: 200,
        headers: { "Content-Type": "video/mp4" },
      });
    });
    const files = await fetchVariantFiles(
      [{ file_url: "/api/variants/s1/v01.mp4", filename: "v01.mp4" }],
      fetchFn as unknown as typeof fetch,
    );
    expect(files).toHaveLength(1);
    expect(files[0].name).toBe("v01.mp4");
    expect(files[0].type).toMatch(/video\/mp4/);
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

describe("cloneShareFiles", () => {
  it("stamps a fresh video/mp4 File so Safari can share the same clips again", () => {
    const original = new File(["a"], "v01", { type: "application/octet-stream" });
    const [clone] = cloneShareFiles([original]);
    expect(clone).not.toBe(original);
    expect(clone.name).toBe("v01.mp4");
    expect(clone.type).toBe("video/mp4");
  });
});

describe("saveOrShareVideoFiles", () => {
  it("falls back to per-file download when share is unavailable on desktop", async () => {
    const file = new File(["x"], "v01.mp4", { type: "video/mp4" });
    const download = vi.fn();
    expect(
      await saveOrShareVideoFiles([file], {
        download,
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
      }),
    ).toEqual({
      result: "downloaded",
      remaining: [],
    });
    expect(download).toHaveBeenCalledWith([file]);
  });

  it("shares every selected clip in one Safari sheet", async () => {
    const files = [
      new File(["a"], "v01.mp4", { type: "video/mp4" }),
      new File(["b"], "v02.mp4", { type: "video/mp4" }),
    ];
    const share = vi.fn(async () => {});
    const download = vi.fn();
    expect(
      await saveOrShareVideoFiles(files, {
        share: { canShare: () => true, share },
        download,
        userAgent: SAFARI_IPHONE,
        maxTouchPoints: 5,
      }),
    ).toEqual({ result: "shared", remaining: [] });
    expect(share).toHaveBeenCalledTimes(1);
    expect(share.mock.calls[0][0].files.map((f: File) => f.name)).toEqual(["v01.mp4", "v02.mp4"]);
    expect(share.mock.calls[0][0]).not.toHaveProperty("title");
    expect(share.mock.calls[0][0]).not.toHaveProperty("url");
    expect(download).not.toHaveBeenCalled();
  });

  it("does not Safari-download when iOS blocks share — keeps clips for another tap", async () => {
    const files = [
      new File(["a"], "v01.mp4", { type: "video/mp4" }),
      new File(["b"], "v02.mp4", { type: "video/mp4" }),
    ];
    const share = vi.fn(async () => {
      throw new DOMException("The request is not allowed", "NotAllowedError");
    });
    const download = vi.fn();
    expect(
      await saveOrShareVideoFiles(files, {
        share: { canShare: () => true, share },
        download,
        userAgent: SAFARI_IPHONE,
        maxTouchPoints: 5,
      }),
    ).toEqual({ result: "needs_gesture", remaining: files, reason: "retry" });
    expect(download).not.toHaveBeenCalled();
  });

  it("still tries the share sheet on Chrome iPhone instead of Drive/Files download", async () => {
    const files = [
      new File(["a"], "v01.mp4", { type: "video/mp4" }),
      new File(["b"], "v02.mp4", { type: "video/mp4" }),
    ];
    const share = vi.fn(async () => {});
    const download = vi.fn();
    expect(
      await saveOrShareVideoFiles(files, {
        share: { share },
        download,
        userAgent: CHROME_IPHONE,
        maxTouchPoints: 5,
      }),
    ).toEqual({ result: "shared", remaining: [] });
    expect(share).toHaveBeenCalledTimes(1);
    expect(share.mock.calls[0][0].files.map((f: File) => f.name)).toEqual(["v01.mp4", "v02.mp4"]);
    expect(download).not.toHaveBeenCalled();
    expect(isAppleMobile(CHROME_IPHONE, 5)).toBe(true);
  });
});

describe("variant file cache", () => {
  it("fills missing urls and peeks without refetching", async () => {
    const cache = new Map<string, File>();
    const variants = [
      { file_url: "/a", filename: "v01.mp4" },
      { file_url: "/b", filename: "v02.mp4" },
    ];
    const fetchFn = vi.fn(async (url: string) => {
      return new Response(url, { status: 200, headers: { "Content-Type": "video/mp4" } });
    });
    expect(cacheHasAll(cache, variants)).toBe(false);
    expect(filesReadyNow(cache, variants)).toBeNull();
    const files = await fillFileCache(cache, variants, fetchFn as unknown as typeof fetch);
    expect(files.map((f) => f.name)).toEqual(["v01.mp4", "v02.mp4"]);
    expect(cacheHasAll(cache, variants)).toBe(true);
    expect(peekCachedFiles(cache, variants)).toEqual(files);
    expect(filesReadyNow(cache, variants)?.map((f) => f.name)).toEqual(["v01.mp4", "v02.mp4"]);
    const pending = [files[1]];
    expect(filesReadyNow(cache, variants, pending)).toEqual(pending);
    fetchFn.mockClear();
    await fillFileCache(cache, variants, fetchFn as unknown as typeof fetch);
    expect(fetchFn).not.toHaveBeenCalled();
  });
});

describe("selectedShareableVariants", () => {
  it("keeps selected ok-ready clips with file urls", () => {
    expect(
      selectedShareableVariants(
        [
          {
            source_id: "s1",
            filename: "a.mp4",
            requested: 2,
            delivered: 2,
            shortfall: 0,
            variants: [
              { filename: "v01.mp4", file_url: "/a", status: "ok", index: 1 } as never,
              { filename: "v02.mp4", file_url: "/b", status: "ok", index: 2 } as never,
              { filename: "v03.mp4", file_url: "/c", status: "best_effort", index: 3 } as never,
            ],
          },
        ],
        new Set(["s1:1", "s1:3"]),
      ),
    ).toEqual([{ file_url: "/a", filename: "v01.mp4" }]);
  });
});

describe("copy", () => {
  it("labels Save to Photos when the share sheet can take videos", () => {
    expect(shareVideosLabel(true)).toBe("Save to Photos");
    expect(shareVideosLabel(false)).toBe("Save to phone");
    expect(shouldOfferPhotosSave({ share: async () => {} })).toBe(true);
    expect(shouldOfferPhotosSave({}, SAFARI_IPHONE, 5)).toBe(true);
    expect(shareVideosBusyLabel()).toBe("Saving…");
    expect(saveNoneSelectedCopy()).toBe("Select clips first");
    expect(preparingClipsCopy()).toBe("Preparing clips…");
    expect(shareLoadingCopy()).toMatch(/Preparing clips/i);
    expect(shareRetryCopy()).toMatch(/Tap Save to Photos again/i);
    expect(phoneShareHintCopy()).toMatch(/Save Videos/i);
    expect(shareRetryCopy() + shareLoadingCopy()).not.toMatch(/Diagnostics/i);
  });

  it("keeps ZIP as a secondary desktop action and names the Files-app trap", () => {
    expect(zipSecondaryCopy()).toMatch(/ZIP/i);
    expect(zipSecondaryCopy()).toMatch(/desktop/i);
    expect(zipSecondaryCopy()).toMatch(/Files/i);
    expect(phoneShareHintCopy()).toMatch(/Save Video/i);
    expect(phoneShareHintCopy()).toMatch(/Photos/i);
    expect(zipVisibleOnDevice(() => ({ matches: true }))).toBe(false);
    expect(zipVisibleOnDevice(() => ({ matches: false }))).toBe(true);
    expect(zipVisibleOnDevice(undefined)).toBe(true);
    expect(zipSecondaryCopy() + phoneShareHintCopy() + shareEmptyCopy()).not.toMatch(/Diagnostics/i);
  });
});
