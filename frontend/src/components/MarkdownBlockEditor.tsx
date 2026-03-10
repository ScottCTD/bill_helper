import { Component, Suspense, lazy } from "react";

import { Textarea } from "./ui/textarea";

interface MarkdownBlockEditorProps {
  markdown: string;
  resetKey: string;
  disabled?: boolean;
  onChange: (markdown: string) => void;
}

const LazyMarkdownBlockEditorImpl = lazy(async () => {
  const module = await import("./MarkdownBlockEditorImpl");
  return { default: module.MarkdownBlockEditorImpl };
});

const IS_DEV = import.meta.env.DEV;

interface MarkdownTextareaFallbackProps extends Omit<MarkdownBlockEditorProps, "resetKey"> {
  mode: "loading" | "error";
  errorMessage?: string | null;
}

function MarkdownTextareaFallback({
  markdown,
  disabled,
  onChange,
  mode,
  errorMessage = null
}: MarkdownTextareaFallbackProps) {
  return (
    <div className="grid gap-2">
      {mode === "loading" ? (
        <p className="text-xs text-muted-foreground">Loading rich markdown editor...</p>
      ) : IS_DEV ? (
        <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
          <p className="font-medium text-foreground">Rich markdown editor failed to load.</p>
          <p className="mt-1 text-muted-foreground">
            Dev mode kept the plain textarea active so the form stays usable while surfacing the runtime error.
          </p>
          {errorMessage ? <pre className="mt-2 whitespace-pre-wrap break-words text-xs text-muted-foreground">{errorMessage}</pre> : null}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">Rich markdown editor unavailable. Using plain text fallback.</p>
      )}
      <Textarea
        aria-label="Markdown"
        className="min-h-56"
        value={markdown}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

interface MarkdownBlockEditorBoundaryProps extends MarkdownBlockEditorProps {
  children: React.ReactNode;
}

interface MarkdownBlockEditorBoundaryState {
  hasError: boolean;
  errorMessage: string | null;
}

class MarkdownBlockEditorBoundary extends Component<
  MarkdownBlockEditorBoundaryProps,
  MarkdownBlockEditorBoundaryState
> {
  state: MarkdownBlockEditorBoundaryState = {
    hasError: false,
    errorMessage: null
  };

  static getDerivedStateFromError(): MarkdownBlockEditorBoundaryState {
    return { hasError: true, errorMessage: null };
  }

  componentDidCatch(error: Error) {
    console.error("MarkdownBlockEditor failed to load; falling back to textarea.", error);
    this.setState({ errorMessage: error.message });
  }

  componentDidUpdate(prevProps: MarkdownBlockEditorBoundaryProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false, errorMessage: null });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <MarkdownTextareaFallback
          markdown={this.props.markdown}
          disabled={this.props.disabled}
          onChange={this.props.onChange}
          mode="error"
          errorMessage={this.state.errorMessage}
        />
      );
    }

    return this.props.children;
  }
}

export function MarkdownBlockEditor(props: MarkdownBlockEditorProps) {
  return (
    <MarkdownBlockEditorBoundary {...props}>
      <Suspense
        fallback={
          <MarkdownTextareaFallback
            markdown={props.markdown}
            disabled={props.disabled}
            onChange={props.onChange}
            mode="loading"
          />
        }
      >
        <LazyMarkdownBlockEditorImpl {...props} />
      </Suspense>
    </MarkdownBlockEditorBoundary>
  );
}
