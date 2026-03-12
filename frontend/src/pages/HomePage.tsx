import { PageHeader } from "../components/layout/PageHeader";
import { AgentPanel } from "../features/agent/AgentPanel";

export function HomePage() {
  return (
    <div className="page stack-lg agent-page">
      <PageHeader
        title="Agent Workspace"
        description="Threads, attachments, and review."
      />
      <AgentPanel isOpen />
    </div>
  );
}
