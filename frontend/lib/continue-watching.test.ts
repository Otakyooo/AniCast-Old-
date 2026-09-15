import assert from "node:assert/strict";
import test from "node:test";
import { resumeEpisode, resumeEpisodeStarted, resumeProgressPercent, type ContinueWatchingEntry } from "./continue-watching.ts";


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


test("resumeProgressPercent prefers the confirmed playback position", () => {
  assert.equal(resumeProgressPercent(entry({ resume_at_seconds: 48, duration_seconds: 120 })), 40);
  assert.equal(resumeProgressPercent(entry({ resume_at_seconds: 130, duration_seconds: 120 })), 100);
});


test("resumeProgressPercent falls back to watched episodes and never invents progress", () => {
  const withCount = entry({
    title: { slug: "test", name: "Test", episodes_count: 8 },
    watched_count: 2,
  });
  assert.equal(resumeProgressPercent(withCount), 25);
  assert.equal(resumeProgressPercent(entry({ resume_at_seconds: 48, duration_seconds: null })), 0);
  assert.equal(resumeProgressPercent(entry({ resume_at_seconds: 0, duration_seconds: 120 })), 0);
  assert.equal(resumeProgressPercent(entry()), 0);
});


test("resumeEpisodeStarted is true only for an episode with a real position", () => {
  assert.equal(resumeEpisodeStarted(entry({ resume_at_seconds: 48, duration_seconds: 120 })), true);
  // Opened but never played: the shelf must not claim progress.
  assert.equal(resumeEpisodeStarted(entry({ resume_at_seconds: 0, duration_seconds: 120 })), false);
  assert.equal(resumeEpisodeStarted(entry()), false);
  // A finished episode hands over to the next one, which has no position yet,
  // so the card offers "Смотреть серию N" rather than "Продолжить серию N".
  assert.equal(
    resumeEpisodeStarted(entry({ is_watched: true, resume_at_seconds: 0, duration_seconds: null })),
    false,
  );
});
