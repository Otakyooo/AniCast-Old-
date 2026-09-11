"use client";

import { useSyncExternalStore } from "react";

/**
 * Client-side map of the viewer's library statuses, shared by every card on
 * the page. One `/api/v1/library/statuses/` response answers all of them at
 * once instead of one request per card; mutations update the store in place
 * and notify subscribers.
 */

export interface CardLibraryEntry {
  status: "planned" | "watching" | "completed" | "on_hold" | "dropped";
  is_favorite: boolean;
}

type Store = {
  state: "loading" | "ready" | "guest" | "error";
  entries: Map<string, CardLibraryEntry>;
};

const EMPTY_STORE: Store = { state: "loading", entries: new Map() };

let store: Store = EMPTY_STORE;
const listeners = new Set<() => void>();
let inFlight: Promise<void> | null = null;

function emit() {
  for (const listener of listeners) listener();
}

function setState(next: Store) {
  store = next;
  emit();
}

/** Load the status map once; guests resolve to an empty store silently. */
export function refreshLibraryStatuses(): Promise<void> {
  if (!inFlight) {
    inFlight = (async () => {
      try {
        const response = await fetch("/api/v1/library/statuses/", {
          credentials: "same-origin",
          cache: "no-store",
        });
        if (response.status === 401 || response.status === 403) {
          setState({ state: "guest", entries: new Map() });
          return;
        }
        if (!response.ok) throw new Error(`statuses failed: ${response.status}`);
        const payload = (await response.json()) as { entries: Array<{ slug: string } & CardLibraryEntry> };
        setState({
          state: "ready",
          entries: new Map(payload.entries.map((row) => [row.slug, { status: row.status, is_favorite: row.is_favorite }])),
        });
      } catch {
        setState({ state: "error", entries: new Map() });
      }
    })().finally(() => {
      inFlight = null;
    });
  }
  return inFlight;
}

/** Optimistic local mutation; called after the API mutation succeeded. */
export function applyLibraryStatusLocally(slug: string, entry: CardLibraryEntry | null) {
  const entries = new Map(store.entries);
  if (entry === null) entries.delete(slug);
  else entries.set(slug, entry);
  setState({ state: store.state === "loading" ? "ready" : store.state, entries });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (store.state === "loading" && !inFlight) void refreshLibraryStatuses();
  return () => listeners.delete(listener);
}

function snapshot(): Store {
  return store;
}

function serverSnapshot(): Store {
  return EMPTY_STORE;
}

/** Card-level read access: current entry for a slug, or undefined. */
export function useCardLibraryEntry(slug: string): {
  entry: CardLibraryEntry | undefined;
  ready: boolean;
  guest: boolean;
} {
  const current = useSyncExternalStore(subscribe, snapshot, serverSnapshot);
  const entry = current.entries.get(slug);
  return {
    entry,
    ready: current.state === "ready" || current.state === "guest",
    guest: current.state === "guest",
  };
}
