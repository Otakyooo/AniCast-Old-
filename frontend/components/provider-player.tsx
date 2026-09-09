"use client";

import { useEffect, useRef, useState } from "react";
import { getPlayback, type PlaybackMode } from "../lib/api";
import {
  getEpisodeProgress,
  HistoryApiError,
  recordEpisodeOpen,
  syncEpisodeProgress,
  type EpisodeProgress,
  type PlaybackProgressData,
  type ProgressSyncEvent,
} from "../lib/history";
import {
  KODIK_PLAYER_ORIGIN,
  parseTrustedKodikPlayerEvent,
  safePlaybackTarget,
} from "../lib/playback";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

type PlayerState =
  | { kind: "loading" }
  | { kind: "ready"; src: string }
  | { kind: "error" };

export type PlaybackProgressPhase = "loading" | "ready" | "saving" | "saved" | "guest" | "error";

export interface PlaybackProgressSnapshot {
  phase: PlaybackProgressPhase;
  watchedSeconds: number;
  durationSeconds: number | null;
  progressPercent: number;
  isWatched: boolean;
}

const HEARTBEAT_MS = 20_000;
const RESUME_MIN_SECONDS = 5;
const RESUME_END_GUARD_SECONDS = 30;

function validSeconds(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? Math.floor(value)
    : null;
}

interface ProviderPlayerProps {
  sourceId: number;
  playbackMode: PlaybackMode;
  title: string;
  slug: string;
  episodeNumber: number;
  onProgressChange?: (progress: PlaybackProgressSnapshot) => void;
}

export function ProviderPlayer(props: ProviderPlayerProps) {
  return <PlayerSession key={`${props.slug}:${props.episodeNumber}:${props.sourceId}:${props.playbackMode}`} {...props} />;
}

function PlayerSession({
  sourceId,
  playbackMode,
  title,
  slug,
  episodeNumber,
  onProgressChange,
}: ProviderPlayerProps) {
  const { t } = useI18n();
  const [state, setState] = useState<PlayerState>({ kind: "loading" });
  const [frameLoaded, setFrameLoaded] = useState(false);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const progressCallbackRef = useRef(onProgressChange);

  useEffect(() => {
    progressCallbackRef.current = onProgressChange;
  }, [onProgressChange]);

  useEffect(() => {
    let active = true;
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
    const controller = new AbortController();
    let active = true;
    let storedLoaded = false;
    let storedProgress: EpisodeProgress | null = null;
    let started = false;
    let restored = false;
    let guest = false;
    let positionSeconds = 0;
    let playerPositionSeconds = 0;
    let durationSeconds: number | null = null;
    let playerDurationReady = false;
    let isWatched = false;
    let phase: PlaybackProgressPhase = "loading";
    let syncInFlight = false;
    let queuedSync: { event: ProgressSyncEvent; keepalive: boolean } | null = null;
    let lastSyncStartedAt = Date.now();
    let lastSentPosition = -1;
    let lastExitFlushAt = 0;

    function publish(nextPhase = phase) {
      phase = nextPhase;
      const progressPercent = durationSeconds && durationSeconds > 0
        ? Math.min(100, Math.max(0, Math.round((positionSeconds / durationSeconds) * 100)))
        : 0;
      progressCallbackRef.current?.({
        phase,
        watchedSeconds: positionSeconds,
        durationSeconds,
        progressPercent: isWatched ? 100 : progressPercent,
        isWatched,
      });
    }

    function mergeServerProgress(progress: PlaybackProgressData, nextPhase: PlaybackProgressPhase) {
      const storedPosition = validSeconds(progress.watched_seconds);
      const storedDuration = validSeconds(progress.duration_seconds);
      if (storedPosition !== null && playerPositionSeconds <= RESUME_MIN_SECONDS) {
        positionSeconds = storedPosition;
      }
      if (durationSeconds === null && storedDuration !== null && storedDuration > 0) {
        durationSeconds = storedDuration;
      }
      // A delayed "opened" response may precede the completion PATCH on the
      // server but arrive after it. Completion is monotonic within this player
      // session, just as it is in the backend progress transaction.
      isWatched = isWatched || progress.is_watched;
      publish(nextPhase);
    }

    function tryRestorePosition() {
      if (restored || !storedLoaded || !playerDurationReady || durationSeconds === null) return;
      restored = true;
      const resumeAt = validSeconds(storedProgress?.watched_seconds);
      if (
        resumeAt === null
        || storedProgress?.is_watched
        || resumeAt <= RESUME_MIN_SECONDS
        || resumeAt >= durationSeconds - RESUME_END_GUARD_SECONDS
        || playerPositionSeconds > RESUME_MIN_SECONDS
      ) return;
      frameRef.current?.contentWindow?.postMessage(
        { key: "kodik_player_api", value: { method: "seek", seconds: resumeAt } },
        KODIK_PLAYER_ORIGIN,
      );
      positionSeconds = resumeAt;
      playerPositionSeconds = resumeAt;
      publish(phase === "loading" ? "ready" : phase);
    }

    function markGuest() {
      guest = true;
      publish("guest");
    }

    function beginPlayback() {
      if (started) return;
      started = true;
      recordEpisodeOpen(slug, episodeNumber)
        .then((progress) => {
          if (!active) return;
          storedLoaded = true;
          storedProgress = progress;
          mergeServerProgress(progress, "saved");
          tryRestorePosition();
        })
        .catch((reason) => {
          if (!active) return;
          if (reason instanceof HistoryApiError && [401, 403].includes(reason.status)) markGuest();
          else publish("error");
        });
    }

    function syncProgress(event: ProgressSyncEvent, keepalive = false) {
      if (guest || !started || durationSeconds === null || durationSeconds <= 0) return;
      if (syncInFlight) {
        const priority = { progress: 0, pause: 1, ended: 2 } as const;
        if (!queuedSync || priority[event] >= priority[queuedSync.event]) {
          queuedSync = { event, keepalive: keepalive || queuedSync?.keepalive === true };
        }
        return;
      }

      const sentPosition = event === "ended"
        ? Math.max(positionSeconds, durationSeconds)
        : positionSeconds;
      if (event !== "ended" && sentPosition === lastSentPosition && Date.now() - lastSyncStartedAt < HEARTBEAT_MS) return;

      syncInFlight = true;
      lastSyncStartedAt = Date.now();
      lastSentPosition = sentPosition;
      publish("saving");
      syncEpisodeProgress(slug, episodeNumber, {
        watched_seconds: Math.floor(sentPosition),
        duration_seconds: Math.floor(durationSeconds),
        event,
      }, keepalive)
        .then((progress) => {
          if (!active) return;
          mergeServerProgress(progress, "saved");
        })
        .catch((reason) => {
          if (!active) return;
          if (reason instanceof HistoryApiError && [401, 403].includes(reason.status)) markGuest();
          else publish("error");
        })
        .finally(() => {
          syncInFlight = false;
          if (!active) return;
          const queued = queuedSync;
          queuedSync = null;
          if (queued) syncProgress(queued.event, queued.keepalive);
        });
    }

    function bestEffortExitSync() {
      const now = Date.now();
      if (
        guest
        || !started
        || durationSeconds === null
        || durationSeconds <= 0
        || (now - lastExitFlushAt < 1_000 && positionSeconds === lastSentPosition)
      ) return;
      lastExitFlushAt = now;
      lastSentPosition = positionSeconds;
      void syncEpisodeProgress(slug, episodeNumber, {
        watched_seconds: Math.floor(positionSeconds),
        duration_seconds: Math.floor(durationSeconds),
        event: "pause",
      }, true).catch(() => undefined);
    }

    getEpisodeProgress(slug, episodeNumber, controller.signal)
      .then((progress) => {
        if (!active) return;
        storedLoaded = true;
        storedProgress = progress;
        mergeServerProgress(progress, "ready");
        tryRestorePosition();
      })
      .catch((reason) => {
        if (!active || (reason instanceof DOMException && reason.name === "AbortError")) return;
        storedLoaded = true;
        if (reason instanceof HistoryApiError && [401, 403].includes(reason.status)) markGuest();
        else if (reason instanceof HistoryApiError && reason.status === 404) publish("ready");
        else publish("error");
        tryRestorePosition();
      });
    publish("loading");

    function handlePlayerMessage(message: MessageEvent) {
      const event = parseTrustedKodikPlayerEvent(message, frameRef.current?.contentWindow);
      if (!event) return;

      if (event.type === "started" || event.type === "play") {
        beginPlayback();
        return;
      }
      if (event.type === "duration") {
        durationSeconds = Math.max(1, Math.floor(event.seconds));
        playerDurationReady = true;
        publish(phase === "loading" ? "ready" : phase);
        tryRestorePosition();
        return;
      }
      if (event.type === "time") {
        beginPlayback();
        playerPositionSeconds = Math.max(0, Math.floor(event.seconds));
        positionSeconds = playerPositionSeconds;
        publish(phase === "loading" ? "ready" : phase);
        if (Date.now() - lastSyncStartedAt >= HEARTBEAT_MS) syncProgress("progress");
        return;
      }
      if (event.type === "pause") {
        if (started) syncProgress("pause");
        return;
      }
      if (event.type === "ended") {
        beginPlayback();
        if (durationSeconds !== null) {
          positionSeconds = durationSeconds;
          playerPositionSeconds = durationSeconds;
        }
        syncProgress("ended");
      }
    }

    function flushWhenHidden() {
      if (document.visibilityState === "hidden") bestEffortExitSync();
    }

    function flushOnPageHide() {
      bestEffortExitSync();
    }

    window.addEventListener("message", handlePlayerMessage);
    window.addEventListener("pagehide", flushOnPageHide);
    document.addEventListener("visibilitychange", flushWhenHidden);
    return () => {
      bestEffortExitSync();
      active = false;
      controller.abort();
      window.removeEventListener("message", handlePlayerMessage);
      window.removeEventListener("pagehide", flushOnPageHide);
      document.removeEventListener("visibilitychange", flushWhenHidden);
    };
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
