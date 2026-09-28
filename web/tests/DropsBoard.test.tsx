import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { DropsBoard } from "@/components/drops/DropsBoard";
import { DROPS_EMPTY_COPY } from "@/lib/drops";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

const listDriveExports = vi.fn();
vi.mock("@/lib/api", () => ({
  listDriveExports: (...args: unknown[]) => listDriveExports(...args),
}));

beforeEach(() => {
  listDriveExports.mockReset();
});

describe("DropsBoard", () => {
  it("shows the empty send-to-Drive copy", async () => {
    listDriveExports.mockResolvedValue([]);
    render(<DropsBoard filter={null} />);
    expect(await screen.findByText(DROPS_EMPTY_COPY)).toBeInTheDocument();
  });

  it("lists destination, send day, count, and variant id — not a caption filename", async () => {
    listDriveExports.mockResolvedValue([
      {
        export_id: "exp_1",
        created_utc: "2026-08-21T10:00:00Z",
        destination_id: "dst_a",
        destination_name: "LOGAN REPURPOSE 1",
        folder_id: "fld",
        count: 2,
        outcome: "miss",
        miss_labels: ["flagged"],
        files: [
          {
            source_id: "s1", index: 1, variant_id: "s1:1", job_id: "j1",
            drive_file_id: "drv1", platform_result: "flagged", outcome: "miss",
          },
          {
            source_id: "s1", index: 2, variant_id: "s1:2", job_id: "j1",
            drive_file_id: "drv2", platform_result: null, outcome: "pass",
          },
        ],
      },
    ]);
    const { container } = render(<DropsBoard filter={null} />);
    expect(await screen.findByText("LOGAN REPURPOSE 1")).toBeInTheDocument();
    expect(screen.getByText(/2026-08-21/)).toBeInTheDocument();
    expect(screen.getByText(/2 files/)).toBeInTheDocument();
    expect(screen.getByText("Flagged")).toBeInTheDocument();
    expect(container.textContent).toContain("s1:1");
    expect(container.textContent).not.toMatch(/POV|#reels|\.mp4/);
    await waitFor(() => expect(listDriveExports).toHaveBeenCalled());
  });
});
