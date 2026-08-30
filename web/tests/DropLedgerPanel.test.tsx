import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DropLedgerEnsure, DropLedgerStatus, DropLedgerSync } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getDropLedgerStatus: vi.fn(),
  ensureDropLedger: vi.fn(),
  syncDropLedger: vi.fn(),
}));

import { ensureDropLedger, getDropLedgerStatus, syncDropLedger } from "@/lib/api";
import { DropLedgerPanel } from "@/components/drive/DropLedgerPanel";

const SHEET_URL = "https://docs.google.com/spreadsheets/d/sheet_1";

const notConnected: DropLedgerStatus = {
  configured: false,
  spreadsheet_id: null,
  spreadsheet_url: null,
  message: "Connect Google first (Settings → Drive), then tap Ensure sheet to create VaryForge Drop Ledger",
};

const noSheet: DropLedgerStatus = {
  configured: false,
  spreadsheet_id: null,
  spreadsheet_url: null,
  message: "No sheet yet — tap Ensure sheet to create VaryForge Drop Ledger",
};

const configured: DropLedgerStatus = {
  configured: true,
  spreadsheet_id: "sheet_1",
  spreadsheet_url: SHEET_URL,
  message: "Drop Ledger is ready",
};

const ensured: DropLedgerEnsure = {
  spreadsheet_id: "sheet_1",
  spreadsheet_url: SHEET_URL,
  created: true,
};

const synced: DropLedgerSync = {
  spreadsheet_id: "sheet_1",
  spreadsheet_url: SHEET_URL,
  job_ids: ["j1"],
  rows: 4,
  inserted: 3,
  updated: 1,
  unchanged: 0,
};

beforeEach(() => {
  vi.mocked(getDropLedgerStatus).mockReset();
  vi.mocked(ensureDropLedger).mockReset();
  vi.mocked(syncDropLedger).mockReset();
  vi.mocked(getDropLedgerStatus).mockResolvedValue(noSheet);
  vi.mocked(ensureDropLedger).mockResolvedValue(ensured);
  vi.mocked(syncDropLedger).mockResolvedValue(synced);
});

describe("DropLedgerPanel", () => {
  it("prompts to Connect Google first and disables Ensure sheet / Sync from Studio", async () => {
    vi.mocked(getDropLedgerStatus).mockResolvedValue(notConnected);
    render(<DropLedgerPanel />);
    expect(await screen.findByText(/does not change uniqueness/i)).toBeInTheDocument();
    expect(await screen.findByText(/studio Drive email above first/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ensure sheet" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sync from Studio" })).toBeDisabled();
    expect(screen.queryByRole("link", { name: "Open sheet" })).not.toBeInTheDocument();
  });

  it("creates VaryForge Drop Ledger on Ensure sheet", async () => {
    render(<DropLedgerPanel />);
    const ensure = await screen.findByRole("button", { name: "Ensure sheet" });
    expect(ensure).not.toBeDisabled();
    fireEvent.click(ensure);
    await waitFor(() => {
      expect(ensureDropLedger).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText("Created VaryForge Drop Ledger")).toBeInTheDocument();
    const link = await screen.findByRole("link", { name: "Open sheet" });
    expect(link).toHaveAttribute("href", SHEET_URL);
  });

  it("syncs from Studio and shows the sheet URL", async () => {
    vi.mocked(getDropLedgerStatus).mockResolvedValue(configured);
    render(<DropLedgerPanel />);
    expect(await screen.findByRole("link", { name: "Open sheet" })).toHaveAttribute("href", SHEET_URL);
    fireEvent.click(screen.getByRole("button", { name: "Sync from Studio" }));
    await waitFor(() => {
      expect(syncDropLedger).toHaveBeenCalledWith({ ensure: true });
    });
    expect(
      await screen.findByText(/Synced 4 clips — 3 new, 1 updated, 0 unchanged/),
    ).toBeInTheDocument();
    expect(screen.getByText(/existing labels were kept/i)).toBeInTheDocument();
    expect(screen.getByText(/unlabeled clips count as pass/i)).toBeInTheDocument();
  });
});
