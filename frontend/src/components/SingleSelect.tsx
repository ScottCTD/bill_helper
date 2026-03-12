import { KeyboardEvent, PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown } from "lucide-react";

import { useFloatingMenuPosition } from "../hooks/useFloatingMenuPosition";
import { Input } from "./ui/input";

interface SingleSelectOption {
  value: string;
  label: string;
}

interface SingleSelectProps {
  options: SingleSelectOption[];
  value: string;
  onChange: (nextValue: string) => void;
  placeholder?: string;
  disabled?: boolean;
  ariaLabel?: string;
  searchable?: boolean;
  searchPlaceholder?: string;
  emptyLabel?: string;
}

export function SingleSelect({
  options,
  value,
  onChange,
  placeholder = "Select...",
  disabled = false,
  ariaLabel,
  searchable = false,
  searchPlaceholder = "Search...",
  emptyLabel = "No matching options."
}: SingleSelectProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const controlRef = useRef<HTMLButtonElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { menuRef, menuStyle } = useFloatingMenuPosition({
    anchorRef: controlRef,
    open: isOpen
  });
  const selectedOption = useMemo(() => options.find((option) => option.value === value) ?? null, [options, value]);
  const filteredOptions = useMemo(() => {
    if (!searchable) {
      return options;
    }
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return options;
    }
    return options.filter((option) => option.label.toLowerCase().includes(normalizedQuery));
  }, [options, query, searchable]);

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

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      return;
    }
    if (searchable) {
      searchInputRef.current?.focus();
    }
  }, [isOpen, searchable]);

  function toggleMenu() {
    if (disabled) {
      return;
    }
    setIsOpen((open) => !open);
  }

  function selectOption(optionValue: string) {
    if (disabled || optionValue === value) {
      setIsOpen(false);
      return;
    }
    onChange(optionValue);
    setIsOpen(false);
  }

  function onOptionPointerDown(event: ReactPointerEvent<HTMLButtonElement>, action: () => void) {
    if (disabled || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    action();
  }

  function onControlKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (disabled) {
      return;
    }

    if (event.key === "Enter" || event.key === " " || event.key === "ArrowDown") {
      event.preventDefault();
      setIsOpen(true);
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
    }
  }

  function onOptionKeyDown(event: KeyboardEvent<HTMLButtonElement>, optionValue: string) {
    if (disabled) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectOption(optionValue);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
    }
  }

  function onSearchInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      const firstOption = filteredOptions[0];
      if (firstOption) {
        selectOption(firstOption.value);
      }
    }
  }

  return (
    <div className={`single-select ${disabled ? "is-disabled" : ""}`} ref={rootRef}>
      <button
        ref={controlRef}
        type="button"
        className="single-select-control"
        onClick={toggleMenu}
        onKeyDown={onControlKeyDown}
        aria-label={ariaLabel}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        disabled={disabled}
      >
        <span className={selectedOption ? "single-select-value" : "single-select-placeholder"}>
          {selectedOption?.label ?? placeholder}
        </span>
        <ChevronDown className="single-select-caret" />
      </button>
      {isOpen && typeof document !== "undefined"
        ? createPortal(
            <div className="single-select-menu" role="listbox" aria-label="Select option" ref={menuRef} style={menuStyle}>
              {searchable ? (
                <div className="p-1">
                  <Input
                    ref={searchInputRef}
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    onKeyDown={onSearchInputKeyDown}
                    placeholder={searchPlaceholder}
                    className="h-8"
                    aria-label={searchPlaceholder}
                  />
                </div>
              ) : null}
              {filteredOptions.length === 0 ? <p className="tag-multiselect-empty">{emptyLabel}</p> : null}
              {filteredOptions.map((option) => {
                const isSelected = option.value === value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    className={`single-select-option ${isSelected ? "is-selected" : ""}`}
                    role="option"
                    aria-selected={isSelected}
                    onPointerDown={(event) => onOptionPointerDown(event, () => selectOption(option.value))}
                    onKeyDown={(event) => onOptionKeyDown(event, option.value)}
                  >
                    <span>{option.label}</span>
                    <Check className={`single-select-check ${isSelected ? "is-visible" : ""}`} />
                  </button>
                );
              })}
            </div>,
            document.body
          )
        : null}
    </div>
  );
}
