import { describe, it, expect } from "vitest";
import {
  DEFAULT_DRIVE_SHARE_EMAIL,
  DRIVE_SHARE_BODY,
  DRIVE_SHARE_HEADING,
  driveShareEmail,
} from "@/lib/driveShareCopy";

describe("driveShareCopy", () => {
  it("defaults the share mailbox to studio@varimo.io", () => {
    expect(DEFAULT_DRIVE_SHARE_EMAIL).toBe("studio@varimo.io");
    expect(driveShareEmail(null)).toBe("studio@varimo.io");
    expect(driveShareEmail("  ")).toBe("studio@varimo.io");
    expect(driveShareEmail(null, "studio@varimo.io")).toBe("studio@varimo.io");
    expect(driveShareEmail("drive@varyforge.app")).toBe("drive@varyforge.app");
    expect(driveShareEmail("ops@varyforge.app")).toBe("ops@varyforge.app");
    expect(DRIVE_SHARE_HEADING).toMatch(/share this email/i);
    expect(DRIVE_SHARE_BODY).toMatch(/Editor/i);
    expect(DRIVE_SHARE_BODY).toMatch(/paste the folder link/i);
    expect(DRIVE_SHARE_BODY).toMatch(/do not connect your own Google/i);
  });
});
