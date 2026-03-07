# Entries Table Tags Column - Display Tag Colors

**Created:** 2026-03-07

## Overview

The entries table in [`EntriesPage.tsx`](frontend/src/pages/EntriesPage.tsx:326-337) displays tags without applying their color. The tag style should match how tags are displayed in the tag editor (within the entry edit modal).

## Current Behavior

In the entries table, tags are rendered as plain badges without any color:

```jsx
// EntriesPage.tsx lines 329-332
<Badge key={tag.id} variant="secondary" className="entries-tag-pill">
  {tag.name}
</Badge>
```

This ignores the `color` property available on the `Tag` interface defined in [`types.ts`](frontend/src/lib/types.ts:4-11).

## Expected Behavior

Tags in the entries table should display with their assigned color, matching the style used in [`TagMultiSelect.tsx`](frontend/src/components/TagMultiSelect.tsx:295-296):

- Use the tag's `color` property if available
- Fall back to a generated color based on tag name (using the same `fallbackTagColor` function)
- Display a color indicator (dot or background) similar to the tag editor

## Technical Details

### Tag Interface (from types.ts)

```typescript
export interface Tag {
  id: number;
  name: string;
  color: string | null;  // <-- This property is not being used in entries table
  description?: string | null;
  type?: string | null;
  entry_count?: number | null;
}
```

### Fallback Color Function (from TagMultiSelect.tsx)

```typescript
function fallbackTagColor(tagName: string) {
  let hash = 0;
  for (let index = 0; index < tagName.length; index += 1) {
    hash = (hash * 31 + tagName.charCodeAt(index)) >>> 0;
  }
  const hue = hash % 360;
  return `hsl(${hue} 62% 72%)`;
}
```

### Tag Editor Style (TagMultiSelect.tsx)

Tags in the tag editor display with:
- A colored border: `style={{ borderColor: tag.color ?? undefined }}`
- A color dot: `style={{ backgroundColor: tag.color || "hsl(var(--muted))" }}`

## Changes Required

1. **Import or replicate the `fallbackTagColor` function** in `EntriesPage.tsx`
2. **Update the tag rendering** in the entries table to apply the tag color:
   - Apply background color or border color to match tag editor style
   - Use fallback color when `tag.color` is null

### Location

- Primary: [`EntriesPage.tsx:326-337`](frontend/src/pages/EntriesPage.tsx:326-337)
- Reference: [`TagMultiSelect.tsx:295-296`](frontend/src/components/TagMultiSelect.tsx:295-296)

## Affected Files

| File | Changes |
|------|---------|
| `frontend/src/pages/EntriesPage.tsx` | Import/replicate fallback color function, update tag Badge rendering to apply color |
| `frontend/src/styles.css` | Optional: update `.entries-tag-pill` styles if needed |

## Notes

- The `Tag` type is shared between the entries table and tag editor, so the color information is already available
- The fallback color ensures tags without explicit colors still display distinctly
- Consider whether to use the same visual style (color dot + border) or a simpler background color approach
