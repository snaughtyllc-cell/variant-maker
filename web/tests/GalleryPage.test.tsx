import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SourceOut, VariantOut } from "@/lib/types";

const routerPush = vi.fn();
const routerReplace = vi.fn();
const searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
  useSearchParams: () => searchParams,
}));

vi.mock("@/lib/useGallery", () => ({
  useGallery: () => ({ data: [source()], mutate: vi.fn(), isLoading: false }),
}));

vi.mock("@/lib/runStore", () => ({
  useRun: () => ({ complete: false }),
}));

vi.mock("@/lib/api", () => ({
  getDriveStatus: () => Promise.resolve({ status: "not_configured", sa_email: null, message: "" }),
  listDestinations: () => Promise.resolve([]),
  sourceUrl: (id: string) => `/api/sources/${id}/source`,
  sourceZipUrl: () => "/api/sources/s1/zip",
  regenerate: vi.fn(),
  retryCopy: vi.fn(),
  removeSource: vi.fn(),
  setPlatformResult: vi.fn().mockResolvedValue({}),
  setPostUrl: vi.fn().mockResolvedValue({}),
}));

import { GalleryContent } from "@/app/gallery/page";
import { clearSharedVariantFileCache } from "@/lib/shareVideos";

function variant(over: Partial<VariantOut> = {}): VariantOut {
  return {
    index: 3,
    filename: "boil_v03.mp4",
    status: "ok",
    quality: {
      vmaf: 95,
      histogram_ok: true,
      regen_count: 0,
      passed: true,
      spatial_vmaf: null,
      spatial_ok: true,
    },
    file_url: "/api/variants/s1/boil_v03.mp4",
    file_ready: true,
    look_src_url: "/api/look/s1/look_v03_src.jpg",
    look_var_url: "/api/look/s1/look_v03.jpg",
    ...over,
  };
}

function source(over: Partial<SourceOut> = {}): SourceOut {
  return {
    source_id: "6bc8f627184a",
    filename: "if you didnt know a good boil.mp4",
    requested: 1,
    delivered: 1,
    shortfall: 0,
    files_ready: 1,
    job_state: "done",
    copy_status: "ok",
    variants: [variant()],
    ...over,
  };
}

describe("Gallery variant sheet open", () => {
  beforeEach(() => {
    routerPush.mockReset();
    routerReplace.mockReset();
    searchParams.delete("v");
  });

  afterEach(() => {
    clearSharedVariantFileCache();
    vi.unstubAllGlobals();
  });

  it("opens the sheet with history.pushState so Gallery does not remount", () => {
    const pushState = vi.spyOn(window.history, "pushState").mockImplementation(() => {});
    render(<GalleryContent />);
    fireEvent.click(screen.getByText("v03"));
    expect(pushState).toHaveBeenCalledWith(null, "", "/gallery?v=6bc8f627184a:3");
    expect(routerPush).not.toHaveBeenCalled();
    expect(routerReplace).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    pushState.mockRestore();
  });

  it("keeps toolbar Select all and puts Save and Send on the pack", () => {
    render(<GalleryContent />);
    const toolbar = screen.getByRole("region", { name: /gallery controls/i });
    expect(within(toolbar).getByRole("button", { name: "Select all" })).toBeInTheDocument();
    expect(within(toolbar).queryByRole("button", { name: /save to phone/i })).not.toBeInTheDocument();
    expect(within(toolbar).queryByRole("button", { name: /send to drive/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save to phone/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send to drive/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /select all \(/i })).not.toBeInTheDocument();
  });

  it("does not download clips when Select all is pressed", async () => {
    const fetchMock = vi.fn(async () =>
      new Response("vid", { status: 200, headers: { "Content-Type": "video/mp4" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<GalleryContent />);
    const toolbar = screen.getByRole("region", { name: /gallery controls/i });
    fireEvent.click(within(toolbar).getByRole("button", { name: "Select all" }));
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/Getting clip/i)).not.toBeInTheDocument();
  });

  it("lists each clip only after Save to phone is pressed on the pack", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        await gate;
        return new Response("vid", { status: 200, headers: { "Content-Type": "video/mp4" } });
      }),
    );
    render(<GalleryContent />);
    fireEvent.click(screen.getByRole("button", { name: /save to phone/i }));
    await waitFor(() => {
      expect(screen.getAllByText(/Getting clip 1 of 1/i).length).toBeGreaterThan(0);
      expect(screen.getByText("boil_v03.mp4")).toBeInTheDocument();
      expect(screen.getByText("Getting…")).toBeInTheDocument();
    });
    release();
    await waitFor(() => {
      expect(screen.queryByText("Getting…")).not.toBeInTheDocument();
    });
  });
});
