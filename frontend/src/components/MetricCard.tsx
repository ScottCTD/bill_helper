/**
 * CALLING SPEC:
 * - Purpose: render the `MetricCard` React UI module.
 * - Inputs: callers that import `frontend/src/components/MetricCard.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `MetricCard`.
 * - Side effects: React rendering and user event wiring.
 */
import { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface MetricCardProps {
  title: string;
  children: ReactNode;
}

export function MetricCard({ title, children }: MetricCardProps) {
  return (
    <Card className="metric-card h-full">
      <CardHeader className="pb-3">
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
