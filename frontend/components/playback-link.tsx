"use client";

import { useState } from "react";
import { getPlayback, type PlaybackMode } from "../lib/api";
import { safePlaybackTarget } from "../lib/playback";
import { useI18n } from "./i18n-provider";

export function PlaybackLink({
  sourceId,
  playbackMode,
  onEmbed,
  label,
  className,
}: {
  sourceId: number;
  playbackMode?: PlaybackMode | null;
  onEmbed?: (url: string) => void;
  label?: string;
  className?: string;
}) {
  const { t } = useI18n();
  const [error, setError] = useState("");
  async function open() {
    const popup = playbackMode === "iframe_embed" && onEmbed ? null : window.open("about:blank", "_blank");
    if (popup) popup.opener = null;
    setError("");
    try {
      const payload = await getPlayback(sourceId);
      const target = safePlaybackTarget(payload, window.location.origin);
      if (playbackMode && target.mode !== playbackMode) throw new Error("Playback mode changed");
      if (target.mode === "iframe_embed" && onEmbed) {
        popup?.close();
        onEmbed(target.url);
      } else if (popup) {
        popup.location.href = target.url;
      } else {
        throw new Error("Popup blocked");
      }
    } catch {
      popup?.close();
      setError(t("source.gone"));
    }
  }
  return <><button className={className ?? "primary inline-button"} type="button" onClick={open}>{label ?? t("source.open")}</button>{error && <small role="alert">{error}</small>}</>;
}
