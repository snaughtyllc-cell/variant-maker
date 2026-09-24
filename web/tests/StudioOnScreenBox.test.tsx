import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import {
  captionsWithNewBox,
  emptyOnScreen,
  projectFromDraft,
  rectFromPoints,
  StudioOnScreenBox,
  type OnScreenProject,
} from "@/components/studio/StudioOnScreenBox";

describe("on-screen project", () => {
  it("keeps a drawn box locked by its color", () => {
    const draft = emptyOnScreen();
    draft.captions[0].text = "hello";
    draft.captions[0].box_ids = ["cyan"];
    draft.boxes = [{ id: "cyan", color: "#14b8c4", x: 0.1, y: 0.2, w: 0.5, h: 0.15 }];
    const project = projectFromDraft(draft);
    expect(typeof project).not.toBe("string");
    if (typeof project === "string") return;
    expect(project.captions[0].box_ids).toEqual(["cyan"]);
    expect(project.boxes[0]).toMatchObject({ id: "cyan", x: 0.1, y: 0.2, w: 0.5, h: 0.15 });
  });

  it("refuses a line with no box", () => {
    const draft = emptyOnScreen();
    draft.captions[0].text = "hello";
    expect(projectFromDraft(draft)).toBe("Each line needs a box.");
  });

  it("refuses two lines on the same box", () => {
    const draft = emptyOnScreen();
    draft.boxes = [{ id: "cyan", color: "#14b8c4", x: 0.1, y: 0.2, w: 0.4, h: 0.2 }];
    draft.captions = [
      { id: "1", text: "one", box_ids: ["cyan"] },
      { id: "2", text: "two", box_ids: ["cyan"] },
    ];
    expect(projectFromDraft(draft)).toBe("Each box locks to one line.");
  });

  it("refuses a drawn box that no line owns", () => {
    const draft = emptyOnScreen();
    draft.captions[0].text = "hello";
    draft.captions[0].box_ids = ["cyan"];
    draft.boxes = [
      { id: "cyan", color: "#14b8c4", x: 0.1, y: 0.2, w: 0.4, h: 0.2 },
      { id: "amber", color: "#e39b12", x: 0.1, y: 0.5, w: 0.4, h: 0.2 },
    ];
    expect(projectFromDraft(draft)).toBe("Lock every colored box to a line.");
  });

  it("locks a new box onto the first open line", () => {
    const lines = captionsWithNewBox(
      [
        { id: "1", text: "one", box_ids: [] },
        { id: "2", text: "two", box_ids: [] },
      ],
      "cyan",
    );
    expect(lines[0].box_ids).toEqual(["cyan"]);
    expect(lines[1].box_ids).toEqual([]);
    const extra = captionsWithNewBox(
      [{ id: "1", text: "one", box_ids: ["cyan"] }],
      "amber",
    );
    expect(extra[0].box_ids).toEqual(["cyan", "amber"]);
  });

  it("turns a drag into a rectangle", () => {
    const rect = rectFromPoints(0.4, 0.5, 0.1, 0.2);
    expect(rect.x).toBeCloseTo(0.1);
    expect(rect.y).toBeCloseTo(0.2);
    expect(rect.w).toBeCloseTo(0.3);
    expect(rect.h).toBeCloseTo(0.3);
  });
});

function Harness() {
  const [draft, setDraft] = useState<OnScreenProject>(emptyOnScreen());
  return (
    <StudioOnScreenBox
      enabled
      onEnabledChange={() => undefined}
      draft={draft}
      onChange={setDraft}
    />
  );
}

describe("phone box drawer", () => {
  it("draws a colored box when you drag on the phone", () => {
    render(<Harness />);
    const phone = screen.getByTestId("onscreen-phone");
    phone.getBoundingClientRect = () => ({
      x: 0, y: 0, left: 0, top: 0, right: 180, bottom: 320, width: 180, height: 320, toJSON() { return {}; },
    });
    fireEvent.pointerDown(phone, { button: 0, pointerId: 1, clientX: 20, clientY: 80 });
    fireEvent.pointerMove(phone, { pointerId: 1, clientX: 120, clientY: 180 });
    fireEvent.pointerUp(phone, { pointerId: 1, clientX: 120, clientY: 180 });
    expect(screen.getByRole("button", { name: "Cyan, this line" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("On-screen line 1"), { target: { value: "sale" } });
    expect(phone.querySelector("[data-role='text']")?.textContent).toBe("sale");
  });

  it("shows the clip still under the Reel safe edges", () => {
    const draft = emptyOnScreen();
    render(
      <StudioOnScreenBox
        enabled
        onEnabledChange={() => undefined}
        draft={draft}
        onChange={() => undefined}
        sources={[{ key: "a", name: "gym.mp4", src: "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" }]}
      />,
    );
    const phone = screen.getByTestId("onscreen-phone");
    expect(phone.querySelector("img")?.getAttribute("src")).toContain("data:image");
    expect(phone.textContent).toContain("Header");
    expect(phone.textContent).toContain("Buttons");
    expect(phone.textContent).toContain("Caption");
  });

  it("shows the typed line on the phone and keeps a box on one line", () => {
    const draft = emptyOnScreen();
    draft.boxes = [
      { id: "cyan", color: "#14b8c4", x: 0.1, y: 0.2, w: 0.5, h: 0.2 },
      { id: "amber", color: "#e39b12", x: 0.1, y: 0.55, w: 0.5, h: 0.2 },
    ];
    draft.captions = [
      { id: "1", text: "hello there", box_ids: ["cyan"] },
      { id: "2", text: "second line", box_ids: [] },
    ];
    render(
      <StudioOnScreenBox
        enabled
        onEnabledChange={() => undefined}
        draft={draft}
        onChange={() => undefined}
      />,
    );
    const phone = screen.getByTestId("onscreen-phone");
    const sticker = phone.querySelector("[data-role='text']");
    expect(sticker?.textContent).toBe("hello there");
    expect(sticker?.className).toContain("studio-onscreen__type--solid");
    const line1 = screen.getByRole("group", { name: "Colors for line 1" });
    const line2 = screen.getByRole("group", { name: "Colors for line 2" });
    expect(line1.querySelector("[aria-label='Cyan, this line']")).toBeTruthy();
    expect(line2.querySelector("[aria-label='Cyan, this line']")).toBeNull();
    expect(line2.querySelector("[aria-label='Add Amber']")).toBeTruthy();
  });
});
