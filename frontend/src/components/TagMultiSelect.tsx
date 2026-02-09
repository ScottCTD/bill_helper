import { KeyboardEvent, PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from "react";

import type { Tag } from "../lib/types";

interface TagMultiSelectProps {
  options: Tag[];
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
}

function normalizeTagName(value: string) {
  return value.trim().toLowerCase();
}

function fallbackTagColor(tagName: string) {
  let hash = 0;
  for (let index = 0; index < tagName.length; index += 1) {
    hash = (hash * 31 + tagName.charCodeAt(index)) >>> 0;
  }
  const hue = hash % 360;
  return `hsl(${hue} 62% 72%)`;
}

function tagColor(name: string, color: string | null | undefined) {
  return color ?? fallbackTagColor(name);
}

function normalizeTagList(values: string[]) {
  const normalizedTags: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const normalized = normalizeTagName(value);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    normalizedTags.push(normalized);
  }
  return normalizedTags;
}

function areTagArraysEqual(left: string[], right: string[]) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function tagExists(values: string[], normalizedTagName: string) {
  return values.some((value) => normalizeTagName(value) === normalizedTagName);
}

function removeFirstTag(values: string[], normalizedTagName: string) {
  const removeIndex = values.findIndex((name) => normalizeTagName(name) === normalizedTagName);
  if (removeIndex < 0) {
    return values;
  }
  return values.filter((_, currentIndex) => currentIndex !== removeIndex);
}

export function TagMultiSelect({ options, value, onChange, placeholder = "Select tags...", disabled = false, ariaLabel }: TagMultiSelectProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const normalizedValue = useMemo(() => normalizeTagList(value), [value]);
  const [selectedValues, setSelectedValues] = useState<string[]>(normalizedValue);
  const selectedValuesRef = useRef<string[]>(selectedValues);
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    selectedValuesRef.current = selectedValues;
  }, [selectedValues]);

  useEffect(() => {
    if (areTagArraysEqual(selectedValuesRef.current, normalizedValue)) {
      return;
    }
    selectedValuesRef.current = normalizedValue;
    setSelectedValues(normalizedValue);
  }, [normalizedValue]);

  const effectiveOptions = useMemo(() => {
    const map = new Map<string, Tag>();
    for (const tag of options) {
      map.set(normalizeTagName(tag.name), tag);
    }
    selectedValues.forEach((selectedTagName, index) => {
      const normalized = normalizeTagName(selectedTagName);
      if (!normalized || map.has(normalized)) {
        return;
      }
      map.set(normalized, {
        id: -1 - index,
        name: selectedTagName.trim(),
        color: null
      });
    });
    return Array.from(map.values()).sort((left, right) => left.name.localeCompare(right.name));
  }, [options, selectedValues]);

  const optionsByName = useMemo(() => {
    const map = new Map<string, Tag>();
    effectiveOptions.forEach((tag) => map.set(normalizeTagName(tag.name), tag));
    return map;
  }, [effectiveOptions]);

  const selected = useMemo(() => {
    const selectedTags: Array<{ key: string; name: string; color: string | null }> = [];
    for (const tagName of selectedValues) {
      const key = normalizeTagName(tagName);
      const catalogTag = optionsByName.get(key);
      selectedTags.push({
        key,
        name: catalogTag?.name ?? tagName.trim(),
        color: tagColor(catalogTag?.name ?? tagName.trim(), catalogTag?.color)
      });
    }
    return selectedTags;
  }, [optionsByName, selectedValues]);

  const selectedKeys = useMemo(() => new Set(selectedValues), [selectedValues]);

  const filteredOptions = useMemo(() => {
    const q = normalizeTagName(query);
    return effectiveOptions
      .filter((tag) => {
        if (!q) {
          return true;
        }
        return normalizeTagName(tag.name).includes(q);
      })
      .sort((left, right) => left.name.localeCompare(right.name));
  }, [effectiveOptions, query]);

  const creatableTag = useMemo(() => {
    const normalized = normalizeTagName(query);
    if (!normalized) {
      return null;
    }
    if (optionsByName.has(normalized) || selectedKeys.has(normalized)) {
      return null;
    }
    return normalized;
  }, [optionsByName, query, selectedKeys]);

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current) {
        return;
      }
      if (!rootRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, []);

  function commitTags(update: (current: string[]) => string[]) {
    const current = selectedValuesRef.current;
    const next = normalizeTagList(update(current));
    if (areTagArraysEqual(current, next)) {
      return;
    }
    selectedValuesRef.current = next;
    setSelectedValues(next);
    onChange(next);
  }

  function focusInput() {
    if (disabled) {
      return;
    }
    inputRef.current?.focus();
    setIsOpen(true);
  }

  function addTag(tagName: string) {
    const normalized = normalizeTagName(tagName);
    if (!normalized) {
      return;
    }
    commitTags((current) => {
      if (tagExists(current, normalized)) {
        return current;
      }
      return [...current, normalized];
    });
    setQuery("");
    setIsOpen(true);
  }

  function removeTagAt(index: number) {
    commitTags((current) => current.filter((_, currentIndex) => currentIndex !== index));
  }

  function removeFirstTagByName(tagName: string) {
    const normalized = normalizeTagName(tagName);
    if (!normalized) {
      return;
    }
    commitTags((current) => removeFirstTag(current, normalized));
  }

  function toggleTag(tagName: string) {
    const normalized = normalizeTagName(tagName);
    if (!normalized) {
      return;
    }
    commitTags((current) => {
      if (tagExists(current, normalized)) {
        return removeFirstTag(current, normalized);
      }
      return [...current, normalized];
    });
    setQuery("");
    setIsOpen(true);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && query === "" && selected.length > 0) {
      event.preventDefault();
      removeFirstTagByName(selected[selected.length - 1].key);
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      const normalizedQuery = normalizeTagName(query);
      if (!normalizedQuery) {
        return;
      }
      const exactMatch = filteredOptions.find(
        (tag) => normalizeTagName(tag.name) === normalizedQuery && !selectedKeys.has(normalizeTagName(tag.name))
      );
      if (exactMatch) {
        addTag(exactMatch.name);
        return;
      }
      const firstMatch = filteredOptions.find((tag) => !selectedKeys.has(normalizeTagName(tag.name)));
      if (firstMatch) {
        addTag(firstMatch.name);
        return;
      }
      if (creatableTag) {
        addTag(creatableTag);
      }
      return;
    }

    if (event.key === "Escape") {
      setIsOpen(false);
    }
  }

  function onOptionPointerDown(event: ReactPointerEvent<HTMLButtonElement>, action: () => void) {
    if (disabled || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    action();
  }

  function onActionKeyDown(event: KeyboardEvent<HTMLButtonElement>, action: () => void) {
    if (disabled) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      event.stopPropagation();
      action();
    }
  }

  return (
    <div className={`tag-multiselect ${disabled ? "is-disabled" : ""}`} ref={rootRef}>
      <div className="tag-multiselect-control" onClick={focusInput}>
        {selected.map((tag, index) => (
          <span key={tag.key} className="tag-chip" style={{ borderColor: tag.color ?? undefined }}>
            <span className="tag-chip-color" style={{ backgroundColor: tag.color || "hsl(var(--muted))" }} />
            <span>{tag.name}</span>
            <button
              type="button"
              className="tag-chip-remove"
              onPointerDown={(event) => {
                onOptionPointerDown(event, () => {
                  removeTagAt(index);
                });
              }}
              onKeyDown={(event) => onActionKeyDown(event, () => removeTagAt(index))}
              disabled={disabled}
              aria-label={`Remove tag ${tag.name}`}
            >
              <span className="tag-chip-close">×</span>
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          className="tag-multiselect-input"
          aria-label={ariaLabel}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={selected.length === 0 ? placeholder : ""}
          disabled={disabled}
        />
      </div>

      {isOpen ? (
        <div className="tag-multiselect-menu">
          {filteredOptions.length === 0 && !creatableTag ? <p className="tag-multiselect-empty">No matching tags.</p> : null}
          {filteredOptions.map((tag) => {
            const key = normalizeTagName(tag.name);
            const isSelected = selectedKeys.has(key);
            return (
              <button
                key={key}
                type="button"
                className={`tag-multiselect-option ${isSelected ? "is-selected" : ""}`}
                onPointerDown={(event) => {
                  onOptionPointerDown(event, () => {
                    toggleTag(tag.name);
                  });
                }}
                onKeyDown={(event) => onActionKeyDown(event, () => toggleTag(tag.name))}
                aria-pressed={isSelected}
              >
                <span className="tag-option-label">
                  <span className="tag-option-color" style={{ backgroundColor: tagColor(tag.name, tag.color) }} />
                  {tag.name}
                </span>
                <span className="tag-option-check">{isSelected ? "✓" : ""}</span>
              </button>
            );
          })}
          {creatableTag ? (
            <button
              type="button"
              className="tag-multiselect-option"
              onPointerDown={(event) => {
                onOptionPointerDown(event, () => {
                  addTag(creatableTag);
                });
              }}
              onKeyDown={(event) => onActionKeyDown(event, () => addTag(creatableTag))}
            >
              <span className="tag-option-label">Create "{creatableTag}"</span>
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
