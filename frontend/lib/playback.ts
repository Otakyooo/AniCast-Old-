import type { PlaybackMode, PlaybackResponse } from "./api";

const PLAYBACK_MODES = new Set<PlaybackMode>(["external_link", "iframe_embed"]);

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
