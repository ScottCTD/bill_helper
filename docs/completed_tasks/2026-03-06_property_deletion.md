# Property Deletion Implementation

## Status: In Progress

## Overview

Properties (entities and tags) are currently not deletable from the frontend UI. This plan adds delete functionality to the Properties page.

**Key constraint**: When an entity is deleted, entries preserve the denormalized entity name text, but the UI should indicate the entity no longer exists.

## Scope


| Property | Included? | Notes                                          |
| -------- | --------- | ---------------------------------------------- |
| Entities | Yes       | From Properties page                           |
| Tags     | Yes       | From Properties page                           |
| Accounts | No        | Accounts deleted separately from Accounts page |


## Database Behavior (Already Configured)

### Entities

- `Entry.from_entity_id` / `to_entity_id`: `ondelete="SET NULL"`
- `Entry.from_entity` / `to_entity`: Denormalized text preserved
- `Account.entity_id`: `ondelete="SET NULL"`

### Tags

- `EntryTag.tag_id`: `ondelete="CASCADE"` (junction records auto-deleted)
- Entries unaffected

## Safety Rules


| Property | Blocking Condition      | Warning Shown |
| -------- | ----------------------- | ------------- |
| Entity   | Has associated accounts | Has entries   |
| Tag      | None                    | Has entries   |


## Implementation Checklist

### Backend

- `backend/routers/entities.py` - Add DELETE endpoint with account blocking
- `backend/routers/tags.py` - Add DELETE endpoint

### Frontend

- `frontend/src/lib/api.ts` - Add deleteEntity, deleteTag functions
- `frontend/src/components/DeleteConfirmDialog.tsx` - New component
- `frontend/src/features/properties/usePropertiesPageModel.ts` - Add mutations
- `frontend/src/features/properties/usePropertiesFormState.ts` - Add delete state
- `frontend/src/features/properties/sections/EntitiesSection.tsx` - Add delete UI
- `frontend/src/features/properties/sections/TagsSection.tsx` - Add delete UI

## Notes

- Deleted entity indicator in entry display is out of scope for initial implementation
- Entity deletion blocked if entity has associated accounts (409 Conflict)
- Tag deletion always succeeds (cascades to entry_tag junction table)

