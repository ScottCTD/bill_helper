/**
 * CALLING SPEC:
 * - Purpose: render the `PropertiesPage` React UI module.
 * - Inputs: callers that import `frontend/src/pages/PropertiesPage.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `PropertiesPage`.
 * - Side effects: React rendering and user event wiring.
 */
import { PageHeader } from "../components/layout/PageHeader";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { PropertiesSectionContent } from "../features/properties/PropertiesSectionContent";
import { PropertiesSectionNavigation } from "../features/properties/PropertiesSectionNavigation";
import { usePropertiesPageModel } from "../features/properties/usePropertiesPageModel";

export function PropertiesPage() {
  const model = usePropertiesPageModel();

  return (
    <div className="page stack-lg">
      <PageHeader
        title="Property Databases"
        description="Users, currencies, tags, and taxonomy."
      />

      <WorkspaceSection>
        {model.queries.taxonomiesQuery.isError ? <p className="error">{(model.queries.taxonomiesQuery.error as Error).message}</p> : null}

        <div className="properties-layout">
          <PropertiesSectionNavigation
            activeSection={model.activeSection}
            onSelectSection={model.setActiveSection}
            coreSections={model.coreSections}
            taxonomySections={model.taxonomySections}
          />

          <section className="properties-panel">
            <PropertiesSectionContent model={model} />
          </section>
        </div>
      </WorkspaceSection>
    </div>
  );
}
