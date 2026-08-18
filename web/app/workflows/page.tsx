import { WorkflowsPanel } from "@/components/workflows/WorkflowsPanel";
import { workflowPageBlurb } from "@/lib/workflowCopy";

export default function WorkflowsPage() {
  return (
    <main style={{ minHeight: "100vh" }}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: 14,
          padding: "18px 20px 4px",
        }}
      >
        <div>
          <div style={{ fontSize: 16, fontWeight: 800, color: "var(--color-text)" }}>Workflows</div>
          <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2, maxWidth: 560, lineHeight: 1.45 }}>
            {workflowPageBlurb()}
          </div>
        </div>
      </div>

      <div style={{ padding: "14px 20px 22px" }}>
        <WorkflowsPanel />
      </div>
    </main>
  );
}
