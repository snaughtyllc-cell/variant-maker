import { DestinationsPanel } from "@/components/drive/DestinationsPanel";
import { CaptionBankPanel } from "@/components/drive/CaptionBankPanel";
import { DropLedgerPanel } from "@/components/drive/DropLedgerPanel";
import { DriveLoginNote } from "@/components/auth/DriveLoginNote";
import { PasswordPanel } from "@/components/auth/PasswordPanel";
import { Cloud } from "lucide-react";

export default function DriveSettingsPage() {
  return (
    <main className="drive-page">
      <div className="workspace-heading">
        <span className="workspace-heading__icon"><Cloud size={19} /></span>
        <div>
          <p className="workspace-heading__eyebrow">Delivery setup</p>
          <h1>Drive</h1>
          <div className="workspace-heading__copy">
            Share the VaryForge Drive email with your folder, paste the link, then set captions and Drop Ledger.
            <DriveLoginNote />
          </div>
        </div>
      </div>
      <div>
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
