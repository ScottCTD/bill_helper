import { useEffect, useRef } from "react";
import type { PartialBlock } from "@blocknote/core";
import { BlockNoteView } from "@blocknote/ariakit";
import { useCreateBlockNote } from "@blocknote/react";

import "@blocknote/core/fonts/inter.css";
import "@blocknote/ariakit/style.css";

interface MarkdownBlockEditorProps {
  markdown: string;
  resetKey: string;
  disabled?: boolean;
  onChange: (markdown: string) => void;
}

function toDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith("image/")) {
      reject(new Error("Only image files are supported."));
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }
      reject(new Error("Unable to read file."));
    };
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read file."));
    reader.readAsDataURL(file);
  });
}

export function MarkdownBlockEditor({ markdown, resetKey, disabled, onChange }: MarkdownBlockEditorProps) {
  const isHydratingRef = useRef(false);
  const hydratedKeyRef = useRef<string>("");
  const editor = useCreateBlockNote({
    uploadFile: toDataUrl
  });

  useEffect(() => {
    if (hydratedKeyRef.current === resetKey) {
      return;
    }
    hydratedKeyRef.current = resetKey;
    isHydratingRef.current = true;
    if (markdown.trim().length > 0) {
      editor.replaceBlocks(editor.document, editor.tryParseMarkdownToBlocks(markdown));
    } else {
      editor.replaceBlocks(editor.document, [{ type: "paragraph" }] as PartialBlock[]);
    }
    isHydratingRef.current = false;
  }, [editor, markdown, resetKey]);

  return (
    <div className="entry-editor-blocknote">
      <BlockNoteView
        editor={editor}
        editable={!disabled}
        onChange={() => {
          if (isHydratingRef.current) {
            return;
          }
          onChange(editor.blocksToMarkdownLossy(editor.document));
        }}
      />
    </div>
  );
}
