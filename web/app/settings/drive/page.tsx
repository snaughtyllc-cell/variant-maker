import { DestinationsPanel } from "@/components/drive/DestinationsPanel";
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
            Share the varimo Drive email with your folder, paste the link, then add destinations and Drop Ledger.
            Captions are written from Studio Generate.
          </div>
        </div>
      </div>

      {/* Two numbered steps + a destinations table on the left; Drop Ledger,
          account and a workspace-vs-login callout in a fixed right column at
          desktop widths. Below 900px everything stacks in one column and the
          phone chrome around it is untouched. */}
      <div className="drive-body">
        <DestinationsPanel />
        <DropLedgerPanel />
        <div className="drive-slot-password">
          <PasswordPanel />
        </div>
        <div className="drive-slot-callout drive-callout">
          <span className="material-symbols-rounded" aria-hidden="true">info</span>
          <DriveLoginNote />
        </div>
      </div>
    </main>
  );
}
