import { useState } from "react";

export function usePropertiesFormState() {
  const [newEntityName, setNewEntityName] = useState("");
  const [newEntityCategory, setNewEntityCategory] = useState("");
  const [editingEntityId, setEditingEntityId] = useState("");
  const [editingEntityName, setEditingEntityName] = useState("");
  const [editingEntityCategory, setEditingEntityCategory] = useState("");

  const [newTagName, setNewTagName] = useState("");
  const [newTagCategory, setNewTagCategory] = useState("");
  const [newTagColor, setNewTagColor] = useState("");
  const [editingTagId, setEditingTagId] = useState<number | null>(null);
  const [editingTagName, setEditingTagName] = useState("");
  const [editingTagCategory, setEditingTagCategory] = useState("");
  const [editingTagColor, setEditingTagColor] = useState("");

  const [newUserName, setNewUserName] = useState("");
  const [editingUserId, setEditingUserId] = useState("");
  const [editingUserName, setEditingUserName] = useState("");

  const [newEntityCategoryTermName, setNewEntityCategoryTermName] = useState("");
  const [editingEntityCategoryTermId, setEditingEntityCategoryTermId] = useState("");
  const [editingEntityCategoryTermName, setEditingEntityCategoryTermName] = useState("");

  const [newTagCategoryTermName, setNewTagCategoryTermName] = useState("");
  const [editingTagCategoryTermId, setEditingTagCategoryTermId] = useState("");
  const [editingTagCategoryTermName, setEditingTagCategoryTermName] = useState("");

  return {
    newEntityName,
    setNewEntityName,
    newEntityCategory,
    setNewEntityCategory,
    editingEntityId,
    setEditingEntityId,
    editingEntityName,
    setEditingEntityName,
    editingEntityCategory,
    setEditingEntityCategory,
    newTagName,
    setNewTagName,
    newTagCategory,
    setNewTagCategory,
    newTagColor,
    setNewTagColor,
    editingTagId,
    setEditingTagId,
    editingTagName,
    setEditingTagName,
    editingTagCategory,
    setEditingTagCategory,
    editingTagColor,
    setEditingTagColor,
    newUserName,
    setNewUserName,
    editingUserId,
    setEditingUserId,
    editingUserName,
    setEditingUserName,
    newEntityCategoryTermName,
    setNewEntityCategoryTermName,
    editingEntityCategoryTermId,
    setEditingEntityCategoryTermId,
    editingEntityCategoryTermName,
    setEditingEntityCategoryTermName,
    newTagCategoryTermName,
    setNewTagCategoryTermName,
    editingTagCategoryTermId,
    setEditingTagCategoryTermId,
    editingTagCategoryTermName,
    setEditingTagCategoryTermName
  };
}
