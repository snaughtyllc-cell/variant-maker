import { describe, expect, it } from "vitest";
import type { DropPack } from "@/lib/types";
import {
  DROPS_EMPTY_COPY,
  dropStats,
  filterDropPacks,
  formatSendDay,
  sentWithinDays,
} from "@/lib/drops";

const mk = (over: Partial<DropPack> & Pick<DropPack, "export_id">): DropPack => ({
  created_utc: "2026-08-20T12:00:00Z",
  destination_id: "dst_a",
  destination_name: "Main",
  folder_id: "fld",
  count: 1,
  outcome: "pass",
  miss_labels: [],
  files: [{
    source_id: "s1",
    index: 1,
    variant_id: "s1:1",
    job_id: "j1",
    drive_file_id: "drv_1",
    platform_result: null,
    outcome: "pass",
  }],
  ...over,
});

describe("drops board helpers", () => {
  it("treats unlabeled as pass in the week window", () => {
    const now = Date.parse("2026-08-22T12:00:00Z");
    const packs = [
      mk({ export_id: "old", created_utc: "2026-08-01T00:00:00Z" }),
      mk({ export_id: "week", created_utc: "2026-08-20T00:00:00Z" }),
    ];
    expect(filterDropPacks(packs, "week", now).map((p) => p.export_id)).toEqual(["week"]);
    expect(sentWithinDays("2026-08-20T00:00:00Z", 7, now)).toBe(true);
    expect(sentWithinDays("2026-08-01T00:00:00Z", 7, now)).toBe(false);
  });

  it("flagged this week uses send day, not a label timestamp", () => {
    const now = Date.parse("2026-08-22T12:00:00Z");
    const packs = [
      mk({
        export_id: "old_miss",
        created_utc: "2026-08-01T00:00:00Z",
        outcome: "miss",
        miss_labels: ["flagged"],
        files: [{
          source_id: "s1", index: 1, variant_id: "s1:1", job_id: "j1",
          drive_file_id: "drv", platform_result: "flagged", outcome: "miss",
        }],
      }),
      mk({
        export_id: "week_miss",
        created_utc: "2026-08-21T00:00:00Z",
        outcome: "miss",
        miss_labels: ["duplicate_reject"],
        files: [{
          source_id: "s2", index: 2, variant_id: "s2:2", job_id: "j2",
          drive_file_id: "drv2", platform_result: "duplicate_reject", outcome: "miss",
        }],
      }),
      mk({ export_id: "week_pass", created_utc: "2026-08-21T01:00:00Z" }),
    ];
    expect(filterDropPacks(packs, "flagged_week", now).map((p) => p.export_id)).toEqual([
      "week_miss",
    ]);
    expect(filterDropPacks(packs, "misses", now).map((p) => p.export_id)).toEqual([
      "old_miss",
      "week_miss",
    ]);
  });

  it("win rate counts unlabeled as pass", () => {
    const packs = [
      mk({ export_id: "a", count: 2, files: [
        { source_id: "s1", index: 1, variant_id: "s1:1", job_id: "j1",
          drive_file_id: "d1", platform_result: null, outcome: "pass" },
        { source_id: "s1", index: 2, variant_id: "s1:2", job_id: "j1",
          drive_file_id: "d2", platform_result: "flagged", outcome: "miss" },
      ] }),
    ];
    expect(dropStats(packs)).toEqual({ sent: 2, misses: 1, winRate: 0.5 });
  });

  it("formats send day and empty copy without mentioning captions", () => {
    expect(formatSendDay("2026-08-21T10:15:00Z")).toBe("2026-08-21");
    expect(DROPS_EMPTY_COPY).toMatch(/Send to Drive/);
    expect(DROPS_EMPTY_COPY.toLowerCase()).not.toMatch(/caption/);
  });
});
