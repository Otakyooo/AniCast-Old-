import assert from "node:assert/strict";
import { test } from "node:test";
import { isTrustedKodikPlayerEvent, safePlaybackTarget } from "./playback.ts";

const expires_at = "2026-08-25T20:00:00Z";

test("safePlaybackTarget accepts signed same-origin playback modes", () => {
  for (const mode of ["external_link", "iframe_embed"] as const) {
    assert.deepEqual(
      safePlaybackTarget({ mode, url: "/api/v1/playback/signed-token/", expires_at }, "https://anicast.online"),
      { mode, url: "https://anicast.online/api/v1/playback/signed-token/", expiresAt: new Date(expires_at) },
    );
  }
});

test("safePlaybackTarget rejects raw, cross-origin and unknown targets", () => {
  const invalid = [
    { mode: "iframe_embed", url: "https://kodikplayer.com/seria/private", expires_at },
    { mode: "external_link", url: "https://evil.example/api/v1/playback/token/", expires_at },
    { mode: "unknown", url: "/api/v1/playback/token/", expires_at },
    { mode: "iframe_embed", url: "/api/v1/playback/token/?next=evil", expires_at },
    { mode: "iframe_embed", url: "/api/v1/playback/token/", expires_at: "invalid" },
  ];
  for (const payload of invalid) {
    assert.throws(() => safePlaybackTarget(payload, "https://anicast.online"));
  }
});

test("Kodik events require the exact origin, iframe window and event key", () => {
  const frameWindow = {};
  const trusted = {
    origin: "https://kodikplayer.com",
    source: frameWindow,
    data: { key: "kodik_player_video_started" },
  };
  assert.equal(isTrustedKodikPlayerEvent(trusted, frameWindow, "kodik_player_video_started"), true);
  assert.equal(isTrustedKodikPlayerEvent({ ...trusted, origin: "https://evil.example" }, frameWindow, "kodik_player_video_started"), false);
  assert.equal(isTrustedKodikPlayerEvent({ ...trusted, source: {} }, frameWindow, "kodik_player_video_started"), false);
  assert.equal(isTrustedKodikPlayerEvent({ ...trusted, data: { key: "kodik_player_play" } }, frameWindow, "kodik_player_video_started"), false);
  assert.equal(isTrustedKodikPlayerEvent({ ...trusted, data: null }, frameWindow, "kodik_player_video_started"), false);
});
