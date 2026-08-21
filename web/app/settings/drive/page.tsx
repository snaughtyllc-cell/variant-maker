import { DestinationsPanel } from "@/components/drive/DestinationsPanel";
import { CaptionBankPanel } from "@/components/drive/CaptionBankPanel";
import { DropLedgerPanel } from "@/components/drive/DropLedgerPanel";
import { DriveLoginNote } from "@/components/auth/DriveLoginNote";
import { PasswordPanel } from "@/components/auth/PasswordPanel";

export default function DriveSettingsPage() {
  return (
    <main style={{ minHeight: "100vh" }}>
      {/* Page header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: 14,
          padding: "18px 20px 4px",
        }}
      >
        <div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 800,
              color: "var(--color-text)",
            }}
          >
            Drive destinations
          </div>
          <div
            style={{
              fontSize: 12,
              color: "var(--color-muted)",
              marginTop: 2,
            }}
          >
            Manage the Google Drive folders variants can be exported to. Studio import and Workflows use the same saved folders.
            <DriveLoginNote />
          </div>
        </div>
      </div>

      <div style={{ padding: "14px 20px 22px" }}>
        <PasswordPanel />
        <DestinationsPanel />
        <div style={{ height: 28 }} />
        <CaptionBankPanel />
        <div style={{ height: 28 }} />
        <DropLedgerPanel />
      </div>
    </main>
  );
}
