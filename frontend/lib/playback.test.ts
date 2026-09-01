import assert from "node:assert/strict";
import { test } from "node:test";
import {
  formatPlaybackTime,
  parseTrustedKodikPlayerEvent,
  safePlaybackTarget,
} from "./playback.ts";

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

test("Kodik progress parser accepts only namespaced events from the exact iframe", () => {
  const frameWindow = {};
  const message = (data: unknown, origin = "https://kodikplayer.com", source: unknown = frameWindow) => ({
    origin,
    source,
    data,
  });

  assert.deepEqual(
    parseTrustedKodikPlayerEvent(message({ key: "kodik_player_duration_update", value: 1440.5 }), frameWindow),
    { type: "duration", seconds: 1440.5 },
  );
  assert.deepEqual(
    parseTrustedKodikPlayerEvent(message({ key: "kodik_player_time_update", value: 83 }), frameWindow),
    { type: "time", seconds: 83 },
  );
  assert.deepEqual(
    parseTrustedKodikPlayerEvent(message({ key: "kodik_player_video_started" }), frameWindow),
    { type: "started" },
  );
  assert.deepEqual(
    parseTrustedKodikPlayerEvent(message({ key: "kodik_player_video_ended" }), frameWindow),
    { type: "ended" },
  );
  assert.equal(parseTrustedKodikPlayerEvent(message(null), frameWindow), null);
  assert.equal(parseTrustedKodikPlayerEvent(message({ key: "time_update", value: 83 }), frameWindow), null);
  assert.equal(parseTrustedKodikPlayerEvent(message({ key: "kodik_player_time_update", value: "83" }), frameWindow), null);
  assert.equal(parseTrustedKodikPlayerEvent(message({ key: "kodik_player_time_update", value: -1 }), frameWindow), null);
  assert.equal(parseTrustedKodikPlayerEvent(message({ key: "kodik_player_time_update", value: Number.NaN }), frameWindow), null);
  assert.equal(parseTrustedKodikPlayerEvent(message({ key: "kodik_player_time_update", value: 90_000 }), frameWindow), null);
  assert.equal(parseTrustedKodikPlayerEvent(message({ key: "kodik_player_time_update", value: 83 }, "https://evil.example"), frameWindow), null);
  assert.equal(parseTrustedKodikPlayerEvent(message({ key: "kodik_player_time_update", value: 83 }, undefined, {}), frameWindow), null);
});

test("formatPlaybackTime formats media positions without rounding up", () => {
  assert.equal(formatPlaybackTime(0), "0:00");
  assert.equal(formatPlaybackTime(65.9), "1:05");
  assert.equal(formatPlaybackTime(3661), "1:01:01");
  assert.equal(formatPlaybackTime(Number.NaN), "0:00");
});
