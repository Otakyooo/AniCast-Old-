"use client";

import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "./i18n-provider";
import styles from "./rail-scroller.module.css";

/**
 * Arrow affordance for horizontal card rails.
 *
 * The rails keep native horizontal scrolling (keyboard, wheel, touch) and hide
 * the scrollbar; the arrows make the overflow discoverable on pointer
 * devices. Below the arrow breakpoint the rails fall back to swipe alone, so
 * no interactive element depends on a pointer being present.
 */
export function RailScroller({
  railClassName,
  children,
}: {
  /** Caller class with rail-specific `--rail-*` custom properties. */
  railClassName?: string;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  const railRef = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ canScroll: false, start: true, end: false });

  const measure = useCallback(() => {
    const rail = railRef.current;
    if (!rail) return;
    const max = rail.scrollWidth - rail.clientWidth;
    if (max <= 1) {
      setEdges({ canScroll: false, start: true, end: false });
      return;
    }
    setEdges({
      canScroll: true,
      start: rail.scrollLeft <= 1,
      end: rail.scrollLeft >= max - 1,
    });
  }, []);

  useEffect(() => {
    const rail = railRef.current;
    if (!rail) return;
    measure();
    rail.addEventListener("scroll", measure, { passive: true });
    const observer = new ResizeObserver(measure);
    observer.observe(rail);
    return () => {
      rail.removeEventListener("scroll", measure);
      observer.disconnect();
    };
  }, [measure]);

  function scrollRail(direction: 1 | -1) {
    const rail = railRef.current;
    if (!rail) return;
    const distance = Math.max(rail.clientWidth * 0.8, 240);
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth";
    rail.scrollBy({ left: direction * distance, behavior });
  }

  return (
    <div className={styles.shell}>
      <div className={`${styles.rail} ${railClassName ?? ""}`} ref={railRef}>
        {children}
      </div>
      {edges.canScroll && (
        <>
          <button
            className={styles.arrowPrev}
            type="button"
            disabled={edges.start}
            aria-label={t("rail.scrollBack")}
            onClick={() => scrollRail(-1)}
          >
            <CaretLeft aria-hidden="true" weight="bold" />
          </button>
          <button
            className={styles.arrowNext}
            type="button"
            disabled={edges.end}
            aria-label={t("rail.scrollForward")}
            onClick={() => scrollRail(1)}
          >
            <CaretRight aria-hidden="true" weight="bold" />
          </button>
        </>
      )}
    </div>
  );
}
