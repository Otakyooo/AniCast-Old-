"use client";

import { useEffect, useRef } from "react";
import { getCsrfToken } from "../lib/auth";

/** Fires the privacy-safe visit counter once per page load.
 *
 * The backend counts at most one visit per browser per UTC day (signed
 * cookie dedupe, bot/advisory guards) and throttles only the counting
 * branch, so this call is fire-and-forget by design: any failure is
 * swallowed because a vanity metric must never break a page load.
 */
export function VisitTracker() {
  const sent = useRef(false);
  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    (async () => {
      try {
        const csrf = await getCsrfToken();
        await fetch("/api/v1/analytics/visit/", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        });
      } catch {
        // Vanity metric: never surface to the viewer.
      }
    })();
  }, []);
  return null;
}
