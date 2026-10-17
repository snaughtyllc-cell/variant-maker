import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const health: { lab?: boolean } = {};

vi.mock("@/lib/api", () => ({
  getHealth: async () => ({ status: "ok", lab: health.lab }),
}));

import { LabBanner } from "@/components/nav/LabBanner";

describe("LabBanner", () => {
  it("is hidden on live Studio", async () => {
    health.lab = false;
    const { container } = render(<LabBanner />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("warns when VARIANT_LAB is on", async () => {
    health.lab = true;
    render(<LabBanner />);
    expect(await screen.findByRole("status")).toHaveTextContent(/LAB/);
    expect(screen.getByRole("status").textContent).toMatch(/Team Studio/);
  });
});
