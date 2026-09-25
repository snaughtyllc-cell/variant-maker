import { describe, it, expect, vi } from "vitest";
import {
  COMPARE_TOUCH_THRESHOLD,
  compareTouchIntent,
  releasePointerCaptureSafe,
  startsCompareDragImmediately,
} from "@/lib/compareGesture";

describe("compare slider gestures", () => {
  it("starts dragging immediately for mouse and pen, not touch", () => {
    expect(startsCompareDragImmediately("mouse")).toBe(true);
    expect(startsCompareDragImmediately("pen")).toBe(true);
    expect(startsCompareDragImmediately("touch")).toBe(false);
  });

  it("waits under the movement threshold so a tap is not a drag", () => {
    expect(compareTouchIntent(0, 0)).toBe("undecided");
    expect(compareTouchIntent(COMPARE_TOUCH_THRESHOLD - 1, 2)).toBe("undecided");
  });

  it("treats mostly-vertical motion as sheet scroll, not a split drag", () => {
    expect(compareTouchIntent(4, 20)).toBe("scroll");
    expect(compareTouchIntent(-3, -12)).toBe("scroll");
  });

  it("treats mostly-horizontal motion as a split drag", () => {
    expect(compareTouchIntent(20, 4)).toBe("drag");
    expect(compareTouchIntent(-16, -2)).toBe("drag");
  });
});

describe("releasePointerCaptureSafe", () => {
  it("releases when the element still holds the pointer", () => {
    const releasePointerCapture = vi.fn();
    releasePointerCaptureSafe(
      { hasPointerCapture: () => true, releasePointerCapture },
      7,
    );
    expect(releasePointerCapture).toHaveBeenCalledWith(7);
  });

  it("does not throw when capture was never taken or already dropped", () => {
    expect(() => releasePointerCaptureSafe(null, 1)).not.toThrow();
    expect(() =>
      releasePointerCaptureSafe(
        { hasPointerCapture: () => false, releasePointerCapture: vi.fn() },
        1,
      ),
    ).not.toThrow();
    expect(() =>
      releasePointerCaptureSafe(
        {
          releasePointerCapture: () => {
            throw new DOMException("InvalidStateError");
          },
        },
        1,
      ),
    ).not.toThrow();
  });
});
