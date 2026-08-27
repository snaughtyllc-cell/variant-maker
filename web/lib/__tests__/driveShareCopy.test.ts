import { describe, it, expect } from "vitest";
import {
  DEFAULT_DRIVE_SHARE_EMAIL,
  DRIVE_SHARE_BODY,
  DRIVE_SHARE_HEADING,
  driveShareEmail,
} from "@/lib/driveShareCopy";

describe("driveShareCopy", () => {
  it("keeps the live Drive mailbox on Jeff's Gmail until the branded switch is ready", () => {
    expect(DEFAULT_DRIVE_SHARE_EMAIL).toBe("snaughtyllc@gmail.com");
    expect(driveShareEmail(null)).toBe("snaughtyllc@gmail.com");
    expect(driveShareEmail("  ")).toBe("snaughtyllc@gmail.com");
    expect(driveShareEmail(null, "snaughtyllc@gmail.com")).toBe("snaughtyllc@gmail.com");
    expect(driveShareEmail("drive@varyforge.app")).toBe("drive@varyforge.app");
    expect(driveShareEmail("ops@varyforge.app")).toBe("ops@varyforge.app");
    expect(DRIVE_SHARE_HEADING).toMatch(/share this email/i);
    expect(DRIVE_SHARE_BODY).toMatch(/Editor/i);
    expect(DRIVE_SHARE_BODY).toMatch(/paste the folder link/i);
  });
});
