"use client";

import { useEffect, useState } from "react";
import { getPlayback, type PlaybackMode } from "../lib/api";
import { recordEpisodeOpen } from "../lib/history";
import { safePlaybackTarget } from "../lib/playback";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

type PlayerState =
  | { kind: "idle" }
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
  const [state, setState] = useState<PlayerState>({ kind: "idle" });
  const [frameLoaded, setFrameLoaded] = useState(false);

  useEffect(() => {
    setState({ kind: "idle" });
    setFrameLoaded(false);
  }, [playbackMode, sourceId]);

  async function start() {
    setState({ kind: "loading" });
    setFrameLoaded(false);
    try {
      const payload = await getPlayback(sourceId);
      const target = safePlaybackTarget(payload, window.location.origin);
      if (target.mode !== playbackMode || target.mode !== "iframe_embed") {
        throw new Error("Playback mode changed");
      }
      // Playback progress starts only after an explicit user action and a
      // successfully authorized target. Guest history failure never blocks TV.
      void recordEpisodeOpen(slug, episodeNumber).catch(() => undefined);
      setState({ kind: "ready", src: target.url });
    } catch {
      setState({ kind: "error" });
    }
  }

  return (
    <section
      className={styles.playerShell}
      aria-busy={state.kind === "loading" || (state.kind === "ready" && !frameLoaded)}
    >
      <div className={styles.playerBar}>
        <strong>{title}</strong>
      </div>
      <div className={styles.playerFrameWrap}>
        {state.kind === "idle" && (
          <div className={styles.playerPreviewBody}>
            <button className={styles.playerLaunch} type="button" onClick={start}>
              {t("watch.startEpisode", { number: episodeNumber })}
            </button>
          </div>
        )}
        {(state.kind === "loading" || (state.kind === "ready" && !frameLoaded)) && (
          <span className={styles.playerLoading} role="status">{t("common.loading")}</span>
        )}
        {state.kind === "error" && (
          <div className={styles.playerError} role="alert">
            <span>{t("watch.sourceFailed")}</span>
            <button className="secondary inline-button" type="button" onClick={start}>
              {t("common.retry")}
            </button>
          </div>
        )}
        {state.kind === "ready" && (
          <iframe
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
