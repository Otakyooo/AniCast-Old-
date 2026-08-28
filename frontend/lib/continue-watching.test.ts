import assert from "node:assert/strict";
import test from "node:test";
import { resumeEpisode, type ContinueWatchingEntry } from "./continue-watching.ts";


function entry(overrides: Partial<ContinueWatchingEntry> = {}): ContinueWatchingEntry {
  const episode = { id: 1, number: 4, name: "", sources: [] };
  return {
    title: { slug: "test", name: "Test" },
    last_episode: episode,
    resume_episode: episode,
    next_episode: episode,
    is_watched: false,
    watched_count: 0,
    last_opened_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}


test("resumeEpisode uses the backend-validated playable target", () => {
  assert.equal(resumeEpisode(entry())?.number, 4);
});


test("resumeEpisode supports the compatibility target without replaying last_episode", () => {
  const value = entry({ resume_episode: undefined, next_episode: null });
  assert.equal(resumeEpisode(value), null);
});
