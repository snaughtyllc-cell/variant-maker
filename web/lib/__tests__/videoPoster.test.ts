import { afterEach, describe, expect, it, vi } from "vitest";
import {
  captureVideoPoster,
  posterTimeoutMs,
  resetVideoPosterCache,
} from "@/lib/videoPoster";

function mockPosterPaint() {
  const drawImage = vi.fn();
  const toDataURL = vi.fn(() => "data:image/jpeg;base64,frame");
  const originalCreate = document.createElement.bind(document);
  let videos = 0;
  vi.spyOn(document, "createElement").mockImplementation((tag: string, options?: string | ElementCreationOptions) => {
    const el = originalCreate(tag, options as ElementCreationOptions);
    if (tag === "video") {
      videos += 1;
      Object.defineProperty(el, "videoWidth", { configurable: true, get: () => 1080 });
      Object.defineProperty(el, "videoHeight", { configurable: true, get: () => 1920 });
      Object.defineProperty(el, "duration", { configurable: true, get: () => 4 });
      let src = "";
      Object.defineProperty(el, "src", {
        configurable: true,
        get: () => src,
        set: (value: string) => {
          src = value;
          queueMicrotask(() => {
            el.dispatchEvent(new Event("loadedmetadata"));
            el.dispatchEvent(new Event("loadeddata"));
            queueMicrotask(() => el.dispatchEvent(new Event("seeked")));
          });
        },
      });
    }
    if (tag === "canvas") {
      Object.defineProperty(el, "getContext", {
        value: () => ({ drawImage }),
      });
      Object.defineProperty(el, "toDataURL", { value: toDataURL });
    }
    return el;
  });
  return { drawImage, videoCount: () => videos };
}

afterEach(() => {
  resetVideoPosterCache();
  vi.restoreAllMocks();
});

describe("captureVideoPoster", () => {
  it("gives large clips more time to decode a first frame", () => {
    const small = new File(["x"], "short.mp4", { type: "video/mp4" });
    const big = new File(["x"], "long.mp4", { type: "video/mp4" });
    Object.defineProperty(big, "size", { value: 80 * 1024 * 1024 });
    expect(posterTimeoutMs(small)).toBeGreaterThanOrEqual(8000);
    expect(posterTimeoutMs(big)).toBeGreaterThan(posterTimeoutMs(small));
    expect(posterTimeoutMs(big)).toBeLessThanOrEqual(25000);
  });

  it("draws a jpeg once the offscreen video can paint a frame", async () => {
    if (!URL.createObjectURL) URL.createObjectURL = vi.fn(() => "blob:poster");
    if (!URL.revokeObjectURL) URL.revokeObjectURL = vi.fn();
    const { drawImage } = mockPosterPaint();
    const file = new File(["x"], "gym.mp4", { type: "video/mp4" });
    await expect(captureVideoPoster(file, 500)).resolves.toBe("data:image/jpeg;base64,frame");
    expect(drawImage).toHaveBeenCalled();
  });

  it("reuses one decode for the same file so source and caption thumbs share a poster", async () => {
    if (!URL.createObjectURL) URL.createObjectURL = vi.fn(() => "blob:poster");
    if (!URL.revokeObjectURL) URL.revokeObjectURL = vi.fn();
    const { videoCount } = mockPosterPaint();
    const file = new File(["x"], "gym.mp4", { type: "video/mp4" });
    const first = captureVideoPoster(file, 500);
    const second = captureVideoPoster(file, 500);
    expect(first).toBe(second);
    await expect(first).resolves.toBe("data:image/jpeg;base64,frame");
    await expect(second).resolves.toBe("data:image/jpeg;base64,frame");
    expect(videoCount()).toBe(1);
  });
});
