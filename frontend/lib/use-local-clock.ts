"use client";

import { useSyncExternalStore } from "react";
import { MINUTE_MS } from "./schedule";

// A minute is the schedule's display precision. Stable snapshots avoid both
// hydration mismatches and an extra state-setting effect on every mount.
function minuteSnapshot() {
  return Math.floor(Date.now() / MINUTE_MS) * MINUTE_MS;
}

function serverSnapshot() { return null; }

function subscribe(listener: () => void) {
  const timer = window.setInterval(listener, MINUTE_MS);
  return () => window.clearInterval(timer);
}

export function useLocalClock(serverTodayKey: string) {
  const now = useSyncExternalStore(subscribe, minuteSnapshot, serverSnapshot);
  return {
    now: now ?? Date.parse(`${serverTodayKey}T00:00:00Z`),
    local: now !== null,
  };
}
