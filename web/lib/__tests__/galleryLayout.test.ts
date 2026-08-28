import { describe, expect, it } from "vitest";
import {
  GALLERY_PREVIEW_TILE_PX,
  galleryPreviewFrameClass,
  galleryPreviewTileClass,
} from "@/lib/galleryLayout";

describe("gallery preview tile size", () => {
  it("caps preview tiles at a small–medium width, not native 1080", () => {
    expect(GALLERY_PREVIEW_TILE_PX).toBeGreaterThanOrEqual(140);
    expect(GALLERY_PREVIEW_TILE_PX).toBeLessThanOrEqual(180);
  });

  it("names the locked preview frame classes", () => {
    expect(galleryPreviewTileClass()).toBe("gallery-tile");
    expect(galleryPreviewFrameClass()).toBe("gallery-tile__frame");
  });
});
