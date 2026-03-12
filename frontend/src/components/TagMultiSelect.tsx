import { KeyboardEvent, PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useFloatingMenuPosition } from "../hooks/useFloatingMenuPosition";
import { resolveTagColor } from "../lib/tagColors";
import type { Tag } from "../lib/types";

interface TagMultiSelectProps {
  options: Tag[];
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
  allowCreate?: boolean;
  createLabelPrefix?: string;
}

function normalizeTagName(value: string) {
  return value.trim().toLowerCase();
}

function compactTagName(value: string) {
  return normalizeTagName(value).replace(/[\s_-]+/g, "");
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

function fuzzyTagScore(tagName: string, query: string) {
  const normalizedTagName = normalizeTagName(tagName);
  const normalizedQuery = normalizeTagName(query);
  if (!normalizedQuery) {
    return 0;
  }

  if (normalizedTagName === normalizedQuery) {
    return 1_000;
  }

  if (normalizedTagName.startsWith(normalizedQuery)) {
    return 900 - (normalizedTagName.length - normalizedQuery.length);
  }

  const tagWords = normalizedTagName.split(/[\s_-]+/).filter(Boolean);
  const wordPrefixIndex = tagWords.findIndex((word) => word.startsWith(normalizedQuery));
  if (wordPrefixIndex >= 0) {
    return 800 - wordPrefixIndex * 10 - (tagWords[wordPrefixIndex].length - normalizedQuery.length);
  }

  const containsIndex = normalizedTagName.indexOf(normalizedQuery);
  if (containsIndex >= 0) {
    return 700 - containsIndex * 10 - (normalizedTagName.length - normalizedQuery.length);
  }

  const compactTag = compactTagName(tagName);
  const compactQuery = compactTagName(query);
  if (!compactQuery) {
    return null;
  }

  const matchedPositions: number[] = [];
  let queryIndex = 0;
  for (let tagIndex = 0; tagIndex < compactTag.length && queryIndex < compactQuery.length; tagIndex += 1) {
    if (compactTag[tagIndex] !== compactQuery[queryIndex]) {
      continue;
    }
    matchedPositions.push(tagIndex);
    queryIndex += 1;
  }

  if (queryIndex < compactQuery.length) {
    return null;
  }

  let contiguousPairs = 0;
  for (let index = 1; index < matchedPositions.length; index += 1) {
    if (matchedPositions[index] === matchedPositions[index - 1] + 1) {
      contiguousPairs += 1;
    }
  }

  const matchStart = matchedPositions[0];
  const matchSpan = matchedPositions[matchedPositions.length - 1] - matchStart + 1;
  const gapsInsideMatch = matchSpan - compactQuery.length;
  return 500 - matchStart * 10 - gapsInsideMatch * 8 - (compactTag.length - compactQuery.length) + contiguousPairs * 20;
}

export function TagMultiSelect({
  options,
  value,
  onChange,
  placeholder = "Select tags...",
  disabled = false,
  ariaLabel,
  allowCreate = true,
  createLabelPrefix = "Create"
}: TagMultiSelectProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const controlRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const normalizedValue = useMemo(() => normalizeTagList(value), [value]);
  const [selectedValues, setSelectedValues] = useState<string[]>(normalizedValue);
  const selectedValuesRef = useRef<string[]>(selectedValues);
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const { menuRef, menuStyle } = useFloatingMenuPosition({
    anchorRef: controlRef,
    open: isOpen
  });

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
        color: resolveTagColor(catalogTag?.name ?? tagName.trim(), catalogTag?.color)
      });
    }
    return selectedTags;
  }, [optionsByName, selectedValues]);

  const selectedKeys = useMemo(() => new Set(selectedValues), [selectedValues]);

  const filteredOptions = useMemo(() => {
    const q = normalizeTagName(query);
    if (!q) {
      return effectiveOptions;
    }
    return effectiveOptions
      .map((tag) => ({
        tag,
        score: fuzzyTagScore(tag.name, q)
      }))
      .filter((entry): entry is { tag: Tag; score: number } => entry.score !== null)
      .sort((left, right) => right.score - left.score || left.tag.name.localeCompare(right.tag.name))
      .map((entry) => entry.tag);
  }, [effectiveOptions, query]);

  const creatableTag = useMemo(() => {
    if (!allowCreate) {
      return null;
    }
    const normalized = normalizeTagName(query);
    if (!normalized) {
      return null;
    }
    if (optionsByName.has(normalized) || selectedKeys.has(normalized)) {
      return null;
    }
    return normalized;
  }, [allowCreate, optionsByName, query, selectedKeys]);

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current) {
        return;
      }
      if (rootRef.current.contains(event.target as Node) || menuRef.current?.contains(event.target as Node)) {
        return;
      }
      setIsOpen(false);
    };

    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [menuRef]);

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
      <div className="tag-multiselect-control" onClick={focusInput} ref={controlRef}>
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
          className="tag-multiselect-input !h-full !rounded-none !border-0 !bg-transparent !px-1 !py-0.5 !shadow-none focus-visible:!ring-0"
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

      {isOpen && typeof document !== "undefined"
        ? createPortal(
            <div className="tag-multiselect-menu" ref={menuRef} style={menuStyle}>
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
                      <span className="tag-option-color" style={{ backgroundColor: resolveTagColor(tag.name, tag.color) }} />
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
                  <span className="tag-option-label">
                    {createLabelPrefix} "{creatableTag}"
                  </span>
                </button>
              ) : null}
            </div>,
            document.body
          )
        : null}
    </div>
  );
}
