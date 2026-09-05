"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CaretLeft,
  CaretRight,
  CaretDown,
  Check,
  MagnifyingGlass,
  SpeakerHigh,
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

function coverageCopy(group: ResolvedWatchSourceGroup, t: Translator, locale: Locale) {
  if (!group.coverage_known) {
    return { summary: t("watch.coverageUnknown"), detail: "" };
  }
  const summary = summarizeEpisodeCoverage(group.episode_numbers);
  return {
    // The per-voice count never competes with the title total: it is phrased
    // as "available" and lives only inside the voice panel.
    summary: t("watch.voiceCoverage", { coverage: episodeCountLabel(t, locale, summary.count) }),
    detail: compactCoverage(group.episode_numbers, t, group.coverage_known),
  };
}

function PlaybackProgressStatus({ progress }: { progress: PlaybackProgressSnapshot }) {
  const { t } = useI18n();
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

  // This line reports only whether progress is being saved. The player's own
  // timeline is the single position display: a second time readout here
  // contradicted it whenever the provider resumed on its own, and a second
  // bar restated the same fact as a third strip on screen.
  return (
    <div className={styles.watchProgress} aria-busy={progress.phase === "loading" || progress.phase === "saving"}>
      <div className={styles.watchProgressCopy}>
        <strong>{title}</strong>
        {progress.phase === "guest" && <Link href="/login">{t("common.login")}</Link>}
      </div>
    </div>
  );
}

export function WatchSpace({
  slug,
  titleName,
  playableEpisodeNumbers,
  sourceGroups,
  requestedSourceKey,
  currentNumber,
  playbackPresentation,
  navigationDegraded = false,
  invalidEpisodeRequest = false,
  catalogEpisodeCount,
  episode,
}: {
  slug: string;
  titleName: string;
  playableEpisodeNumbers: number[];
  sourceGroups: WatchSourceGroup[];
  requestedSourceKey?: string;
  currentNumber: number;
  playbackPresentation: PlaybackPresentation;
  navigationDegraded?: boolean;
  invalidEpisodeRequest?: boolean;
  /** Episode total of the title itself; 0 when the backend reports none. */
  catalogEpisodeCount?: number;
  episode: WatchEpisode;
}) {
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
  const preferredKey = requestedGroup?.key
    ?? firstRankedPlayableGroupKey(
      groups,
      playableSourceKeys,
      currentNumber,
    );
  const [selectedGroupKey, setSelectedGroupKey] = useState(preferredKey);
  const [episodeQuery, setEpisodeQuery] = useState("");
  const [selectedRangeIndex, setSelectedRangeIndex] = useState(0);
  const [voiceOptionsOpen, setVoiceOptionsOpen] = useState(false);
  const [episodeDialogMounted, setEpisodeDialogMounted] = useState(false);
  const [playbackProgress, setPlaybackProgress] = useState<PlaybackProgressSnapshot | null>(null);
  const [episodeMeta, setEpisodeMeta] = useState<Map<number, EpisodeRailMeta>>(new Map());
  const [watchedNumbers, setWatchedNumbers] = useState<Set<number> | null>(null);
  const episodeDialogRef = useRef<HTMLDialogElement>(null);
  const episodeTriggerRef = useRef<HTMLButtonElement>(null);
  const mobileVoiceTriggerRef = useRef<HTMLButtonElement>(null);
  const railVoiceTriggerRef = useRef<HTMLButtonElement>(null);
  const lastVoiceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const episodeRailSearchRef = useRef<HTMLInputElement>(null);
  const episodeDialogSearchRef = useRef<HTMLInputElement>(null);
  const episodeRailContentRef = useRef<HTMLDivElement>(null);
  const currentEpisodeRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    setSelectedGroupKey(preferredKey);
  }, [currentNumber, preferredKey]);

  const selectedGroup = groups.find((group) => group.key === selectedGroupKey) ?? null;
  const selectedSources = playableSources.filter(
    (source) => source.selection_key === selectedGroupKey,
  );
  const chosen = selectedSources[0] ?? null;
  const playableNumbers = useMemo(
    () => normalizeEpisodeNumbers(playableEpisodeNumbers),
    [playableEpisodeNumbers],
  );
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
  // One honest number in the triggers: the title's own episode total. The
  // per-voice coverage is spelled out only inside the voice panel, so two
  // totals never compete on screen ("1120 из 1176" next to "1180").
  const catalogEpisodeTotal = (catalogEpisodeCount ?? 0) > 0
    ? episodeCountLabel(t, locale, catalogEpisodeCount ?? 0)
    : availableEpisodeNumbers.length > 0
      ? episodeCountLabel(t, locale, availableEpisodeNumbers.length)
      : "";
  const selectedKindLabel = selectedGroup
    ? t(`watch.voiceGroup.${voiceSection(selectedGroup.kind)}`)
    : "";
  const invalidVoiceRequest = Boolean(requestedSourceKey && !requestedGroup);
  const handleProgressChange = useCallback((progress: PlaybackProgressSnapshot) => {
    setPlaybackProgress(progress);
  }, []);

  useEffect(() => {
    setPlaybackProgress(null);
  }, [chosen?.id, currentNumber]);

  useEffect(() => {
    setSelectedRangeIndex(currentRangeIndex);
  }, [currentRangeIndex, selectedGroupKey]);

  // Watched marks come from the viewer's own history; guests and API failures
  // keep `null`, which renders the rail without marks instead of guessing.
  useEffect(() => {
    const controller = new AbortController();
    setWatchedNumbers(null);
    getTitleWatchedMarks(slug, controller.signal)
      .then((marks) => {
        if (marks) setWatchedNumbers(new Set(marks.watched_episode_numbers));
      })
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
      });
    return () => controller.abort();
  }, [slug]);

  // The player itself confirms the current episode, so its mark appears the
  // moment playback reports completion instead of waiting for a refetch.
  useEffect(() => {
    if (!playbackProgress?.isWatched) return;
    setWatchedNumbers((current) => {
      if (!current || current.has(currentNumber)) return current;
      const next = new Set(current);
      next.add(currentNumber);
      return next;
    });
  }, [playbackProgress?.isWatched, currentNumber]);

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
    () => new Intl.DateTimeFormat(intlLocale[locale], { day: "numeric", month: "short", timeZone: "UTC" }),
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
      || voiceOptionsOpen
      || window.matchMedia("(max-width: 860px)").matches
      || !currentEpisodeRef.current
      || !episodeRailContentRef.current
    ) return;
    const list = episodeRailContentRef.current;
    const item = currentEpisodeRef.current;
    list.scrollTop = Math.max(0, item.offsetTop - (list.clientHeight - item.clientHeight) / 2);
  }, [currentNumber, episodeQuery, selectedGroupKey, selectedRangeIndex, voiceOptionsOpen]);

  useEffect(() => {
    if (!voiceOptionsOpen) return;
    function closeVoiceOptions(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setVoiceOptionsOpen(false);
      requestAnimationFrame(() => lastVoiceTriggerRef.current?.focus());
    }
    window.addEventListener("keydown", closeVoiceOptions);
    return () => window.removeEventListener("keydown", closeVoiceOptions);
  }, [voiceOptionsOpen]);

  useEffect(() => {
    if (!episodeDialogMounted || !episodeDialogRef.current) return;
    episodeDialogRef.current.showModal();
    requestAnimationFrame(() => episodeDialogSearchRef.current?.focus());
  }, [episodeDialogMounted]);

  function chooseGroup(key: string) {
    setSelectedGroupKey(key);
    setVoiceOptionsOpen(false);
    router.replace(titleWatchHref(slug, currentNumber, key), { scroll: false });
    requestAnimationFrame(() => lastVoiceTriggerRef.current?.focus());
  }

  function toggleVoiceOptions(trigger: HTMLButtonElement) {
    lastVoiceTriggerRef.current = trigger;
    const opening = !voiceOptionsOpen;
    setVoiceOptionsOpen(opening);
    if (opening && !window.matchMedia("(max-width: 860px)").matches) {
      requestAnimationFrame(() => { if (episodeRailContentRef.current) episodeRailContentRef.current.scrollTop = 0; });
    }
  }

  function chooseEpisode(number: number) {
    router.push(titleWatchHref(slug, number, selectedGroupKey), { scroll: false });
  }

  function submitEpisodeSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!visibleEpisodeNumbers.length) return;
    chooseEpisode(visibleEpisodeNumbers[0]);
    episodeDialogRef.current?.close();
  }

  function openEpisodeChooser() {
    if (!availableEpisodeNumbers.length) return;
    if (window.matchMedia("(max-width: 860px)").matches) {
      setVoiceOptionsOpen(false);
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
    const watched = watchedNumbers?.has(number) ?? false;
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
          onClick={() => { if (closeDialog) episodeDialogRef.current?.close(); }}
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
          onChange={(event) => setSelectedRangeIndex(Number(event.target.value))}
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

  const voiceOptions = (id: string) => (
    <section id={id} className={styles.inlineVoicePanel} aria-label={t("watch.voiceOptionsTitle")}>
      <h4>{t("watch.voiceOptionsTitle")}</h4>
      <div className={styles.inlineVoiceOptions}>
        {groups.map((group) => {
          const coverage = coverageCopy(group, t, locale);
          const kind = t(`watch.voiceGroup.${voiceSection(group.kind)}`);
          const selected = group.key === selectedGroupKey;
          return (
            <button
              type="button"
              aria-pressed={selected}
              className={selected ? styles.voiceOptionSelected : undefined}
              onClick={() => chooseGroup(group.key)}
              key={group.key}
            >
              <span className={styles.voiceOptionCopy}>
                <strong>{cleanSourceName(group.name, group.provider_name)}</strong>
                <small>{singlePlayback ? kind : t("watch.voiceOptionMeta", {
                  kind,
                  coverage: coverage.summary,
                })}</small>
                {!singlePlayback && coverage.detail && <small>{coverage.detail}</small>}
              </span>
              {selected && <Check className={styles.voiceSelectedIcon} aria-hidden="true" weight="bold" />}
            </button>
          );
        })}
        {!groups.length && <p className={styles.episodeSearchEmpty}>{t("watch.noVoice")}</p>}
      </div>
    </section>
  );

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
      <div className={styles.watchStage}>
        <div className={styles.watchPlayer}>{player}</div>

        <nav className={styles.watchControls} aria-label={t("watch.navigation")}>
          {!singlePlayback && (previousNumber !== undefined ? (
            <Link
              className={styles.episodeStep}
              href={titleWatchHref(slug, previousNumber, selectedGroupKey)}
              aria-label={t("watch.prev")}
              title={t("watch.prev")}
            >
              <CaretLeft aria-hidden="true" weight="bold" />
            </Link>
          ) : (
            <span className={styles.episodeStep} aria-disabled="true">
              <CaretLeft aria-hidden="true" weight="bold" />
            </span>
          ))}

          {!singlePlayback && <button
            ref={episodeTriggerRef}
            className={styles.currentEpisodeButton}
            type="button"
            aria-haspopup={availableEpisodeNumbers.length ? "dialog" : undefined}
            disabled={!availableEpisodeNumbers.length}
            onClick={openEpisodeChooser}
          >
            <strong>{t("episode.number", { number: currentNumber })}</strong>
            <span>{t("watch.availableEpisodeCount", { count: availableEpisodeNumbers.length })}</span>
          </button>}

          {!singlePlayback && (nextNumber !== undefined ? (
            <Link
              className={styles.episodeStep}
              href={titleWatchHref(slug, nextNumber, selectedGroupKey)}
              aria-label={t("watch.next")}
              title={t("watch.next")}
            >
              <CaretRight aria-hidden="true" weight="bold" />
            </Link>
          ) : (
            <span className={styles.episodeStep} aria-disabled="true">
              <CaretRight aria-hidden="true" weight="bold" />
            </span>
          ))}

          <button
            ref={mobileVoiceTriggerRef}
            className={styles.voiceTrigger}
            type="button"
            aria-expanded={voiceOptionsOpen}
            aria-controls="watch-voice-options-mobile"
            disabled={!groups.length}
            onClick={(event) => toggleVoiceOptions(event.currentTarget)}
          >
            <SpeakerHigh aria-hidden="true" weight="bold" />
            <span>
              <small>{selectedGroup
                ? singlePlayback
                  ? selectedKindLabel
                  : catalogEpisodeTotal
                : t("watch.voiceShort")}</small>
              <strong>{selectedName || t("watch.noVoice")}</strong>
            </span>
            <CaretDown aria-hidden="true" weight="bold" />
          </button>

          {voiceOptionsOpen && (
            <div className={styles.mobileVoicePanel}>
              {voiceOptions("watch-voice-options-mobile")}
            </div>
          )}

          {!singlePlayback && !currentIsAvailable && selectedGroup && (
            <p className={styles.watchWarning} role="status">
              {t("watch.voiceUnavailable", { number: currentNumber, name: selectedName })}
            </p>
          )}
        </nav>

        <aside className={styles.episodeRail} aria-label={singlePlayback ? t("watch.voiceOptionsTitle") : t("watch.navigation")}>
          {singlePlayback ? (
            <div ref={episodeRailContentRef} className={styles.episodeRailContent}>
              {voiceOptions("watch-voice-options-desktop")}
            </div>
          ) : (
            <>
          <div className={styles.episodeRailHeader}>
            <button
              ref={railVoiceTriggerRef}
              className={styles.railVoiceTrigger}
              type="button"
              aria-expanded={voiceOptionsOpen}
              aria-controls="watch-voice-options-desktop"
              disabled={!groups.length}
              onClick={(event) => toggleVoiceOptions(event.currentTarget)}
            >
              <SpeakerHigh aria-hidden="true" weight="bold" />
              <span>
                <strong>{selectedName || t("watch.noVoice")}</strong>
                <small>{singlePlayback && selectedGroup
                  ? selectedKindLabel
                  : catalogEpisodeTotal || t("watch.coverageUnknown")}</small>
              </span>
              <CaretDown aria-hidden="true" weight="bold" />
            </button>
          </div>

          {!voiceOptionsOpen && availableEpisodeNumbers.length > 0 && (
            <div className={styles.episodeRailTools}>
              {previousNumber !== undefined ? (
                <Link
                  className={styles.episodeStep}
                  href={titleWatchHref(slug, previousNumber, selectedGroupKey)}
                  aria-label={t("watch.prev")}
                  title={t("watch.prev")}
                >
                  <CaretLeft aria-hidden="true" weight="bold" />
                </Link>
              ) : (
                <span className={styles.episodeStep} aria-disabled="true">
                  <CaretLeft aria-hidden="true" weight="bold" />
                </span>
              )}

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

              {nextNumber !== undefined ? (
                <Link
                  className={styles.episodeStep}
                  href={titleWatchHref(slug, nextNumber, selectedGroupKey)}
                  aria-label={t("watch.next")}
                  title={t("watch.next")}
                >
                  <CaretRight aria-hidden="true" weight="bold" />
                </Link>
              ) : (
                <span className={styles.episodeStep} aria-disabled="true">
                  <CaretRight aria-hidden="true" weight="bold" />
                </span>
              )}
            </div>
          )}

          <div ref={episodeRailContentRef} className={styles.episodeRailContent}>
            {voiceOptionsOpen ? voiceOptions("watch-voice-options-desktop") : (
              <>
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
              </>
            )}
          </div>
            </>
          )}
        </aside>

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

      {/* One-click voice switching: the chips sit directly under the player,
          while the panel in the rail keeps the detailed coverage breakdown. */}
      {groups.length > 0 && (
        <div className={styles.voiceChips} role="group" aria-label={t("watch.voiceOptionsTitle")}>
          {groups.map((group) => {
            const selected = group.key === selectedGroupKey;
            const name = cleanSourceName(group.name, group.provider_name);
            return (
              <button
                key={group.key}
                type="button"
                className={selected ? styles.voiceChipSelected : styles.voiceChip}
                aria-pressed={selected}
                title={name}
                onClick={() => chooseGroup(group.key)}
              >
                {name}
              </button>
            );
          })}
        </div>
      )}

      <div className={styles.watchUtilityBar} aria-label={t(singlePlayback ? "watch.titleActions" : "watch.episodeActions")}>
        {chosen?.playback_mode === "iframe_embed" && playbackProgress && (
          <PlaybackProgressStatus progress={playbackProgress} />
        )}
        {chosen && <SourceReportControl sourceId={chosen.id} key={chosen.id} />}
      </div>

      {episode.synopsis && <p className={styles.watchSynopsis}>{episode.synopsis}</p>}
    </div>
  );
}
