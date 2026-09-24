import { describe, expect, it } from "vitest";
import { emptyOnScreen, projectFromDraft } from "@/components/studio/StudioOnScreenBox";

describe("on-screen project", () => {
  it("builds one line locked to the middle box", () => {
    const draft = emptyOnScreen();
    draft.captions[0].text = "hello";
    const project = projectFromDraft(draft);
    expect(typeof project).not.toBe("string");
    if (typeof project === "string") return;
    expect(project.captions).toEqual([{ id: "1", text: "hello", box_ids: ["middle"] }]);
    expect(project.boxes.map((box) => box.id)).toEqual(["middle"]);
    expect(project.look.style).toBe("classic");
  });

  it("refuses a line with no box", () => {
    const draft = emptyOnScreen();
    draft.captions[0].text = "hello";
    draft.captions[0].box_ids = [];
    expect(projectFromDraft(draft)).toBe("Each line needs a box.");
  });

  it("refuses two lines on the same box", () => {
    const draft = emptyOnScreen();
    draft.captions = [
      { id: "1", text: "one", box_ids: ["middle"] },
      { id: "2", text: "two", box_ids: ["middle"] },
    ];
    expect(projectFromDraft(draft)).toBe("Each box locks to one line.");
  });
});
