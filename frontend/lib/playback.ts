import type { PlaybackMode, PlaybackResponse } from "./api";

const PLAYBACK_MODES = new Set<PlaybackMode>(["external_link", "iframe_embed"]);
export const KODIK_PLAYER_ORIGIN = "https://kodikplayer.com";

interface PlayerMessage {
  origin: string;
  source: unknown;
  data: unknown;
}

const MAX_PLAYER_SECONDS = 24 * 60 * 60;

const KODIK_EVENT_TYPES = {
  kodik_player_video_started: "started",
  kodik_player_play: "play",
  kodik_player_pause: "pause",
  kodik_player_video_ended: "ended",
  kodik_player_seek: "seek",
  kodik_player_time_update: "time",
  kodik_player_duration_update: "duration",
} as const;

export type KodikPlayerEvent =
  | { type: "started" | "play" | "pause" | "ended" | "seek" }
  | { type: "time" | "duration"; seconds: number };

export interface SafePlaybackTarget {
  mode: PlaybackMode;
  url: string;
  expiresAt: Date;
}

export function safePlaybackTarget(payload: unknown, origin: string): SafePlaybackTarget {
  if (!payload || typeof payload !== "object") throw new Error("Invalid playback response");
  const response = payload as Partial<PlaybackResponse>;
  if (!PLAYBACK_MODES.has(response.mode as PlaybackMode) || typeof response.url !== "string" || typeof response.expires_at !== "string") {
    throw new Error("Invalid playback response");
  }
  const expectedOrigin = new URL(origin).origin;
  const target = new URL(response.url, expectedOrigin);
  const expiresAt = new Date(response.expires_at);
  if (
    target.origin !== expectedOrigin
    || !target.pathname.startsWith("/api/v1/playback/")
    || !target.pathname.endsWith("/")
    || target.search
    || target.hash
    || Number.isNaN(expiresAt.getTime())
  ) {
    throw new Error("Unsafe playback response");
  }
  return { mode: response.mode as PlaybackMode, url: target.href, expiresAt };
}

/**
 * Parse only the documented AniCast/Kodik integration events from the exact
 * iframe window. Unknown messages and malformed time values stay outside the
 * playback-progress boundary.
 */
export function parseTrustedKodikPlayerEvent(
  message: PlayerMessage,
  frameWindow: unknown,
): KodikPlayerEvent | null {
  if (message.origin !== KODIK_PLAYER_ORIGIN || message.source !== frameWindow) return null;
  if (!message.data || typeof message.data !== "object" || Array.isArray(message.data)) return null;

  const data = message.data as { key?: unknown; value?: unknown };
  if (
    typeof data.key !== "string"
    || !Object.prototype.hasOwnProperty.call(KODIK_EVENT_TYPES, data.key)
  ) return null;
  const type = KODIK_EVENT_TYPES[data.key as keyof typeof KODIK_EVENT_TYPES];

  if (type === "time" || type === "duration") {
    if (
      typeof data.value !== "number"
      || !Number.isFinite(data.value)
      || data.value < 0
      || data.value > MAX_PLAYER_SECONDS
    ) return null;
    return { type, seconds: data.value };
  }

  return { type };
}

/** A compact, locale-neutral media clock: M:SS or H:MM:SS. */
export function formatPlaybackTime(value: number) {
  const total = Math.max(0, Math.floor(Number.isFinite(value) ? value : 0));
  const seconds = total % 60;
  const minutes = Math.floor(total / 60) % 60;
  const hours = Math.floor(total / 3600);
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
