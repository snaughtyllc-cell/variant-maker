import { describe, it, expect } from "vitest";
import { dropZoneBrowse, dropZoneHint, dropZoneSubcopy, dropZoneTitle } from "@/lib/dropZoneCopy";
import { studioProgressIdleClass, studioShellClass } from "@/lib/studioLayout";

describe("drop zone copy", () => {
  it("tells phone users to tap, not only drop", () => {
    expect(dropZoneTitle()).toBe("Add videos");
    expect(dropZoneSubcopy()).toMatch(/tap/i);
    expect(dropZoneBrowse()).toMatch(/camera roll|files/i);
    expect(dropZoneHint()).toMatch(/1080/i);
  });
});

describe("studio layout classes", () => {
  it("marks a live run so mobile can pin progress first", () => {
    expect(studioShellClass(false)).toBe("studio-shell");
    expect(studioShellClass(true)).toBe("studio-shell studio-shell--live");
  });

  it("hides the empty progress pane on phones", () => {
    expect(studioProgressIdleClass(false)).toBe("studio-progress studio-progress--idle");
    expect(studioProgressIdleClass(true)).toBe("studio-progress");
  });
});
