import { DestinationsPanel } from "@/components/drive/DestinationsPanel";

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
          </div>
        </div>
      </div>

      <div style={{ padding: "14px 20px 22px" }}>
        <DestinationsPanel />
      </div>
    </main>
  );
}
