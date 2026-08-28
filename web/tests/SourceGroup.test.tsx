import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { SourceOut, VariantOut } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  regenerate: vi.fn(),
  retryCopy: vi.fn(),
  sourceUrl: () => "/api/source/s1",
  sourceZipUrl: () => "/api/sources/s1/zip",
  removeSource: vi.fn(),
}));

import { SourceGroup } from "@/components/gallery/SourceGroup";
import { uniquenessCoverageSubcopy } from "@/lib/prepareCopy";
import { clearSharedVariantFileCache, phoneShareHintCopy, zipSecondaryCopy } from "@/lib/shareVideos";
import type { Destination, DriveStatus } from "@/lib/types";

const driveReady: DriveStatus = { status: "ready", sa_email: "bot@x", message: "Drive ready" };
const dests: Destination[] = [{ id: "dst_1", name: "Cam", folder_id: "f", auth_mode: "oauth" }];

const quality = {
  vmaf: 95,
  histogram_ok: true,
  regen_count: 0,
  passed: true,
  spatial_vmaf: null,
  spatial_ok: true,
};

function variant(over: Partial<VariantOut> = {}): VariantOut {
  return {
    index: 1,
    filename: "v01.mp4",
    status: "ok",
    quality,
    file_url: "/api/variants/s1/v01.mp4",
    file_ready: true,
    ...over,
  };
}

function source(over: Partial<SourceOut> = {}): SourceOut {
  return {
    source_id: "s1",
    filename: "clip.mp4",
    requested: 2,
    delivered: 2,
    shortfall: 0,
    files_ready: 2,
    job_state: "done",
    copy_status: "ok",
    variants: [
      variant(),
      variant({ index: 2, filename: "v02.mp4", file_url: "/api/variants/s1/v02.mp4" }),
    ],
    ...over,
  };
}

const originalUserAgent = navigator.userAgent;
const originalTouchPoints = navigator.maxTouchPoints;

const noop = () => {};
const props = {
  onOpenVariant: noop,
  onRegenerate: noop,
  selected: new Set<string>(),
  onToggleVariant: noop,
  onToggleSelectSource: noop,
  onRemove: noop,
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  clearSharedVariantFileCache();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.innerHTML = "";
  Reflect.deleteProperty(navigator, "canShare");
  Reflect.deleteProperty(navigator, "share");
  Object.defineProperty(navigator, "userAgent", { configurable: true, value: originalUserAgent });
  Object.defineProperty(navigator, "maxTouchPoints", { configurable: true, value: originalTouchPoints });
});

describe("SourceGroup phone save/share", () => {
  it("shows Save to phone as the pack action and ZIP as a quieter secondary on desktop", async () => {
    render(<SourceGroup source={source()} {...props} />);
    expect(screen.getByRole("button", { name: /save to phone/i })).toBeInTheDocument();
    const zip = await screen.findByRole("link", { name: /download zip/i });
    expect(zip).toHaveAttribute("href", "/api/sources/s1/zip");
    expect(zip.getAttribute("title")).toBe(zipSecondaryCopy());
    expect(zip).toHaveClass("gallery-zip-link");
    expect(screen.getByRole("button", { name: /save to phone/i }).getAttribute("title")).toBe(
      phoneShareHintCopy(),
    );
    expect(screen.getByRole("button", { name: /select all/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send to drive/i })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Diagnostics/i);
  });

  it("does not download clips on mount or when Select all is pressed", () => {
    const onToggleSelectSource = vi.fn();
    render(<SourceGroup source={source()} {...props} onToggleSelectSource={onToggleSelectSource} />);
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /select all/i }));
    expect(onToggleSelectSource).toHaveBeenCalledWith(expect.anything(), true);
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.queryByText(/Getting clip/i)).not.toBeInTheDocument();
  });

  it("sends the whole pack to Drive without downloading clips", () => {
    const onSendToDrive = vi.fn();
    render(
      <SourceGroup
        source={source()}
        {...props}
        driveStatus={driveReady}
        destinations={dests}
        onSendToDrive={onSendToDrive}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /send to drive/i }));
    expect(onSendToDrive).toHaveBeenCalledWith([
      { source_id: "s1", index: 1 },
      { source_id: "s1", index: 2 },
    ]);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("sends and saves only the clips selected in this pack", async () => {
    const onSendToDrive = vi.fn();
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      return new Response(url, {
        status: 200,
        headers: { "Content-Type": "video/mp4" },
      });
    });
    const downloads: string[] = [];
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:dl");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const protoClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function click() {
      if (this.download) downloads.push(this.download);
    };

    try {
      render(
        <SourceGroup
          source={source()}
          {...props}
          selected={new Set(["s1:2"])}
          driveStatus={driveReady}
          destinations={dests}
          onSendToDrive={onSendToDrive}
        />,
      );
      fireEvent.click(screen.getByRole("button", { name: /send to drive \(1\)/i }));
      expect(onSendToDrive).toHaveBeenCalledWith([{ source_id: "s1", index: 2 }]);
      expect(fetchMock).not.toHaveBeenCalled();

      fireEvent.click(screen.getByRole("button", { name: /save to phone/i }));
      await waitFor(() => {
        expect(downloads).toEqual(["v02.mp4"]);
      });
      expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual([
        "/api/variants/s1/v02.mp4",
      ]);
    } finally {
      HTMLAnchorElement.prototype.click = protoClick;
    }
  });

  it("labels Save to Photos when the browser can share files", () => {
    Object.defineProperty(navigator, "canShare", {
      configurable: true,
      value: () => true,
    });
    render(<SourceGroup source={source()} {...props} />);
    expect(screen.getByRole("button", { name: /save to photos/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /save to phone/i })).not.toBeInTheDocument();
  });

  it("hides ZIP on coarse-pointer (phone) devices", async () => {
    window.matchMedia = ((query: string) =>
      ({
        matches: query === "(pointer: coarse)",
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as MediaQueryList);
    render(<SourceGroup source={source()} {...props} />);
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: /download zip/i })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /save to phone/i })).toBeInTheDocument();
  });

  it("hides Save to phone while the job is still running", () => {
    render(
      <SourceGroup
        source={source({ job_state: "running", in_flight: { index: 3, state: "rendering", attempt: 0, max_attempts: 2 } })}
        {...props}
      />,
    );
    expect(screen.queryByRole("button", { name: /save to phone/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /download zip/i })).not.toBeInTheDocument();
  });

  it("fetches ready mp4s and downloads each file when share is unavailable", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      return new Response(url, {
        status: 200,
        headers: { "Content-Type": "video/mp4" },
      });
    });
    const downloads: string[] = [];
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:dl");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const protoClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function click() {
      if (this.download) downloads.push(this.download);
    };

    try {
      render(<SourceGroup source={source()} {...props} />);
      fireEvent.click(screen.getByRole("button", { name: /save to phone/i }));

      await waitFor(() => {
        expect(downloads).toEqual(["v01.mp4", "v02.mp4"]);
      });
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));
      expect(urls).toEqual(expect.arrayContaining([
        "/api/variants/s1/v01.mp4",
        "/api/variants/s1/v02.mp4",
      ]));
    } finally {
      HTMLAnchorElement.prototype.click = protoClick;
    }
  });

  it("on iPhone prepares clips on the first Save tap and only shares on the second", async () => {
    const SAFARI_IPHONE =
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
    const share = vi.fn(async () => {});
    Object.defineProperty(navigator, "userAgent", { configurable: true, value: SAFARI_IPHONE });
    Object.defineProperty(navigator, "maxTouchPoints", { configurable: true, value: 5 });
    Object.defineProperty(navigator, "canShare", { configurable: true, value: () => true });
    Object.defineProperty(navigator, "share", { configurable: true, value: share });
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.mocked(fetch).mockImplementation(async () => {
      await gate;
      return new Response("vid", { status: 200, headers: { "Content-Type": "video/mp4" } });
    });

    render(<SourceGroup source={source()} {...props} />);
    fireEvent.click(screen.getByRole("button", { name: /save to photos/i }));
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(share).not.toHaveBeenCalled();
    release();
    await waitFor(() => {
      expect(screen.getByText(/Tap Save to Photos again/i)).toBeInTheDocument();
    });
    expect(share).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /save to photos/i }));
    await waitFor(() => expect(share).toHaveBeenCalledTimes(1));
    const payload = share.mock.calls[0][0] as { files: File[] };
    expect(payload.files.map((f) => f.name)).toEqual(["v01.mp4", "v02.mp4"]);
  });

  it("shares File objects when canShare accepts them", async () => {
    const share = vi.fn(async () => {});
    Object.defineProperty(navigator, "canShare", {
      configurable: true,
      value: () => true,
    });
    Object.defineProperty(navigator, "share", {
      configurable: true,
      value: share,
    });
    vi.mocked(fetch).mockImplementation(async () =>
      new Response("vid", { status: 200, headers: { "Content-Type": "video/mp4" } }),
    );

    render(<SourceGroup source={source()} {...props} />);
    fireEvent.click(screen.getByRole("button", { name: /save to photos/i }));

    await waitFor(() => expect(share).toHaveBeenCalledTimes(1));
    const payload = share.mock.calls[0][0] as { files: File[]; title?: string; url?: string };
    expect(payload.files.map((f) => f.name)).toEqual(["v01.mp4", "v02.mp4"]);
    expect(payload.title).toBeUndefined();
    expect(payload.url).toBeUndefined();
  });

  it("does not fetch variants that are not ready or not ok", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("x", { status: 200, headers: { "Content-Type": "video/mp4" } }),
    );
    render(
      <SourceGroup
        source={source({
          files_ready: 1,
          variants: [
            variant({ file_ready: false }),
            variant({ index: 2, filename: "v02.mp4", file_url: "/api/variants/s1/v02.mp4", status: "best_effort" }),
            variant({ index: 3, filename: "v03.mp4", file_url: "/api/variants/s1/v03.mp4" }),
          ],
        })}
        {...props}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /save to phone/i }));
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const urls = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
    expect(urls.every((url) => url === "/api/variants/s1/v03.mp4")).toBe(true);
    expect(urls.length).toBeGreaterThanOrEqual(1);
  });
});

describe("SourceGroup live post count", () => {
  it("shows how many variants have a pasted permalink", () => {
    render(
      <SourceGroup
        source={source({
          variants: [
            variant({ post_url: "https://www.instagram.com/reel/a/" }),
            variant({
              index: 2,
              filename: "v02.mp4",
              file_url: "/api/variants/s1/v02.mp4",
              post_url: "https://www.tiktok.com/@x/video/1",
            }),
          ],
        })}
        {...props}
      />,
    );
    expect(screen.getByText(/2 live posts/i)).toBeInTheDocument();
  });
});

describe("SourceGroup originality summary", () => {
  it("titles the Originality average as pixel SSIM, not a platform check", () => {
    render(
      <SourceGroup
        source={source({
          variants: [
            variant({ uniqueness: 0.5 }),
            variant({
              index: 2,
              filename: "v02.mp4",
              file_url: "/api/variants/s1/v02.mp4",
              uniqueness: 0.4,
            }),
          ],
        })}
        {...props}
      />,
    );
    const summary = screen.getByText(/Originality 45% avg/);
    expect(summary).toHaveAttribute("title", uniquenessCoverageSubcopy());
  });
});
