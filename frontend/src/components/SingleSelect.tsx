import { KeyboardEvent, PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

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
}

export function SingleSelect({ options, value, onChange, placeholder = "Select...", disabled = false, ariaLabel }: SingleSelectProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const selectedOption = useMemo(() => options.find((option) => option.value === value) ?? null, [options, value]);

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

  return (
    <div className={`single-select ${disabled ? "is-disabled" : ""}`} ref={rootRef}>
      <button
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
      {isOpen ? (
        <div className="single-select-menu" role="listbox" aria-label="Select option">
          {options.map((option) => {
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
        </div>
      ) : null}
    </div>
  );
}
