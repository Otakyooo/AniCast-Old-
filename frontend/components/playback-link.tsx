"use client";

import { useState } from "react";
import { getPlayback, type PlaybackMode } from "../lib/api";
import { safePlaybackTarget } from "../lib/playback";
import { recordEpisodeOpen } from "../lib/history";
import { useI18n } from "./i18n-provider";

export function PlaybackLink({
  sourceId,
  playbackMode,
  label,
  className,
  slug,
  episodeNumber,
}: {
  sourceId: number;
  playbackMode?: PlaybackMode | null;
  label?: string;
  className?: string;
  slug?: string;
  episodeNumber?: number;
}) {
  const { t } = useI18n();
  const [error, setError] = useState("");
  async function open() {
    // Embedded playback is handled by ProviderPlayer, so this component always
    // hands the resolved URL to a fresh tab. The blank popup is opened before
    // the await so the click is still the trusted user gesture.
    const popup = window.open("about:blank", "_blank");
    if (popup) popup.opener = null;
    setError("");
    try {
      const payload = await getPlayback(sourceId);
      const target = safePlaybackTarget(payload, window.location.origin);
      if (playbackMode && target.mode !== playbackMode) throw new Error("Playback mode changed");
      if (slug && episodeNumber) void recordEpisodeOpen(slug, episodeNumber).catch(() => undefined);
      if (!popup) throw new Error("Popup blocked");
      popup.location.href = target.url;
    } catch {
      popup?.close();
      setError(t("source.gone"));
    }
  }
  return <><button className={className ?? "primary inline-button"} type="button" onClick={open}>{label ?? t("source.open")}</button>{error && <small role="alert">{error}</small>}</>;
}
