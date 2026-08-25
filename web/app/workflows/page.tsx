"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { WorkflowsPanel } from "@/components/workflows/WorkflowsPanel";
import { workflowPageBlurb } from "@/lib/workflowCopy";
import { Workflow } from "lucide-react";
import { useAuthMe } from "@/lib/useAuthMe";
import { showWorkflowsNav } from "@/lib/navAccess";

export default function WorkflowsPage() {
  const router = useRouter();
  const { data: me, isLoading } = useAuthMe();
  const allowed = showWorkflowsNav(me);

  useEffect(() => {
    if (isLoading) return;
    if (!allowed) router.replace("/");
  }, [isLoading, allowed, router]);

  if (isLoading || !allowed) {
    return (
      <main className="workflow-page">
        <div style={{ color: "var(--color-muted)", fontSize: 13 }}>
          {isLoading ? "Loading…" : "Workflows are on Pro and Agency."}
        </div>
      </main>
    );
  }

  return (
    <main className="workflow-page">
      <div className="workspace-heading">
        <span className="workspace-heading__icon"><Workflow size={19} /></span>
        <div>
          <p className="workspace-heading__eyebrow">Automation</p>
          <h1>Workflows</h1>
          <p className="workspace-heading__copy">{workflowPageBlurb()}</p>
        </div>
      </div>
      <div>
        <WorkflowsPanel />
      </div>
    </main>
  );
}
