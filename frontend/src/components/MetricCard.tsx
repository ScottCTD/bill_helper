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
