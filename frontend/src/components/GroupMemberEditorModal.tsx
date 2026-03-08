import { useEffect, useMemo, useState } from "react";

import type { GroupMemberRole, GroupType } from "../lib/types";
import { SingleSelect } from "./SingleSelect";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";
import { NativeSelect } from "./ui/native-select";

interface MemberOption {
  id: string;
  label: string;
}

interface GroupMemberEditorModalProps {
  isOpen: boolean;
  groupName: string;
  groupType: GroupType;
  entryOptions: MemberOption[];
  groupOptions: MemberOption[];
  isSaving: boolean;
  saveError?: string | null;
  onClose: () => void;
  onSubmit: (payload: { entry_id?: string; child_group_id?: string; member_role?: GroupMemberRole }) => void;
}

export function GroupMemberEditorModal({
  isOpen,
  groupName,
  groupType,
  entryOptions,
  groupOptions,
  isSaving,
  saveError = null,
  onClose,
  onSubmit
}: GroupMemberEditorModalProps) {
  const [subjectType, setSubjectType] = useState<"ENTRY" | "GROUP">("ENTRY");
  const [selectedId, setSelectedId] = useState("");
  const [memberRole, setMemberRole] = useState<GroupMemberRole>("CHILD");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setSubjectType("ENTRY");
    setSelectedId("");
    setMemberRole(groupType === "SPLIT" ? "CHILD" : "CHILD");
    setFormError(null);
  }, [groupType, isOpen]);

  const selectOptions = useMemo(
    () =>
      (subjectType === "ENTRY" ? entryOptions : groupOptions).map((option) => ({
        value: option.id,
        label: option.label
      })),
    [entryOptions, groupOptions, subjectType]
  );

  function submit() {
    if (!selectedId) {
      setFormError(`Select a ${subjectType === "ENTRY" ? "direct entry" : "child group"}.`);
      return;
    }
    setFormError(null);
    onSubmit(
      subjectType === "ENTRY"
        ? {
            entry_id: selectedId,
            member_role: groupType === "SPLIT" ? memberRole : undefined
          }
        : {
            child_group_id: selectedId,
            member_role: groupType === "SPLIT" ? memberRole : undefined
          }
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Group Member</DialogTitle>
          <DialogDescription>{`Add a direct member to ${groupName}.`}</DialogDescription>
        </DialogHeader>

        <div className="stack-sm">
          <label className="field min-w-0">
            <span>Member type</span>
            <NativeSelect
              value={subjectType}
              onChange={(event) => {
                setSubjectType(event.target.value as "ENTRY" | "GROUP");
                setSelectedId("");
              }}
            >
              <option value="ENTRY">Entry</option>
              <option value="GROUP">Child group</option>
            </NativeSelect>
          </label>

          <label className="field min-w-0">
            <span>{subjectType === "ENTRY" ? "Entry" : "Child group"}</span>
            <SingleSelect
              value={selectedId}
              options={selectOptions}
              placeholder={subjectType === "ENTRY" ? "Select entry..." : "Select group..."}
              searchable
              searchPlaceholder={subjectType === "ENTRY" ? "Search entries..." : "Search groups..."}
              emptyLabel={`No ${subjectType === "ENTRY" ? "entries" : "groups"} available.`}
              onChange={setSelectedId}
            />
          </label>

          {groupType === "SPLIT" ? (
            <label className="field min-w-0">
              <span>Split role</span>
              <NativeSelect value={memberRole} onChange={(event) => setMemberRole(event.target.value as GroupMemberRole)}>
                <option value="PARENT">PARENT</option>
                <option value="CHILD">CHILD</option>
              </NativeSelect>
            </label>
          ) : null}

          {formError ? <p className="error">{formError}</p> : null}
          {saveError ? <p className="error">{saveError}</p> : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button type="button" onClick={submit} disabled={isSaving}>
            {isSaving ? "Saving..." : "Add member"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
