import { WorkflowsPanel } from "@/components/workflows/WorkflowsPanel";
import { workflowPageBlurb } from "@/lib/workflowCopy";
import { Workflow } from "lucide-react";

export default function WorkflowsPage() {
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
      <WorkflowsPanel />
    </main>
  );
}
