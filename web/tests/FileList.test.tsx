import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { FileList } from "@/components/studio/FileList";

beforeAll(() => {
  if (!URL.createObjectURL) {
    URL.createObjectURL = vi.fn(() => "blob:file-thumb");
  }
  if (!URL.revokeObjectURL) {
    URL.revokeObjectURL = vi.fn();
  }
});

describe("FileList thumbs", () => {
  it("shows a video thumbnail for each local source", () => {
    const file = new File(["x"], "gym.mp4", { type: "video/mp4" });
    render(<FileList files={[file]} durations={[12]} onRemove={() => {}} />);
    expect(screen.getByText("gym.mp4")).toBeInTheDocument();
    expect(screen.getByLabelText("gym.mp4 thumbnail")).toBeInTheDocument();
    expect(document.querySelector(".studio-clip-card video")).toBeTruthy();
  });
});
