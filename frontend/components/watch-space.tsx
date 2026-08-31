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
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { PlaybackLink } from "./playback-link";
import { ProviderPlayer } from "./provider-player";
import type { Source, WatchSourceGroup } from "../lib/api";
import { summarizeEpisodeCoverage } from "../lib/episode-coverage";
import { titleWatchHref } from "../lib/seo";
import {
  filterEpisodeNumbers,
  firstRankedPlayableGroupKey,
  normalizeEpisodeNumbers,
  resolveRequestedGroupKey,
  voiceSection,
} from "../lib/watch-controls";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

interface WatchEpisode {
  synopsis?: string | null;
  sources: Source[];
}

type Translator = (key: string, values?: Record<string, string | number>) => string;
type ViewSourceGroup = WatchSourceGroup & { coverage_known: boolean };

function cleanSourceName(name: string, providerName = "") {
  const prefix = providerName ? `${providerName} · ` : "";
  return prefix && name.startsWith(prefix) ? name.slice(prefix.length) : name;
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

function coverageCopy(group: ViewSourceGroup, totalEpisodes: number, t: Translator) {
  if (!group.coverage_known) {
    return { summary: t("watch.coverageUnknown"), detail: "" };
  }
  const summary = summarizeEpisodeCoverage(group.episode_numbers);
  return {
    summary: t("watch.coverageCount", { count: summary.count, total: totalEpisodes }),
    detail: compactCoverage(group.episode_numbers, t, group.coverage_known),
  };
}

export function WatchSpace({
  slug,
  episodeNumbers,
  sourceGroups,
  requestedSourceKey,
  currentNumber,
  episode,
}: {
  slug: string;
  episodeNumbers: number[];
  sourceGroups: WatchSourceGroup[];
  requestedSourceKey?: string;
  currentNumber: number;
  episode: WatchEpisode;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const playableSources = useMemo(
    () => episode.sources.filter((source) => source.playback_available),
    [episode.sources],
  );
  const groups = useMemo<ViewSourceGroup[]>(() => {
    if (sourceGroups.length) {
      return sourceGroups.map((group) => ({ ...group, coverage_known: true }));
    }
    const fallback = new Map<string, ViewSourceGroup>();
    for (const source of playableSources) {
      if (!source.selection_key || fallback.has(source.selection_key)) continue;
      fallback.set(source.selection_key, {
        key: source.selection_key,
        name: source.name,
        kind: source.kind,
        provider_name: source.provider_name ?? "",
        provider_variant_id: source.provider_variant_id,
        episodes_count: 1,
        episode_numbers: [currentNumber],
        popularity_percent: 0,
        coverage_known: false,
      });
    }
    return [...fallback.values()];
  }, [currentNumber, playableSources, sourceGroups]);
  const requestedGroup = resolveRequestedGroupKey(groups, requestedSourceKey);
  const preferredKey = requestedGroup?.key
    ?? firstRankedPlayableGroupKey(
      groups,
      playableSources.map((source) => source.selection_key),
      currentNumber,
    );
  const [selectedGroupKey, setSelectedGroupKey] = useState(preferredKey);
  const [episodeQuery, setEpisodeQuery] = useState("");
  const [voiceOptionsOpen, setVoiceOptionsOpen] = useState(false);
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

  useEffect(() => {
    if (!requestedGroup?.legacy) return;
    router.replace(titleWatchHref(slug, currentNumber, requestedGroup.key), { scroll: false });
  }, [currentNumber, requestedGroup?.key, requestedGroup?.legacy, router, slug]);

  const selectedGroup = groups.find((group) => group.key === selectedGroupKey) ?? null;
  const selectedSources = playableSources.filter(
    (source) => source.selection_key === selectedGroupKey,
  );
  const chosen = selectedSources[0] ?? null;
  const allEpisodeNumbers = useMemo(
    () => normalizeEpisodeNumbers(episodeNumbers),
    [episodeNumbers],
  );
  const availableNumbers = useMemo(
    () => new Set(selectedGroup?.episode_numbers ?? allEpisodeNumbers),
    [allEpisodeNumbers, selectedGroup],
  );
  const currentIsAvailable = availableNumbers.has(currentNumber);
  const availableEpisodeNumbers = useMemo(
    () => allEpisodeNumbers.filter((number) => availableNumbers.has(number)),
    [allEpisodeNumbers, availableNumbers],
  );
  const visibleEpisodeNumbers = useMemo(
    () => filterEpisodeNumbers(availableEpisodeNumbers, episodeQuery),
    [availableEpisodeNumbers, episodeQuery],
  );
  const previousNumber = availableEpisodeNumbers.filter((number) => number < currentNumber).at(-1);
  const nextNumber = availableEpisodeNumbers.find((number) => number > currentNumber);
  const selectedName = selectedGroup
    ? cleanSourceName(selectedGroup.name, selectedGroup.provider_name)
    : "";
  const selectedCoverageSummary = selectedGroup
    ? coverageCopy(selectedGroup, allEpisodeNumbers.length, t).summary
    : "";

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
  }, [currentNumber, episodeQuery, selectedGroupKey, voiceOptionsOpen]);

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
    if (window.matchMedia("(max-width: 860px)").matches) {
      setVoiceOptionsOpen(false);
      episodeDialogRef.current?.showModal();
      requestAnimationFrame(() => episodeDialogSearchRef.current?.focus());
      return;
    }
    episodeRailSearchRef.current?.focus();
    episodeRailSearchRef.current?.select();
  }

  const playerTitle = `${selectedName || t("watch.noVoice")} · ${t("episode.number", { number: currentNumber })}`;
  const player = chosen?.playback_mode === "iframe_embed" ? (
    <ProviderPlayer
      key={chosen.id}
      sourceId={chosen.id}
      playbackMode={chosen.playback_mode}
      title={playerTitle}
      slug={slug}
      episodeNumber={currentNumber}
    />
  ) : chosen ? (
    <section className={`${styles.playerShell} ${styles.playerPreview}`} aria-label={playerTitle}>
      <div className={styles.playerPreviewBody}>
        <PlaybackLink
          sourceId={chosen.id}
          playbackMode={chosen.playback_mode}
          slug={slug}
          episodeNumber={currentNumber}
          label={t("watch.playEpisode", { number: currentNumber })}
          className={styles.playerLaunch}
        />
      </div>
    </section>
  ) : (
    <div className={styles.watchEmpty}>
      <strong>{t("watch.noPlayer")}</strong>
      <span>{t("watch.chooseAvailableEpisode")}</span>
    </div>
  );

  const episodeList = (closeDialog = false) => visibleEpisodeNumbers.map((number) => {
    const current = number === currentNumber;
    return (
      <li key={number}>
        <Link
          ref={closeDialog ? undefined : current ? currentEpisodeRef : undefined}
          href={titleWatchHref(slug, number, selectedGroupKey)}
          aria-current={current ? "page" : undefined}
          onClick={() => { if (closeDialog) episodeDialogRef.current?.close(); }}
        >
          <span>{t("episode.number", { number })}</span>
          {current && <small>{t("watch.currentEpisode")}</small>}
        </Link>
      </li>
    );
  });

  const voiceOptions = (id: string) => (
    <section id={id} className={styles.inlineVoicePanel} aria-label={t("watch.voiceOptionsTitle")}>
      <h4>{t("watch.voiceOptionsTitle")}</h4>
      <div className={styles.inlineVoiceOptions}>
        {groups.map((group) => {
          const coverage = coverageCopy(group, allEpisodeNumbers.length, t);
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
                <small>{t("watch.voiceOptionMeta", {
                  kind: t(`watch.voiceGroup.${voiceSection(group.kind)}`),
                  coverage: coverage.summary,
                })}</small>
                {coverage.detail && <small>{coverage.detail}</small>}
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
      <div className={styles.watchStage}>
        <div className={styles.watchPlayer}>{player}</div>

        <nav className={styles.watchControls} aria-label={t("watch.navigation")}>
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

          <button
            ref={episodeTriggerRef}
            className={styles.currentEpisodeButton}
            type="button"
            aria-haspopup="dialog"
            onClick={openEpisodeChooser}
          >
            <strong>{t("watch.episodeCounter", {
              number: currentNumber,
              total: allEpisodeNumbers.length,
            })}</strong>
            <span>{t("watch.chooseEpisode")}</span>
          </button>

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
                ? t("watch.voiceTriggerMeta", {
                  label: t("watch.voiceShort"),
                  coverage: selectedCoverageSummary,
                })
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

          {!currentIsAvailable && selectedGroup && (
            <p className={styles.watchWarning} role="status">
              {t("watch.voiceUnavailable", { number: currentNumber, name: selectedName })}
            </p>
          )}
        </nav>

        <aside className={styles.episodeRail} aria-label={t("watch.navigation")}>
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
                <small>{selectedCoverageSummary || t("watch.coverageUnknown")}</small>
              </span>
              <CaretDown aria-hidden="true" weight="bold" />
            </button>
          </div>

          {!voiceOptionsOpen && (
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
                <ol className={styles.episodeRailList}>{episodeList()}</ol>
                {!visibleEpisodeNumbers.length && (
                  <p className={styles.episodeSearchEmpty} role="status">{t("watch.episodeSearchEmpty")}</p>
                )}
              </>
            )}
          </div>
        </aside>

        <dialog
          ref={episodeDialogRef}
          className={styles.watchDialog}
          aria-labelledby="watch-episode-dialog-title"
          onClick={(event) => {
            if (event.currentTarget === event.target) episodeDialogRef.current?.close();
          }}
          onClose={() => episodeTriggerRef.current?.focus()}
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
            <ol className={styles.dialogEpisodeList}>{episodeList(true)}</ol>
            {!visibleEpisodeNumbers.length && (
              <p className={styles.episodeSearchEmpty} role="status">{t("watch.episodeSearchEmpty")}</p>
            )}
          </div>
        </dialog>

      </div>

      {episode.synopsis && <p className={styles.watchSynopsis}>{episode.synopsis}</p>}
    </div>
  );
}
