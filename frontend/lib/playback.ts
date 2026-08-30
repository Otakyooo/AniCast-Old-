import type { PlaybackMode, PlaybackResponse } from "./api";

const PLAYBACK_MODES = new Set<PlaybackMode>(["external_link", "iframe_embed"]);
export const KODIK_PLAYER_ORIGIN = "https://kodikplayer.com";

interface PlayerMessage {
  origin: string;
  source: unknown;
  data: unknown;
}

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

/** Cross-origin player messages are accepted only from this iframe and Kodik. */
export function isTrustedKodikPlayerEvent(
  message: PlayerMessage,
  frameWindow: unknown,
  eventKey: string,
) {
  if (message.origin !== KODIK_PLAYER_ORIGIN || message.source !== frameWindow) return false;
  if (!message.data || typeof message.data !== "object" || Array.isArray(message.data)) return false;
  return (message.data as { key?: unknown }).key === eventKey;
}
