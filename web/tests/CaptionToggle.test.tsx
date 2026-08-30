import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CaptionToggle } from "@/components/studio/CaptionToggle";

describe("CaptionToggle", () => {
  it("is a Captions setup section with Write captions for these copies on by default", () => {
    render(<CaptionToggle checked onChange={vi.fn()} />);
    expect(screen.getByRole("region", { name: /3 · captions/i })).toBeInTheDocument();
    const box = screen.getByRole("checkbox", { name: /write captions for these copies/i });
    expect(box).toBeChecked();
    expect(screen.getByText(/gallery/i)).toBeInTheDocument();
  });

  it("toggles off when the operator unchecks it", () => {
    const onChange = vi.fn();
    render(<CaptionToggle checked onChange={onChange} />);
    fireEvent.click(screen.getByRole("checkbox", { name: /write captions/i }));
    expect(onChange).toHaveBeenCalledWith(false);
  });
});
