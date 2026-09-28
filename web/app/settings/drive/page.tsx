import { DestinationsPanel } from "@/components/drive/DestinationsPanel";
import { DriveTopbar } from "@/components/drive/DriveTopbar";
import { DropLedgerPanel } from "@/components/drive/DropLedgerPanel";
import { DriveLoginNote } from "@/components/auth/DriveLoginNote";
import { PasswordPanel } from "@/components/auth/PasswordPanel";
import { InstagramPanel } from "@/components/InstagramPanel";

export default function DriveSettingsPage() {
  return (
    <main className="drive-shell">
      {/* Own 58px context bar — the integrator suppresses the global desktop
          header on this route so this is the only breadcrumb bar. */}
      <DriveTopbar />

      {/* Two numbered steps + a destinations table fill the left column; Drop
          Ledger, account and a workspace-vs-login callout stack in a fixed 340px
          right column at desktop widths. Below 900px everything stacks in one
          column and the phone chrome around it is untouched. */}
      <div className="drive-scroll">
        <div className="drive-body">
          <div className="drive-head">
            <p className="drive-head__eyebrow">Delivery setup</p>
            <h1 className="drive-head__title">Drive</h1>
          </div>

          <DestinationsPanel />

          <div className="drive-slot-ig">
            <InstagramPanel />
          </div>

          <DropLedgerPanel />
          <div className="drive-slot-password">
            <PasswordPanel />
          </div>
          <div className="drive-slot-callout drive-callout">
            <span className="material-symbols-rounded" aria-hidden="true">info</span>
            <DriveLoginNote />
          </div>
        </div>
      </div>
    </main>
  );
}
