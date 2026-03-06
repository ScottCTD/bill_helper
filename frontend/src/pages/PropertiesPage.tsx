import { Card, CardContent } from "../components/ui/card";
import { PropertiesSectionContent } from "../features/properties/PropertiesSectionContent";
import { PropertiesSectionNavigation } from "../features/properties/PropertiesSectionNavigation";
import { usePropertiesPageModel } from "../features/properties/usePropertiesPageModel";

export function PropertiesPage() {
  const model = usePropertiesPageModel();

  return (
    <div className="stack-lg">
      <Card>
        <CardContent className="space-y-5 pt-6">
          <div className="space-y-1.5">
            <h2 className="text-xl font-semibold">Property Databases</h2>
            <p className="muted">
              Manage core catalogs and taxonomy terms from one workspace. Category pickers for entities and type pickers for tags
              are driven by taxonomy terms.
            </p>
            {model.queries.taxonomiesQuery.isError ? <p className="error">{(model.queries.taxonomiesQuery.error as Error).message}</p> : null}
          </div>

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
        </CardContent>
      </Card>
    </div>
  );
}
