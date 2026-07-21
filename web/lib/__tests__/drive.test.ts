import { describe, it, expect } from "vitest";
import { exportProgressLabel, okVariantRefs, sendDisabledReason, truncateFolderId } from "@/lib/drive";
import type { SourceOut } from "@/lib/types";

const sources: SourceOut[] = [{
  source_id: "s1", filename: "a.mp4", requested: 2, delivered: 1, shortfall: 1,
  variants: [
    { index: 1, filename: "v01.mp4", status: "ok", quality: {}, file_url: "/x" },
    { index: 2, filename: "v02.mp4", status: "best_effort", quality: {}, file_url: "/y" },
  ],
  failed: 1,
}];

describe("okVariantRefs", () => {
  it("keeps only ok selected", () => {
    const sel = new Set(["s1:1", "s1:2"]);
    expect(okVariantRefs(sources, sel)).toEqual([{ source_id: "s1", index: 1 }]);
  });
});

describe("truncateFolderId", () => {
  it("truncates long folder ids", () => {
    expect(truncateFolderId("1AbCdefghijk0123456789XYZ", 4)).toBe("1AbC…9XYZ");
  });
});

describe("sendDisabledReason", () => {
  it("blocks when not configured", () => {
    expect(sendDisabledReason(
      { status: "not_configured", sa_email: null, message: "Drive not configured — set VARIANT_DRIVE_SERVICE_ACCOUNT_JSON" },
      [{ id: "dst_1", name: "R", folder_id: "f", auth_mode: "service_account" }],
      [{ source_id: "s1", index: 1 }],
    )).toMatch(/not configured/i);
  });
  it("blocks when no destinations", () => {
    expect(sendDisabledReason(
      { status: "ready", sa_email: "bot@x", message: "Drive ready" },
      [],
      [{ source_id: "s1", index: 1 }],
    )).toMatch(/destination/i);
  });
  it("blocks when no ok refs", () => {
    expect(sendDisabledReason(
      { status: "ready", sa_email: "bot@x", message: "Drive ready" },
      [{ id: "dst_1", name: "R", folder_id: "f", auth_mode: "service_account" }],
      [],
    )).toMatch(/ok variant/i);
  });
  it("allows when ready", () => {
    expect(sendDisabledReason(
      { status: "ready", sa_email: "bot@x", message: "Drive ready" },
      [{ id: "dst_1", name: "R", folder_id: "f", auth_mode: "service_account" }],
      [{ source_id: "s1", index: 1 }],
    )).toBeNull();
  });
});

describe("exportProgressLabel", () => {
  it("counts finished and current", () => {
    expect(exportProgressLabel({
      files: [
        { status: "succeeded", filename: "v01.mp4" },
        { status: "uploading", filename: "v02.mp4" },
        { status: "pending", filename: "v03.mp4" },
      ],
    })).toEqual({ done: 1, total: 3, current: "v02.mp4" });
  });
});
