import { useEffect, useState } from "react";

import type { GroupType } from "../lib/types";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";
import { Input } from "./ui/input";
import { NativeSelect } from "./ui/native-select";

const GROUP_TYPE_OPTIONS: GroupType[] = ["BUNDLE", "SPLIT", "RECURRING"];

interface GroupEditorModalProps {
  isOpen: boolean;
  mode: "create" | "rename";
  initialName?: string;
  initialGroupType?: GroupType;
  isSaving: boolean;
  saveError?: string | null;
  onClose: () => void;
  onSubmit: (payload: { name: string; group_type: GroupType }) => void;
}

export function GroupEditorModal({
  isOpen,
  mode,
  initialName = "",
  initialGroupType = "BUNDLE",
  isSaving,
  saveError = null,
  onClose,
  onSubmit
}: GroupEditorModalProps) {
  const [name, setName] = useState(initialName);
  const [groupType, setGroupType] = useState<GroupType>(initialGroupType);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setName(initialName);
    setGroupType(initialGroupType);
    setFormError(null);
  }, [initialGroupType, initialName, isOpen]);

  function submit() {
    const normalizedName = name.trim();
    if (!normalizedName) {
      setFormError("Group name is required.");
      return;
    }
    setFormError(null);
    onSubmit({ name: normalizedName, group_type: groupType });
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "Create Group" : "Rename Group"}</DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "Create an empty typed group now and add members afterwards."
              : "Rename this group without changing its type."}
          </DialogDescription>
        </DialogHeader>

        <div className="stack-sm">
          <label className="field min-w-0">
            <span>Name</span>
            <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Monthly bills" />
          </label>

          <label className="field min-w-0">
            <span>Type</span>
            <NativeSelect
              value={groupType}
              onChange={(event) => setGroupType(event.target.value as GroupType)}
              disabled={mode === "rename"}
            >
              {GROUP_TYPE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </NativeSelect>
          </label>

          {formError ? <p className="error">{formError}</p> : null}
          {saveError ? <p className="error">{saveError}</p> : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button type="button" onClick={submit} disabled={isSaving}>
            {isSaving ? "Saving..." : mode === "create" ? "Create group" : "Rename group"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
