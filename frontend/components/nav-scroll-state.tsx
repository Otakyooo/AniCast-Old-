"use client";

import { useEffect } from "react";

// The header is transparent until the page moves: the bottom border appears
// only once content can slide under it, so a fresh page reads as one surface
// and a scrolled one gets a visible edge (design spec §6).
const SCROLLED_AFTER = 4;

export function NavScrollState() {
  useEffect(() => {
    const nav = document.querySelector<HTMLElement>(".global-nav");
    if (!nav) return;

    const sync = () => {
      nav.dataset.scrolled = window.scrollY > SCROLLED_AFTER ? "true" : "false";
    };

    sync();
    window.addEventListener("scroll", sync, { passive: true });
    return () => window.removeEventListener("scroll", sync);
  }, []);

  return null;
}
