# Double-Click to Edit for All Tables

**Created:** 2026-03-07

## Overview

Enable double-click to open edit modals for all table entities (accounts, entities, tags, users), matching the existing behavior for entries. This removes the need for explicit Edit buttons in these tables.

## Current Behavior

- **Entries** (`[EntriesPage.tsx:297](frontend/src/pages/EntriesPage.tsx:297)`): Double-click on a row opens the edit modal via `onDoubleClick={() => setEditorState({ mode: "edit", entryId: entry.id })}`
- **Accounts** (`[AccountsTableSection.tsx:113-123](frontend/src/features/accounts/AccountsTableSection.tsx:113-123)`): Has explicit Edit button, no double-click
- **Entities** (`[EntitiesSection.tsx:137-139](frontend/src/features/properties/sections/EntitiesSection.tsx:137-139)`): Has explicit Edit button, no double-click
- **Tags** (`[TagsSection.tsx:164-166](frontend/src/features/properties/sections/TagsSection.tsx:164-166)`): Has explicit Edit button, no double-click
- **Users** (`[UsersSection.tsx:117-119](frontend/src/features/properties/sections/UsersSection.tsx:117-119)`): Has explicit Edit button, no double-click

## Changes Required

### 1. Add Double-Click to Accounts Table

Add `onDoubleClick` handler to the `[TableRow](frontend/src/features/accounts/AccountsTableSection.tsx:89-137)` in AccountsTableSection to trigger the edit dialog.

- **Location:** `[AccountsTableSection.tsx:89-94](frontend/src/features/accounts/AccountsTableSection.tsx:89-94)`
- **Add:** `onDoubleClick={() => onEditAccount(account.id)}`

### 2. Add Double-Click to Entities Table

Add `onDoubleClick` handler to the `[TableRow](frontend/src/features/properties/sections/EntitiesSection.tsx:132-145)` in EntitiesSection to trigger the edit dialog.

- **Location:** `[EntitiesSection.tsx:132](frontend/src/features/properties/sections/EntitiesSection.tsx:132)`
- **Add:** `onDoubleClick={() => onStartEditEntity(entity)}`

### 3. Add Double-Click to Tags Table

Add `onDoubleClick` handler to the `[TableRow](frontend/src/features/properties/sections/TagsSection.tsx:153-172)` in TagsSection to trigger the edit dialog.

- **Location:** `[TagsSection.tsx:153](frontend/src/features/properties/sections/TagsSection.tsx:153)`
- **Add:** `onDoubleClick={() => onStartEditTag(tag)}`

### 4. Add Double-Click to Users Table

Add `onDoubleClick` handler to the `[TableRow](frontend/src/features/properties/sections/UsersSection.tsx:111-121)` in UsersSection to trigger the edit dialog.

- **Location:** `[UsersSection.tsx:111](frontend/src/features/properties/sections/UsersSection.tsx:111)`
- **Add:** `onDoubleClick={() => onStartEditUser(user)}`

### 5. Remove Edit Buttons from Accounts Table

Remove the Edit button from the actions column since double-click now provides this functionality.

- **Location:** `[AccountsTableSection.tsx:111-135](frontend/src/features/accounts/AccountsTableSection.tsx:111-135)`
- **Remove:** Edit button (lines 113-123), keep Delete button

### 6. Remove Edit Buttons from Entities Table

Remove the Edit button from the actions column.

- **Location:** `[EntitiesSection.tsx:135-144](frontend/src/features/properties/sections/EntitiesSection.tsx:135-144)`
- **Remove:** Edit button (lines 137-139), keep Delete button

### 7. Remove Edit Buttons from Tags Table

Remove the Edit button from the actions column.

- **Location:** `[TagsSection.tsx:162-171](frontend/src/features/properties/sections/TagsSection.tsx:162-171)`
- **Remove:** Edit button (lines 164-166), keep Delete button

### 8. Remove Edit Button from Users Table

Remove the Edit button from the actions column.

- **Location:** `[UsersSection.tsx:116-120](frontend/src/features/properties/sections/UsersSection.tsx:116-120)`
- **Remove:** Edit button (lines 117-119)

## Affected Files


| File                                                            | Changes                                      |
| --------------------------------------------------------------- | -------------------------------------------- |
| `frontend/src/features/accounts/AccountsTableSection.tsx`       | Add double-click handler, remove Edit button |
| `frontend/src/features/properties/sections/EntitiesSection.tsx` | Add double-click handler, remove Edit button |
| `frontend/src/features/properties/sections/TagsSection.tsx`     | Add double-click handler, remove Edit button |
| `frontend/src/features/properties/sections/UsersSection.tsx`    | Add double-click handler, remove Edit button |


## Notes

- The EntriesPage already demonstrates the intended UX pattern - double-click to edit
- Delete buttons should remain as they require explicit confirmation and are distinct from editing
- Consider adding `cursor-pointer` class to table rows to indicate the double-click action is available
- The `onClick` handler on accounts table row should call `onSelectAccount`, but double-click should call `onEditAccount`. Ensure proper event handling to avoid conflicts

