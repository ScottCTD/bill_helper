import { useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

interface UseFloatingMenuPositionArgs {
  anchorRef: RefObject<HTMLElement | null>;
  open: boolean;
  offset?: number;
  preferredMaxHeight?: number;
  viewportPadding?: number;
  minVisibleHeight?: number;
}

function resolvedMenuHeight(availableSpace: number, preferredMaxHeight: number, minVisibleHeight: number) {
  return Math.max(Math.min(preferredMaxHeight, availableSpace), Math.min(minVisibleHeight, availableSpace));
}

export function useFloatingMenuPosition({
  anchorRef,
  open,
  offset = 6,
  preferredMaxHeight = 224,
  viewportPadding = 12,
  minVisibleHeight = 96
}: UseFloatingMenuPositionArgs) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [menuStyle, setMenuStyle] = useState<CSSProperties>({
    left: 0,
    maxHeight: preferredMaxHeight,
    pointerEvents: "auto",
    position: "fixed",
    top: 0,
    visibility: "hidden",
    width: 0,
    zIndex: 60
  });

  useLayoutEffect(() => {
    if (!open) {
      return;
    }

    function updatePosition() {
      const anchor = anchorRef.current;
      if (!anchor) {
        return;
      }

      const rect = anchor.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const availableBelow = Math.max(viewportHeight - rect.bottom - offset - viewportPadding, 0);
      const availableAbove = Math.max(rect.top - offset - viewportPadding, 0);
      const shouldPlaceAbove = availableAbove > availableBelow && availableBelow < minVisibleHeight;
      const availableSpace = shouldPlaceAbove ? availableAbove : availableBelow;
      const maxHeight = resolvedMenuHeight(availableSpace, preferredMaxHeight, minVisibleHeight);
      const width = Math.min(rect.width, Math.max(viewportWidth - viewportPadding * 2, 0));
      const left = Math.min(Math.max(rect.left, viewportPadding), Math.max(viewportPadding, viewportWidth - viewportPadding - width));

      setMenuStyle({
        left,
        maxHeight,
        pointerEvents: "auto",
        position: "fixed",
        top: shouldPlaceAbove ? Math.max(rect.top - offset, viewportPadding) : rect.bottom + offset,
        transform: shouldPlaceAbove ? "translateY(-100%)" : undefined,
        visibility: "visible",
        width,
        zIndex: 60
      });
    }

    updatePosition();

    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [anchorRef, minVisibleHeight, offset, open, preferredMaxHeight, viewportPadding]);

  return {
    menuRef,
    menuStyle
  };
}
