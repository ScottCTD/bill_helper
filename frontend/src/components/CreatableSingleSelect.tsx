import { KeyboardEvent, PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown } from "lucide-react";

import { useFloatingMenuPosition } from "../hooks/useFloatingMenuPosition";

interface CreatableSingleSelectProps {
  options: string[];
  value: string;
  onChange: (nextValue: string, meta?: CreatableSingleSelectChangeMeta) => void;
  placeholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
  onCreateOption?: (createdValue: string) => void;
  createLabelPrefix?: string;
}

export interface CreatableSingleSelectChangeMeta {
  source: "input" | "select" | "create";
}

function normalizeValue(value: string) {
  return value.trim().toLowerCase();
}

function uniqueNormalized(values: string[]) {
  const uniqueValues: string[] = [];
  const seen = new Set<string>();

  for (const value of values) {
    const trimmed = value.trim();
    const normalized = normalizeValue(trimmed);
    if (!trimmed || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    uniqueValues.push(trimmed);
  }
  return uniqueValues.sort((left, right) => left.localeCompare(right));
}

export function CreatableSingleSelect({
  options,
  value,
  onChange,
  placeholder = "Select or create...",
  disabled = false,
  ariaLabel,
  onCreateOption,
  createLabelPrefix = "Create"
}: CreatableSingleSelectProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const controlRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [createdOptions, setCreatedOptions] = useState<string[]>([]);
  const { menuRef, menuStyle } = useFloatingMenuPosition({
    anchorRef: controlRef,
    open: isOpen
  });

  const normalizedValue = normalizeValue(value);
  const effectiveOptions = useMemo(() => uniqueNormalized([...options, ...createdOptions]), [options, createdOptions]);
  const filteredOptions = useMemo(() => {
    const normalizedQuery = normalizeValue(value);
    if (!normalizedQuery) {
      return effectiveOptions;
    }
    return effectiveOptions.filter((option) => normalizeValue(option).includes(normalizedQuery));
  }, [effectiveOptions, value]);

  const creatableValue = useMemo(() => {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const alreadyCreated = createdOptions.some((option) => normalizeValue(option) === normalizeValue(trimmed));
    if (alreadyCreated) {
      return null;
    }
    return trimmed;
  }, [createdOptions, value]);

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

  function focusInput() {
    if (disabled) {
      return;
    }
    inputRef.current?.focus();
    setIsOpen(true);
  }

  function selectValue(nextValue: string, markAsCreated = false) {
    if (markAsCreated) {
      setCreatedOptions((current) => uniqueNormalized([...current, nextValue]));
      onCreateOption?.(nextValue);
    }
    onChange(nextValue, { source: markAsCreated ? "create" : "select" });
    setIsOpen(false);
    requestAnimationFrame(() => inputRef.current?.blur());
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

  function onInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      const exactMatch = filteredOptions.find((option) => normalizeValue(option) === normalizedValue);
      if (exactMatch) {
        selectValue(exactMatch);
        return;
      }
      const firstMatch = filteredOptions[0];
      if (firstMatch) {
        selectValue(firstMatch);
        return;
      }
      if (creatableValue) {
        selectValue(creatableValue);
      }
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIsOpen(true);
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
    }
  }

  return (
    <div className={`creatable-select ${disabled ? "is-disabled" : ""}`} ref={rootRef}>
      <div className="creatable-select-control" onClick={focusInput} ref={controlRef}>
        <input
          ref={inputRef}
          type="text"
          className="creatable-select-input !h-full !rounded-none !border-0 !bg-transparent !px-0 !py-0 !shadow-none focus-visible:!ring-0"
          aria-label={ariaLabel}
          placeholder={placeholder}
          disabled={disabled}
          value={value}
          onChange={(event) => {
            onChange(event.target.value, { source: "input" });
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={onInputKeyDown}
        />
        <button
          type="button"
          aria-label="Toggle options"
          className="creatable-select-toggle"
          disabled={disabled}
          onPointerDown={(event) => {
            if (disabled || event.button !== 0) {
              return;
            }
            event.preventDefault();
            event.stopPropagation();
            setIsOpen((open) => !open);
            if (!isOpen) {
              requestAnimationFrame(() => inputRef.current?.focus());
            }
          }}
        >
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </button>
      </div>

      {isOpen && typeof document !== "undefined"
        ? createPortal(
            <div className="creatable-select-menu" ref={menuRef} style={menuStyle}>
              {filteredOptions.map((option) => {
                const isSelected = normalizeValue(option) === normalizedValue;
                return (
                  <button
                    key={normalizeValue(option)}
                    type="button"
                    className={`creatable-select-option ${isSelected ? "is-selected" : ""}`}
                    onPointerDown={(event) => onOptionPointerDown(event, () => selectValue(option))}
                    onKeyDown={(event) => onActionKeyDown(event, () => selectValue(option))}
                  >
                    {option}
                  </button>
                );
              })}
              {creatableValue ? (
                <button
                  type="button"
                  className="creatable-select-option"
                  onPointerDown={(event) => onOptionPointerDown(event, () => selectValue(creatableValue, true))}
                  onKeyDown={(event) => onActionKeyDown(event, () => selectValue(creatableValue, true))}
                >
                  {createLabelPrefix} "{creatableValue}"
                </button>
              ) : null}
              {filteredOptions.length === 0 && !creatableValue ? <p className="tag-multiselect-empty">No matching options.</p> : null}
            </div>,
            document.body
          )
        : null}
    </div>
  );
}
