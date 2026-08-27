"use client";

import { useEffect, useState } from "react";
import { getPlayback, type PlaybackMode } from "../lib/api";
import { safePlaybackTarget } from "../lib/playback";
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
}: {
  sourceId: number;
  playbackMode: PlaybackMode;
  title: string;
}) {
  const { t } = useI18n();
  const [state, setState] = useState<PlayerState>({ kind: "loading" });
  const [frameLoaded, setFrameLoaded] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setState({ kind: "loading" });
    setFrameLoaded(false);

    getPlayback(sourceId)
      .then((payload) => {
        const target = safePlaybackTarget(payload, window.location.origin);
        if (target.mode !== playbackMode || target.mode !== "iframe_embed") {
          throw new Error("Playback mode changed");
        }
        if (active) setState({ kind: "ready", src: target.url });
      })
      .catch(() => {
        if (active) setState({ kind: "error" });
      });

    return () => {
      active = false;
    };
  }, [attempt, playbackMode, sourceId]);

  return (
    <section
      className={styles.playerShell}
      aria-busy={state.kind === "loading" || (state.kind === "ready" && !frameLoaded)}
    >
      <div className={styles.playerBar}>
        <strong>{title}</strong>
      </div>
      <div className={styles.playerFrameWrap}>
        {(state.kind === "loading" || (state.kind === "ready" && !frameLoaded)) && (
          <span className={styles.playerLoading} role="status">{t("common.loading")}</span>
        )}
        {state.kind === "error" && (
          <div className={styles.playerError} role="alert">
            <span>{t("source.gone")}</span>
            <button className="secondary inline-button" type="button" onClick={() => setAttempt((value) => value + 1)}>
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
