/**
 * CALLING SPEC:
 * - Purpose: render the `PropertiesSectionNavigation` React UI module.
 * - Inputs: callers that import `frontend/src/features/properties/PropertiesSectionNavigation.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `PropertiesSectionNavigation`.
 * - Side effects: React rendering and user event wiring.
 */
import { Button } from "../../components/ui/button";
import type { PropertiesSectionId } from "./types";

interface SectionDescriptor {
  id: PropertiesSectionId;
  label: string;
}

interface PropertiesSectionNavigationProps {
  activeSection: PropertiesSectionId;
  onSelectSection: (sectionId: PropertiesSectionId) => void;
  coreSections: readonly SectionDescriptor[];
  taxonomySections: readonly SectionDescriptor[];
}

function SectionGroup({
  label,
  sections,
  activeSection,
  onSelectSection
}: {
  label: string;
  sections: readonly SectionDescriptor[];
  activeSection: PropertiesSectionId;
  onSelectSection: (sectionId: PropertiesSectionId) => void;
}) {
  return (
    <section className="properties-nav-group">
      <p className="properties-nav-label">{label}</p>
      <div className="properties-nav-list">
        {sections.map((section) => (
          <Button
            key={section.id}
            type="button"
            size="sm"
            variant={activeSection === section.id ? "secondary" : "ghost"}
            className="properties-nav-button"
            onClick={() => onSelectSection(section.id)}
          >
            {section.label}
          </Button>
        ))}
      </div>
    </section>
  );
}

export function PropertiesSectionNavigation({
  activeSection,
  onSelectSection,
  coreSections,
  taxonomySections
}: PropertiesSectionNavigationProps) {
  return (
    <nav className="properties-nav" aria-label="Property sections">
      <SectionGroup
        label="Core"
        sections={coreSections}
        activeSection={activeSection}
        onSelectSection={onSelectSection}
      />
      <SectionGroup
        label="Taxonomies"
        sections={taxonomySections}
        activeSection={activeSection}
        onSelectSection={onSelectSection}
      />
    </nav>
  );
}
