import { useState } from "react";

export function usePropertiesFormState() {
  const [newEntityName, setNewEntityName] = useState("");
  const [newEntityCategory, setNewEntityCategory] = useState("");
  const [editingEntityId, setEditingEntityId] = useState("");
  const [editingEntityName, setEditingEntityName] = useState("");
  const [editingEntityCategory, setEditingEntityCategory] = useState("");
  const [deletingEntityId, setDeletingEntityId] = useState("");

  const [newTagName, setNewTagName] = useState("");
  const [newTagType, setNewTagType] = useState("");
  const [newTagColor, setNewTagColor] = useState("");
  const [newTagDescription, setNewTagDescription] = useState("");
  const [editingTagId, setEditingTagId] = useState<number | null>(null);
  const [editingTagName, setEditingTagName] = useState("");
  const [editingTagType, setEditingTagType] = useState("");
  const [editingTagColor, setEditingTagColor] = useState("");
  const [editingTagDescription, setEditingTagDescription] = useState("");
  const [deletingTagId, setDeletingTagId] = useState<number | null>(null);

  const [newUserName, setNewUserName] = useState("");
  const [editingUserId, setEditingUserId] = useState("");
  const [editingUserName, setEditingUserName] = useState("");

  const [newEntityCategoryTermName, setNewEntityCategoryTermName] = useState("");
  const [newEntityCategoryTermDescription, setNewEntityCategoryTermDescription] = useState("");
  const [editingEntityCategoryTermId, setEditingEntityCategoryTermId] = useState("");
  const [editingEntityCategoryTermName, setEditingEntityCategoryTermName] = useState("");
  const [editingEntityCategoryTermDescription, setEditingEntityCategoryTermDescription] = useState("");

  const [newTagTypeTermName, setNewTagTypeTermName] = useState("");
  const [newTagTypeTermDescription, setNewTagTypeTermDescription] = useState("");
  const [editingTagTypeTermId, setEditingTagTypeTermId] = useState("");
  const [editingTagTypeTermName, setEditingTagTypeTermName] = useState("");
  const [editingTagTypeTermDescription, setEditingTagTypeTermDescription] = useState("");

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
    deletingEntityId,
    setDeletingEntityId,
    newTagName,
    setNewTagName,
    newTagType,
    setNewTagType,
    newTagColor,
    setNewTagColor,
    newTagDescription,
    setNewTagDescription,
    editingTagId,
    setEditingTagId,
    editingTagName,
    setEditingTagName,
    editingTagType,
    setEditingTagType,
    editingTagColor,
    setEditingTagColor,
    editingTagDescription,
    setEditingTagDescription,
    deletingTagId,
    setDeletingTagId,
    newUserName,
    setNewUserName,
    editingUserId,
    setEditingUserId,
    editingUserName,
    setEditingUserName,
    newEntityCategoryTermName,
    setNewEntityCategoryTermName,
    newEntityCategoryTermDescription,
    setNewEntityCategoryTermDescription,
    editingEntityCategoryTermId,
    setEditingEntityCategoryTermId,
    editingEntityCategoryTermName,
    setEditingEntityCategoryTermName,
    editingEntityCategoryTermDescription,
    setEditingEntityCategoryTermDescription,
    newTagTypeTermName,
    setNewTagTypeTermName,
    newTagTypeTermDescription,
    setNewTagTypeTermDescription,
    editingTagTypeTermId,
    setEditingTagTypeTermId,
    editingTagTypeTermName,
    setEditingTagTypeTermName,
    editingTagTypeTermDescription,
    setEditingTagTypeTermDescription
  };
}
