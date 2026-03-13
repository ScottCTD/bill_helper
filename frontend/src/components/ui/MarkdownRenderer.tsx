/**
 * CALLING SPEC:
 * - Purpose: render the `MarkdownRenderer` React UI module.
 * - Inputs: callers that import `frontend/src/components/ui/MarkdownRenderer.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `MarkdownRenderer`.
 * - Side effects: React rendering and user event wiring.
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "../../lib/utils";

interface MarkdownRendererProps {
  markdown: string;
  className?: string;
}

function isExternalHref(href: string): boolean {
  return /^https?:\/\//i.test(href);
}

export function MarkdownRenderer({ markdown, className }: MarkdownRendererProps) {
  return (
    <div className={cn("agent-markdown", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, ...props }) => {
            const safeHref = href || "";
            return (
              <a
                {...props}
                href={safeHref}
                rel={isExternalHref(safeHref) ? "noreferrer noopener" : undefined}
                target={isExternalHref(safeHref) ? "_blank" : undefined}
              />
            );
          }
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
