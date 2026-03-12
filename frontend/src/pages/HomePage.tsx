import { PageHeader } from "../components/layout/PageHeader";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { AgentPanel } from "../features/agent/AgentPanel";

export function HomePage() {
  return (
    <div className="page stack-lg agent-page">
      <PageHeader
        title="Agent Workspace"
        description="Threads, attachments, and review."
      />
      <WorkspaceSection className="agent-workspace-shell" contentClassName="agent-workspace-shell-body">
        <AgentPanel isOpen embedded />
      </WorkspaceSection>
    </div>
  );
}
