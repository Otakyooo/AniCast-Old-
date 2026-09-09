"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CaretLeft,
  CaretRight,
  CaretDown,
  Check,
  MagnifyingGlass,
  X,
} from "@phosphor-icons/react";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PlaybackLink } from "./playback-link";
import { ProviderPlayer, type PlaybackProgressSnapshot } from "./provider-player";
import { SourceReportControl } from "./source-report-control";
import { getEpisodeRange, type Source, type WatchSourceGroup } from "../lib/api";
import { getTitleWatchedMarks } from "../lib/history";
import { intlLocale, type Locale } from "../i18n/config";
import type { PlaybackPresentation } from "../lib/title-template";
import { episodeCountLabel } from "../lib/episode-count";
import { summarizeEpisodeCoverage } from "../lib/episode-coverage";
import { titleWatchHref } from "../lib/seo";
import {
  filterEpisodeNumbers,
  episodeNumberRanges,
  episodeRangeIndex,
  firstRankedPlayableGroupKey,
  mergeCurrentWatchSourceGroups,
  normalizeEpisodeNumbers,
  resolveRequestedGroupKey,
  type ResolvedWatchSourceGroup,
  voiceSection,
} from "../lib/watch-controls";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

interface WatchEpisode {
  synopsis?: string | null;
  sources: Source[];
}

type Translator = (key: string, values?: Record<string, string | number>) => string;

function cleanSourceName(name: string, providerName = "") {
  const prefix = providerName ? `${providerName} · ` : "";
  return prefix && name.startsWith(prefix) ? name.slice(prefix.length) : name;
}

/** Display metadata of one rail row; absent until the range slice loads. */
interface EpisodeRailMeta {
  name: string | null;
  airDate: string | null;
}

/** Voice kinds in display order: voice-over first, subtitles, then raw. */
const KIND_ORDER = ["dub", "sub", "raw"] as const;

/** Noon-UTC anchor so a plain YYYY-MM-DD renders the same day in every zone. */
function isoDay(value: string): Date {
  return new Date(`${value}T12:00:00Z`);
}

function compactCoverage(numbers: number[], t: Translator, known: boolean) {
  if (!known) return t("watch.coverageUnknown");
  const summary = summarizeEpisodeCoverage(numbers);
  if (!summary.count || summary.first === null || summary.last === null) {
    return t("watch.coverageEmpty");
  }
  if (summary.count === 1) return t("watch.coverageSingle", { number: summary.first });

  const ranges = t("watch.coverageRanges", { ranges: summary.availableRanges.join(", ") });
  const except = t("watch.coverageExcept", {
    first: summary.first,
    last: summary.last,
    missing: summary.missingRanges.join(", "),
  });
  if (
    summary.missingRanges.length > 0
    && summary.missingRanges.length <= 3
    && summary.density >= 0.8
    && except.length < ranges.length
  ) return except;
  if (summary.availableRanges.length <= 3) return ranges;
  return t("watch.coverageWithGaps", {
    count: summary.count,
    first: summary.first,
    last: summary.last,
  });
}

function coverageCopy(
  group: ResolvedWatchSourceGroup,
  playableSet: Set<number>,
  t: Translator,
  locale: Locale,
) {
  if (!group.coverage_known) {
    return { summary: t("watch.coverageUnknown"), detail: "" };
  }
  // Only currently playable episodes count: a group can know about episodes
  // whose sources expired, and reporting them would contradict the
  // "episodes available" number shown next to the same list.
  const numbers = group.episode_numbers.filter((number) => playableSet.has(number));
  const summary = summarizeEpisodeCoverage(numbers);
  return {
    summary: t("watch.voiceCoverage", { coverage: episodeCountLabel(t, locale, summary.count) }),
    detail: compactCoverage(numbers, t, group.coverage_known),
  };
}

function PlaybackProgressStatus({ progress }: { progress: PlaybackProgressSnapshot }) {
  const { t } = useI18n();
  // Idle confirmations ("saved automatically", "episode watched") are one-time
  // notices, not interface furniture: they dismiss themselves after a pause.
  // Busy, guest and error states stay until they resolve.
  const idle = progress.phase === "ready" || progress.phase === "saved";
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!idle) return;
    const timer = window.setTimeout(() => setDismissed(true), 5000);
    return () => window.clearTimeout(timer);
  }, [idle, progress.phase, progress.isWatched]);

  if (idle && dismissed) return null;

  const title = progress.phase === "guest"
    ? t("watch.progressGuest")
    : progress.phase === "error"
      ? t("watch.progressError")
      : progress.isWatched
        ? t("watch.progressCompleted")
        : progress.phase === "saving"
          ? t("watch.progressSaving")
          : progress.phase === "loading"
            ? t("watch.progressLoading")
            : t("watch.progressAutomatic");

  // The player's own timeline is the single position display; this line only
  // reports whether progress is being saved.
  return (
    <div className={styles.watchProgress} aria-busy={progress.phase === "loading" || progress.phase === "saving"}>
      <div className={styles.watchProgressCopy}>
        <strong>{title}</strong>
        {progress.phase === "guest" && <Link href="/login">{t("common.login")}</Link>}
      </div>
    </div>
  );
}

interface WatchSpaceProps {
  slug: string;
  titleName: string;
  playableEpisodeNumbers: number[];
  sourceGroups: WatchSourceGroup[];
  requestedSourceKey?: string;
  currentNumber: number;
  playbackPresentation: PlaybackPresentation;
  navigationDegraded?: boolean;
  invalidEpisodeRequest?: boolean;
  episode: WatchEpisode;
}

export function WatchSpace(props: WatchSpaceProps) {
  return <TitleWatchSpace key={props.slug} {...props} />;
}

const AUTOPLAY_COUNTDOWN_SECONDS = 10;

function TitleWatchSpace({
  slug,
  titleName,
  playableEpisodeNumbers,
  sourceGroups,
  requestedSourceKey,
  currentNumber,
  playbackPresentation,
  navigationDegraded = false,
  invalidEpisodeRequest = false,
  episode,
}: WatchSpaceProps) {
  const { t, locale } = useI18n();
  const router = useRouter();
  const singlePlayback = playbackPresentation === "single";
  const playableSources = useMemo(
    () => episode.sources.filter((source) => source.playback_available),
    [episode.sources],
  );
  const playableSourceKeys = useMemo(
    () => playableSources.map((source) => source.selection_key).filter(Boolean),
    [playableSources],
  );
  const groups = useMemo(
    () => mergeCurrentWatchSourceGroups(
      sourceGroups,
      playableSources,
      currentNumber,
      singlePlayback,
    ),
    [currentNumber, playableSources, singlePlayback, sourceGroups],
  );
  const requestedGroup = resolveRequestedGroupKey(groups, requestedSourceKey);
  const groupsByKind = useMemo(() => {
    const byKind = new Map<string, ResolvedWatchSourceGroup[]>();
    for (const group of groups) {
      const section = voiceSection(group.kind);
      byKind.set(section, [...(byKind.get(section) ?? []), group]);
    }
    return byKind;
  }, [groups]);
  const preferredKey = requestedGroup?.key
    ?? firstRankedPlayableGroupKey(
      groups,
      playableSourceKeys,
      currentNumber,
    );
  const selectionScope = `${currentNumber}:${preferredKey}`;
  const [groupChoice, setGroupChoice] = useState<{ scope: string; key: string } | null>(null);
  const selectedGroupKey = groupChoice?.scope === selectionScope ? groupChoice.key : preferredKey;
  const [episodeQuery, setEpisodeQuery] = useState("");
  const [rangeChoice, setRangeChoice] = useState<{ scope: string; index: number } | null>(null);
  const [episodeDialogMounted, setEpisodeDialogMounted] = useState(false);
  const [progressResult, setProgressResult] = useState<{ scope: string; progress: PlaybackProgressSnapshot } | null>(null);
  const [episodeMeta, setEpisodeMeta] = useState<Map<number, EpisodeRailMeta>>(new Map());
  const [watchedNumbers, setWatchedNumbers] = useState<Set<number> | null>(null);
  const [completedNumbers, setCompletedNumbers] = useState<Set<number>>(new Set());
  const [autoplaySeconds, setAutoplaySeconds] = useState<number | null>(null);
  const episodeDialogRef = useRef<HTMLDialogElement>(null);
  const episodeTriggerRef = useRef<HTMLButtonElement>(null);
  const episodeRailSearchRef = useRef<HTMLInputElement>(null);
  const episodeDialogSearchRef = useRef<HTMLInputElement>(null);
  const episodeRailContentRef = useRef<HTMLDivElement>(null);
  const currentEpisodeRef = useRef<HTMLAnchorElement>(null);

  const selectedGroup = groups.find((group) => group.key === selectedGroupKey) ?? null;
  const selectedSources = playableSources.filter(
    (source) => source.selection_key === selectedGroupKey,
  );
  const chosen = selectedSources[0] ?? null;
  const progressScope = `${currentNumber}:${chosen?.id}`;
  const playbackProgress = progressResult?.scope === progressScope ? progressResult.progress : null;
  const playableNumbers = useMemo(
    () => normalizeEpisodeNumbers(playableEpisodeNumbers),
    [playableEpisodeNumbers],
  );
  const playableSet = useMemo(() => new Set(playableNumbers), [playableNumbers]);
  const availableNumbers = useMemo(
    () => new Set(selectedGroup?.episode_numbers ?? playableNumbers),
    [playableNumbers, selectedGroup],
  );
  const currentIsAvailable = availableNumbers.has(currentNumber);
  const availableEpisodeNumbers = useMemo(
    () => playableNumbers.filter((number) => availableNumbers.has(number)),
    [playableNumbers, availableNumbers],
  );
  const episodeRanges = useMemo(
    () => episodeNumberRanges(availableEpisodeNumbers),
    [availableEpisodeNumbers],
  );
  const currentRangeIndex = episodeRangeIndex(episodeRanges, currentNumber);
  const rangeScope = `${currentNumber}:${selectedGroupKey}:${currentRangeIndex}`;
  const selectedRangeIndex = rangeChoice?.scope === rangeScope ? rangeChoice.index : currentRangeIndex;
  const searchedEpisodeNumbers = useMemo(
    () => filterEpisodeNumbers(availableEpisodeNumbers, episodeQuery),
    [availableEpisodeNumbers, episodeQuery],
  );
  const visibleEpisodeNumbers = useMemo(
    () => episodeQuery
      ? searchedEpisodeNumbers
      : episodeRanges[selectedRangeIndex]?.numbers ?? [],
    [episodeQuery, episodeRanges, searchedEpisodeNumbers, selectedRangeIndex],
  );
  const previousNumber = availableEpisodeNumbers.filter((number) => number < currentNumber).at(-1);
  const nextNumber = availableEpisodeNumbers.find((number) => number > currentNumber);
  const selectedName = selectedGroup
    ? cleanSourceName(selectedGroup.name, selectedGroup.provider_name)
    : "";
  const invalidVoiceRequest = Boolean(requestedSourceKey && !requestedGroup);
  const handleProgressChange = useCallback((progress: PlaybackProgressSnapshot) => {
    setProgressResult({ scope: progressScope, progress });
    if (progress.isWatched) {
      setCompletedNumbers((current) => {
        if (current.has(currentNumber)) return current;
        return new Set([...current, currentNumber]);
      });
    }
  }, [currentNumber, progressScope]);

  /** The provider's own "ended" event is the only autoplay trigger: a high
   * progress percentage alone cannot distinguish a finished episode from a
   * resumed one. */
  const handleEnded = useCallback(() => {
    if (singlePlayback) return;
    if (nextNumber === undefined) return;
    setAutoplaySeconds(AUTOPLAY_COUNTDOWN_SECONDS);
  }, [nextNumber, singlePlayback]);

  // Countdown to the next episode. State changes live inside the timer
  // callback; leaving the page, cancelling or a route change clears the
  // timer together with the component state.
  useEffect(() => {
    if (autoplaySeconds === null) return;
    const timer = window.setTimeout(() => {
      if (autoplaySeconds <= 1) {
        if (nextNumber !== undefined) {
          router.push(titleWatchHref(slug, nextNumber, selectedGroupKey), { scroll: false });
        }
        setAutoplaySeconds(null);
        return;
      }
      setAutoplaySeconds(autoplaySeconds - 1);
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [autoplaySeconds, nextNumber, router, selectedGroupKey, slug]);

  // Watched marks come from the viewer's own history; guests and API failures
  // keep `null`, which renders the rail without marks instead of guessing.
  useEffect(() => {
    const controller = new AbortController();
    getTitleWatchedMarks(slug, controller.signal)
      .then((marks) => {
        if (marks) setWatchedNumbers(new Set(marks.watched_episode_numbers));
      })
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
      });
    return () => controller.abort();
  }, [slug]);

  // Lazily enrich the visible range with names and air dates. Search results
  // stay number-only: a numeric query matches scattered numbers whose span
  // can exceed the backend window, and the number is the searched fact.
  // Fetches are deliberately not aborted: the merge is idempotent and keyed
  // by episode number, so a completed late fetch still enriches the rail,
  // while the shared 10s request timeout bounds any stall.
  const loadedRangesRef = useRef(new Set<string>());
  const activeRange = !episodeQuery ? episodeRanges[selectedRangeIndex] : null;
  useEffect(() => {
    if (!activeRange) return;
    const rangeKey = `${slug}:${activeRange.first}-${activeRange.last}`;
    if (loadedRangesRef.current.has(rangeKey)) return;
    loadedRangesRef.current.add(rangeKey);
    getEpisodeRange(slug, activeRange.first, activeRange.last)
      .then((rows) => {
        setEpisodeMeta((current) => {
          const next = new Map(current);
          for (const row of rows) {
            next.set(row.number, { name: row.name || null, airDate: row.air_date ?? null });
          }
          return next;
        });
      })
      .catch(() => {
        // A failed slice stays retryable the next time the range is shown.
        loadedRangesRef.current.delete(rangeKey);
      });
  }, [slug, activeRange]);

  const shortDayFormatter = useMemo(
    // The year is not optional: long series span decades of air dates, and a
    // bare "20 окт." next to a 1999 title reads as this October.
    () => new Intl.DateTimeFormat(intlLocale[locale], { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }),
    [locale],
  );

  useEffect(() => {
    if (!invalidEpisodeRequest && !invalidVoiceRequest && !requestedGroup?.legacy) return;
    // Normalize invalid and legacy UI state without a redirect or a second
    // server navigation that could interrupt playback.
    window.history.replaceState(
      window.history.state,
      "",
      titleWatchHref(slug, currentNumber, selectedGroupKey),
    );
  }, [
    currentNumber,
    invalidEpisodeRequest,
    invalidVoiceRequest,
    requestedGroup?.legacy,
    selectedGroupKey,
    slug,
  ]);

  useEffect(() => {
    if (
      episodeQuery
      || window.matchMedia("(max-width: 860px)").matches
      || !currentEpisodeRef.current
      || !episodeRailContentRef.current
    ) return;
    const list = episodeRailContentRef.current;
    const item = currentEpisodeRef.current;
    list.scrollTop = Math.max(0, item.offsetTop - (list.clientHeight - item.clientHeight) / 2);
  }, [currentNumber, episodeQuery, selectedGroupKey, selectedRangeIndex]);

  useEffect(() => {
    if (!episodeDialogMounted || !episodeDialogRef.current) return;
    episodeDialogRef.current.showModal();
    requestAnimationFrame(() => episodeDialogSearchRef.current?.focus());
  }, [episodeDialogMounted]);

  function chooseGroup(key: string) {
    if (key === selectedGroupKey) return;
    setEpisodeQuery("");
    setGroupChoice({ scope: selectionScope, key });
    router.replace(titleWatchHref(slug, currentNumber, key), { scroll: false });
  }

  function chooseEpisode(number: number) {
    router.push(titleWatchHref(slug, number, selectedGroupKey), { scroll: false });
  }

  function submitEpisodeSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!visibleEpisodeNumbers.length) return;
    chooseEpisode(visibleEpisodeNumbers[0]);
    setEpisodeQuery("");
    episodeDialogRef.current?.close();
  }

  function openEpisodeChooser() {
    if (!availableEpisodeNumbers.length) return;
    if (window.matchMedia("(max-width: 860px)").matches) {
      setEpisodeDialogMounted(true);
      return;
    }
    episodeRailSearchRef.current?.focus();
    episodeRailSearchRef.current?.select();
  }

  const playerTitle = singlePlayback
    ? `${titleName} · ${selectedName || t("watch.noVoice")}`
    : `${selectedName || t("watch.noVoice")} · ${t("episode.number", { number: currentNumber })}`;
  const player = chosen?.playback_mode === "iframe_embed" ? (
    <ProviderPlayer
      key={chosen.id}
      sourceId={chosen.id}
      playbackMode={chosen.playback_mode}
      title={playerTitle}
      slug={slug}
      episodeNumber={currentNumber}
      onProgressChange={handleProgressChange}
      onEnded={handleEnded}
    />
  ) : chosen ? (
    <section className={`${styles.playerShell} ${styles.playerPreview}`} aria-label={playerTitle}>
      <div className={styles.playerPreviewBody}>
        <PlaybackLink
          sourceId={chosen.id}
          playbackMode={chosen.playback_mode}
          slug={slug}
          episodeNumber={currentNumber}
          label={singlePlayback ? t("watch.title") : t("watch.playEpisode", { number: currentNumber })}
          className={styles.playerLaunch}
        />
      </div>
    </section>
  ) : (
    <div className={styles.watchEmpty}>
      <strong>{groups.length ? t("watch.noPlayer") : t("watch.noPlayableTitle")}</strong>
      <span>{groups.length && !singlePlayback
        ? t("watch.chooseAvailableEpisode")
        : t("watch.noPlayableText")}</span>
    </div>
  );

  const episodeList = (closeDialog = false) => visibleEpisodeNumbers.map((number) => {
    const current = number === currentNumber;
    const meta = episodeMeta.get(number);
    const watched = completedNumbers.has(number) || (watchedNumbers?.has(number) ?? false);
    const airDay = meta?.airDate && !Number.isNaN(Date.parse(`${meta.airDate}T12:00:00Z`))
      ? shortDayFormatter.format(isoDay(meta.airDate))
      : null;
    return (
      <li key={number}>
        <Link
          ref={closeDialog ? undefined : current ? currentEpisodeRef : undefined}
          href={titleWatchHref(slug, number, selectedGroupKey)}
          aria-current={current ? "page" : undefined}
          aria-label={[
            t("episode.number", { number }),
            meta?.name ?? "",
            watched ? t("watch.watchedMark") : "",
          ].filter(Boolean).join(" · ")}
          scroll={false}
          prefetch={false}
          onClick={() => { setEpisodeQuery(""); if (closeDialog) episodeDialogRef.current?.close(); }}
        >
          <span className={styles.episodeRowMain}>
            <span className={styles.episodeRowNumber}>{t("episode.number", { number })}</span>
            {meta?.name && <small className={styles.episodeRowName}>{meta.name}</small>}
          </span>
          <span className={styles.episodeRowAside}>
            {current && <small>{t("watch.currentEpisode")}</small>}
            {airDay && <time className={styles.episodeAirDate} dateTime={meta?.airDate ?? undefined}>{airDay}</time>}
            {watched && (
              <span className={styles.episodeWatched} title={t("watch.watchedMark")}>
                <Check aria-hidden="true" weight="bold" />
              </span>
            )}
          </span>
        </Link>
      </li>
    );
  });

  const episodeRangeControl = (id: string) => episodeRanges.length > 1 && !episodeQuery ? (
    <label className={styles.episodeRangeField} htmlFor={id}>
      <span>{t("watch.episodeRange")}</span>
      {/* Native select keeps keyboard and screen-reader behavior; the custom
          caret aligns its closed state with the other controls. */}
      <span className={styles.episodeRangeSelect}>
        <select
          id={id}
          value={selectedRangeIndex}
          onChange={(event) => setRangeChoice({ scope: rangeScope, index: Number(event.target.value) })}
        >
          {episodeRanges.map((range, index) => (
            <option value={index} key={`${range.first}-${range.last}`}>
              {t("watch.episodeRangeOption", { first: range.first, last: range.last })}
            </option>
          ))}
        </select>
        <CaretDown aria-hidden="true" weight="bold" />
      </span>
    </label>
  ) : null;

  return (
    <div className={styles.watchLayout}>
      {(invalidEpisodeRequest || invalidVoiceRequest || navigationDegraded) && (
        <div className={styles.watchNotices}>
          {invalidEpisodeRequest && (
            <p className={styles.watchNotice} role="status">
              {t("watch.episodeRequestCorrected", { number: currentNumber })}
            </p>
          )}
          {invalidVoiceRequest && (
            <p className={styles.watchNotice} role="status">{t("watch.voiceRequestCorrected")}</p>
          )}
          {navigationDegraded && (
            <p className={styles.watchNotice} role="status">
              <span>{t("watch.navigationUnavailable")}</span>
              <button type="button" onClick={() => router.refresh()}>{t("common.retry")}</button>
            </p>
          )}
        </div>
      )}
      {/* Single-playback titles (movies) have no episode rail: the stage spans
          the full column and voice choice lives in the selects below. */}
      <div className={`${styles.watchStage} ${singlePlayback ? styles.watchStageFull : ""}`}>
        <div className={styles.watchPlayer}>
          {player}
          {/* Explicit next-episode scenario after the provider reports the end:
              a countdown the viewer can cancel, instead of a silent jump or a
              dead stop. */}
          {autoplaySeconds !== null && nextNumber !== undefined && (
            <div className={styles.autoplayBar} role="status">
              <span>{t("watch.autoplayNext", { seconds: autoplaySeconds })}</span>
              <Link
                className={styles.autoplayNext}
                href={titleWatchHref(slug, nextNumber, selectedGroupKey)}
                onClick={() => setAutoplaySeconds(null)}
              >
                {t("watch.next")}
              </Link>
              <button type="button" onClick={() => setAutoplaySeconds(null)}>
                {t("watch.autoplayCancel")}
              </button>
            </div>
          )}
        </div>

        {/* Episode controls under the player on every viewport: big obvious
            prev/next steps plus the current-episode chooser. */}
        {!singlePlayback && (
          <nav className={styles.watchControls} aria-label={t("watch.navigation")}>
            {previousNumber !== undefined ? (
              <Link
                className={styles.episodeStep}
                href={titleWatchHref(slug, previousNumber, selectedGroupKey)}
                aria-label={t("watch.prev")}
                title={t("watch.prev")}
              >
                <CaretLeft aria-hidden="true" weight="bold" />
                <span>{t("watch.prev")}</span>
              </Link>
            ) : (
              <span className={styles.episodeStep} aria-disabled="true">
                <CaretLeft aria-hidden="true" weight="bold" />
                <span>{t("watch.prev")}</span>
              </span>
            )}

            <button
              ref={episodeTriggerRef}
              className={styles.currentEpisodeButton}
              type="button"
              aria-haspopup={availableEpisodeNumbers.length ? "dialog" : undefined}
              disabled={!availableEpisodeNumbers.length}
              onClick={openEpisodeChooser}
            >
              <strong>{t("episode.number", { number: currentNumber })}</strong>
              <span>{t("watch.availableEpisodeCount", { count: availableEpisodeNumbers.length })}</span>
            </button>

            {nextNumber !== undefined ? (
              <Link
                className={styles.episodeStep}
                href={titleWatchHref(slug, nextNumber, selectedGroupKey)}
                aria-label={t("watch.next")}
                title={t("watch.next")}
              >
                <span>{t("watch.next")}</span>
                <CaretRight aria-hidden="true" weight="bold" />
              </Link>
            ) : (
              <span className={styles.episodeStep} aria-disabled="true">
                <span>{t("watch.next")}</span>
                <CaretRight aria-hidden="true" weight="bold" />
              </span>
            )}

            {!currentIsAvailable && selectedGroup && (
              <p className={styles.watchWarning} role="status">
                {t("watch.voiceUnavailable", { number: currentNumber, name: selectedName })}
              </p>
            )}
          </nav>
        )}

        {!singlePlayback && (
          <aside className={styles.episodeRail} aria-label={t("watch.navigation")}>
            {availableEpisodeNumbers.length > 0 && (
              <div className={styles.episodeRailTools}>
                {/* Prev/next live in the big control bar under the player;
                    the rail toolbar keeps only the number search. */}
                <form className={styles.episodeSearch} onSubmit={submitEpisodeSearch} role="search">
                  <MagnifyingGlass aria-hidden="true" />
                  <label htmlFor="watch-episode-search">{t("watch.episodeSearch")}</label>
                  <input
                    ref={episodeRailSearchRef}
                    id="watch-episode-search"
                    type="search"
                    inputMode="numeric"
                    value={episodeQuery}
                    placeholder={t("watch.episodeSearchPlaceholder")}
                    onChange={(event) => setEpisodeQuery(event.target.value)}
                  />
                </form>
              </div>
            )}

            <div ref={episodeRailContentRef} className={styles.episodeRailContent}>
              {!currentIsAvailable && selectedGroup && (
                <p className={styles.railWarning} role="status">
                  {t("watch.voiceUnavailable", { number: currentNumber, name: selectedName })}
                </p>
              )}
              <div className={styles.episodeRailHeading}>
                <h3>{t("title.episodes")}</h3>
                <span>{t("watch.availableEpisodeCount", { count: availableEpisodeNumbers.length })}</span>
              </div>
              {episodeRangeControl("watch-episode-range")}
              <ol className={styles.episodeRailList}>{episodeList()}</ol>
              {!visibleEpisodeNumbers.length && (
                <p className={styles.episodeSearchEmpty} role="status">{t("watch.episodeSearchEmpty")}</p>
              )}
            </div>
          </aside>
        )}

        {!singlePlayback && availableEpisodeNumbers.length > 0 && episodeDialogMounted && <dialog
          ref={episodeDialogRef}
          className={styles.watchDialog}
          aria-labelledby="watch-episode-dialog-title"
          onClick={(event) => {
            if (event.currentTarget === event.target) episodeDialogRef.current?.close();
          }}
          onClose={() => {
            setEpisodeDialogMounted(false);
            episodeTriggerRef.current?.focus();
          }}
        >
          <div className={styles.dialogPanel}>
            <header className={styles.dialogHeader}>
              <div>
                <h3 id="watch-episode-dialog-title">{t("watch.episodeDialogTitle")}</h3>
                <span>{t("watch.availableEpisodeCount", { count: availableEpisodeNumbers.length })}</span>
              </div>
              <button type="button" onClick={() => episodeDialogRef.current?.close()} aria-label={t("watch.closeChooser")}>
                <X aria-hidden="true" weight="bold" />
              </button>
            </header>
            <form className={styles.episodeSearch} onSubmit={submitEpisodeSearch} role="search">
              <MagnifyingGlass aria-hidden="true" />
              <label htmlFor="watch-episode-dialog-search">{t("watch.episodeSearch")}</label>
              <input
                ref={episodeDialogSearchRef}
                id="watch-episode-dialog-search"
                type="search"
                inputMode="numeric"
                value={episodeQuery}
                placeholder={t("watch.episodeSearchPlaceholder")}
                onChange={(event) => setEpisodeQuery(event.target.value)}
              />
            </form>
            {episodeRangeControl("watch-episode-dialog-range")}
            <ol className={styles.dialogEpisodeList}>{episodeList(true)}</ol>
            {!visibleEpisodeNumbers.length && (
              <p className={styles.episodeSearchEmpty} role="status">{t("watch.episodeSearchEmpty")}</p>
            )}
          </div>
        </dialog>}

      </div>

      {/* The voice selector: one labeled dropdown per kind (voice-over /
          subtitles / original) under the player. Scales to any number of
          teams; the coverage breakdown stays in each option's label. */}
      {groups.length > 0 && (
        <div className={styles.voiceSelects} role="group" aria-label={t("watch.voiceOptionsTitle")}>
          {KIND_ORDER.filter((kind) => groupsByKind.get(kind)?.length).map((kind) => {
            const sectionGroups = groupsByKind.get(kind) ?? [];
            const sectionHasSelection = sectionGroups.some((group) => group.key === selectedGroupKey);
            return (
              <label className={styles.voiceSelect} key={kind}>
                <span>{t(`watch.voiceGroup.${kind}`)}</span>
                <span className={styles.voiceSelectControl}>
                  <select
                    value={sectionHasSelection ? selectedGroupKey : ""}
                    onChange={(event) => {
                      if (event.target.value) chooseGroup(event.target.value);
                    }}
                  >
                    {!sectionHasSelection && <option value="">{t("watch.voiceNone")}</option>}
                    {sectionGroups.map((group) => {
                      const name = cleanSourceName(group.name, group.provider_name);
                      const coverage = coverageCopy(group, playableSet, t, locale);
                      return (
                        <option value={group.key} key={group.key}>
                          {[name, coverage.summary].filter(Boolean).join(" · ")}
                        </option>
                      );
                    })}
                  </select>
                  <CaretDown aria-hidden="true" weight="bold" />
                </span>
              </label>
            );
          })}
        </div>
      )}

      <div className={styles.watchUtilityBar} aria-label={t(singlePlayback ? "watch.titleActions" : "watch.episodeActions")}>
        {chosen?.playback_mode === "iframe_embed" && playbackProgress && (
          <PlaybackProgressStatus key={`${playbackProgress.phase}:${playbackProgress.isWatched}`} progress={playbackProgress} />
        )}
        {chosen && <SourceReportControl sourceId={chosen.id} key={chosen.id} />}
      </div>

      {episode.synopsis && <p className={styles.watchSynopsis}>{episode.synopsis}</p>}
    </div>
  );
}
