"use client";

import { useEffect, useRef, useState } from "react";
import { getPlayback, type PlaybackMode } from "../lib/api";
import { recordEpisodeOpen } from "../lib/history";
import { isTrustedKodikPlayerEvent, safePlaybackTarget } from "../lib/playback";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

type PlayerState =
  | { kind: "loading" }
  | { kind: "ready"; src: string }
  | { kind: "error" };

export function ProviderPlayer({
  sourceId,
  playbackMode,
  title,
  slug,
  episodeNumber,
}: {
  sourceId: number;
  playbackMode: PlaybackMode;
  title: string;
  slug: string;
  episodeNumber: number;
}) {
  const { t } = useI18n();
  const [state, setState] = useState<PlayerState>({ kind: "loading" });
  const [frameLoaded, setFrameLoaded] = useState(false);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const recordedPlaybackRef = useRef("");

  useEffect(() => {
    let active = true;
    setState({ kind: "loading" });
    setFrameLoaded(false);
    getPlayback(sourceId).then((payload) => {
      const target = safePlaybackTarget(payload, window.location.origin);
      if (target.mode !== playbackMode || target.mode !== "iframe_embed") {
        throw new Error("Playback mode changed");
      }
      if (!active) return;
      setState({ kind: "ready", src: target.url });
    }).catch(() => { if (active) setState({ kind: "error" }); });
    return () => { active = false; };
  }, [episodeNumber, playbackMode, sourceId]);

  useEffect(() => {
    const playbackKey = `${sourceId}:${episodeNumber}`;
    recordedPlaybackRef.current = "";

    function handlePlayerMessage(event: MessageEvent) {
      if (
        recordedPlaybackRef.current === playbackKey
        || !isTrustedKodikPlayerEvent(
          event,
          frameRef.current?.contentWindow,
          "kodik_player_video_started",
        )
      ) return;
      recordedPlaybackRef.current = playbackKey;
      void recordEpisodeOpen(slug, episodeNumber).catch(() => undefined);
    }

    window.addEventListener("message", handlePlayerMessage);
    return () => window.removeEventListener("message", handlePlayerMessage);
  }, [episodeNumber, slug, sourceId]);

  async function retry() {
    setState({ kind: "loading" });
    setFrameLoaded(false);
    try {
      const payload = await getPlayback(sourceId);
      const target = safePlaybackTarget(payload, window.location.origin);
      if (target.mode !== playbackMode || target.mode !== "iframe_embed") throw new Error("Playback mode changed");
      setState({ kind: "ready", src: target.url });
    } catch { setState({ kind: "error" }); }
  }

  return (
    <section
      className={styles.playerShell}
      aria-label={title}
      aria-busy={state.kind === "loading" || (state.kind === "ready" && !frameLoaded)}
    >
      <div className={styles.playerFrameWrap}>
        {(state.kind === "loading" || (state.kind === "ready" && !frameLoaded)) && (
          <span className={styles.playerLoading} role="status">{t("common.loading")}</span>
        )}
        {state.kind === "error" && (
          <div className={styles.playerError} role="alert">
            <span>{t("watch.sourceFailed")}</span>
            <button className="secondary inline-button" type="button" onClick={retry}>
              {t("common.retry")}
            </button>
          </div>
        )}
        {state.kind === "ready" && (
          <iframe
            ref={frameRef}
            className={styles.playerFrame}
            src={state.src}
            title={t("source.playerTitle", { name: title })}
            allow="autoplay *; fullscreen *"
            allowFullScreen
            referrerPolicy="no-referrer"
            sandbox="allow-forms allow-presentation allow-same-origin allow-scripts"
            onLoad={() => setFrameLoaded(true)}
          />
        )}
      </div>
    </section>
  );
}
