"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { CharacterAvatar } from "./character-avatar";
import { globalSearch, SEARCH_MIN_LENGTH, type GlobalSearchResponse } from "../lib/api";
import { buildSearchOptionModel } from "../lib/global-search";
import { OPEN_SEARCH_EVENT } from "./mobile-search-link";
import { useI18n } from "./i18n-provider";
import styles from "../app/search.module.css";

type SearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; data: GlobalSearchResponse }
  | { kind: "error" };

const DEBOUNCE_MS = 250;

function hasResults(data: GlobalSearchResponse) {
  return data.titles.length > 0 || data.characters.length > 0 || data.franchises.length > 0;
}

/**
 * Header search with a suggestion panel.
 *
 * The form submits to `/catalog`, so search still works without JavaScript and
 * existing `/catalog?q=` links keep their meaning. On narrow viewports the field
 * collapses into a trigger that opens a full-width sheet. Arrow keys walk the
 * flat option list behind the grouped markup, Enter follows the active row and
 * the plain form submit remains the fallback for "all results".
 */
export function GlobalSearch() {
  const { t } = useI18n();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [state, setState] = useState<SearchState>({ kind: "idle" });
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelId = useId();
  const titlesHeadingId = `${panelId}-titles`;
  const charactersHeadingId = `${panelId}-characters`;
  const franchisesHeadingId = `${panelId}-franchises`;
  const trimmed = query.trim();

  useEffect(() => {
    if (trimmed.length < SEARCH_MIN_LENGTH) {
      setState({ kind: "idle" });
      setActiveIndex(-1);
      return;
    }
    const controller = new AbortController();
    setState({ kind: "loading" });
    setActiveIndex(-1);
    const timer = window.setTimeout(() => {
      globalSearch(trimmed, controller.signal)
        .then((data) => setState({ kind: "ready", data }))
        .catch((reason) => {
          if (reason instanceof DOMException && reason.name === "AbortError") return;
          setState({ kind: "error" });
        });
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [trimmed]);

  // The panel shows groups, but keyboard navigation walks one flat list in the
  // same visual order, including the trailing "all results" entry.
  const optionModel = useMemo(() => {
    if (state.kind !== "ready" || !hasResults(state.data)) {
      return { options: [], starts: { titles: 0, characters: 0, franchises: 0 } };
    }
    return buildSearchOptionModel(state.data, panelId, trimmed);
  }, [state, trimmed, panelId]);
  const { options, starts } = optionModel;

  useEffect(() => {
    if (!open || activeIndex < 0) return;
    const option = options[activeIndex];
    if (option) document.getElementById(option.id)?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open, options]);

  const close = useCallback(() => {
    setOpen(false);
    setExpanded(false);
    setActiveIndex(-1);
  }, []);

  useEffect(() => {
    if (!open && !expanded) return;
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) close();
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        close();
        inputRef.current?.blur();
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, expanded, close]);

  function toggleExpanded() {
    const next = !expanded;
    setExpanded(next);
    setOpen(next);
    if (next) window.requestAnimationFrame(() => inputRef.current?.focus());
  }

  // The mobile bottom-nav "Поиск" action and the Ctrl/Cmd+K shortcut (design
  // spec §13) both expand this field from anywhere on the page.
  useEffect(() => {
    function openSearch() {
      setExpanded(true);
      setOpen(true);
      window.requestAnimationFrame(() => inputRef.current?.focus());
    }
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openSearch();
      }
    }
    window.addEventListener(OPEN_SEARCH_EVENT, openSearch);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener(OPEN_SEARCH_EVENT, openSearch);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  function onInputKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (options.length === 0) return;
      setActiveIndex((current) => {
        if (current < 0) return event.key === "ArrowDown" ? 0 : options.length - 1;
        const step = event.key === "ArrowDown" ? 1 : -1;
        return (current + step + options.length) % options.length;
      });
      return;
    }
    if ((event.key === "Home" || event.key === "End") && options.length > 0) {
      event.preventDefault();
      setActiveIndex(event.key === "Home" ? 0 : options.length - 1);
      return;
    }
    if (event.key === "Enter") {
      const option = open && activeIndex >= 0 ? options[activeIndex] : undefined;
      if (option) {
        event.preventDefault();
        close();
        router.push(option.href);
      }
      return;
    }
    if (event.key === "Tab") close();
  }

  const optionProps = (index: number) => ({
    id: options[index]?.id,
    role: "option" as const,
    "aria-selected": index === activeIndex,
    onMouseMove: () => setActiveIndex(index),
  });

  return (
    <div className={`${styles.wrap} ${expanded ? styles.wrapExpanded : ""}`} ref={containerRef}>
      <button
        className={styles.trigger}
        type="button"
        aria-label={expanded ? t("nav.closeSearch") : t("nav.openSearch")}
        aria-expanded={expanded}
        onClick={toggleExpanded}
      >
        <MagnifyingGlass aria-hidden="true" size={19} />
      </button>

      <div className={styles.field}>
        <form className={`global-search ${styles.form}`} action="/catalog" role="search" onSubmit={close}>
          <MagnifyingGlass aria-hidden="true" size={17} />
          <input
            ref={inputRef}
            name="q"
            type="search"
            autoComplete="off"
            role="combobox"
            aria-label={t("search.title")}
            aria-autocomplete="list"
            aria-expanded={open}
            aria-controls={panelId}
            aria-activedescendant={
              open && activeIndex >= 0 ? options[activeIndex]?.id : undefined
            }
            placeholder={t("search.placeholder")}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onInputKeyDown}
          />
        </form>

        {open && (
          <div className={styles.panel} id={panelId} role="listbox" aria-label={t("search.title")}>
            {trimmed.length < SEARCH_MIN_LENGTH && (
              <p className={styles.hint}>{t("search.hint", { count: SEARCH_MIN_LENGTH })}</p>
            )}
            {trimmed.length >= SEARCH_MIN_LENGTH && state.kind === "loading" && (
              <p className={styles.hint} role="status">{t("search.loading")}</p>
            )}
            {state.kind === "error" && (
              <div className={styles.message} role="alert">
                <strong>{t("search.error")}</strong>
                <span>{t("search.errorText")}</span>
              </div>
            )}
            {state.kind === "ready" && !hasResults(state.data) && (
              <div className={styles.message} role="status">
                <strong>{t("search.empty")}</strong>
                <span>{t("search.emptyText")}</span>
              </div>
            )}
            {state.kind === "ready" && hasResults(state.data) && (
              <>
                {state.data.titles.length > 0 && (
                  <section className={styles.group} role="group" aria-labelledby={titlesHeadingId}>
                    <h3 id={titlesHeadingId}>{t("search.titles")}</h3>
                    {state.data.titles.map((item, groupIndex) => {
                      const index = starts.titles + groupIndex;
                      return (
                        <Link
                          className={`${styles.row} ${index === activeIndex ? styles.rowActive : ""}`}
                          href={`/titles/${item.slug}`}
                          key={item.slug}
                          onClick={close}
                          {...optionProps(index)}
                        >
                          <span className={styles.thumb}>
                            {item.poster_url ? (
                              <Image
                                className={styles.thumbImage}
                                src={item.poster_url}
                                alt=""
                                fill
                                sizes="40px"
                                quality={92}
                                referrerPolicy="no-referrer"
                              />
                            ) : (
                              <span aria-hidden="true">{item.name.slice(0, 1).toUpperCase()}</span>
                            )}
                          </span>
                          <span className={styles.rowBody}>
                            <strong>{item.name}</strong>
                            {item.localized_names && (
                              <span className={styles.aliases}>
                                {Object.entries(item.localized_names)
                                  .filter(([, name]) => name && name !== item.name)
                                  .map(([language, name]) => `${language.toUpperCase()} ${name}`)
                                  .join(" · ")}
                              </span>
                            )}
                            <small>
                              {item.year ?? t("year.unknown")}
                              {item.title_type ? ` · ${t(`type.${item.title_type}`)}` : ""}
                            </small>
                          </span>
                        </Link>
                      );
                    })}
                  </section>
                )}
                {state.data.characters.length > 0 && (
                  <section className={styles.group} role="group" aria-labelledby={charactersHeadingId}>
                    <h3 id={charactersHeadingId}>{t("search.characters")}</h3>
                    {state.data.characters.map((character, groupIndex) => {
                      const index = starts.characters + groupIndex;
                      return (
                        <Link
                          className={`${styles.row} ${index === activeIndex ? styles.rowActive : ""}`}
                          href={`/characters/${character.slug}`}
                          key={character.slug}
                          onClick={close}
                          {...optionProps(index)}
                        >
                          <span className={`${styles.thumb} ${styles.thumbRound}`}>
                            <CharacterAvatar imageUrl={character.image_url} sizes="40px" />
                          </span>
                          <span className={styles.rowBody}>
                            <strong>{character.name}</strong>
                            <small>{t("franchise.count", { count: character.title_count })}</small>
                          </span>
                        </Link>
                      );
                    })}
                  </section>
                )}
                {state.data.franchises.length > 0 && (
                  <section className={styles.group} role="group" aria-labelledby={franchisesHeadingId}>
                    <h3 id={franchisesHeadingId}>{t("search.franchises")}</h3>
                    {state.data.franchises.map((franchise, groupIndex) => {
                      const index = starts.franchises + groupIndex;
                      return (
                        <Link
                          className={`${styles.row} ${index === activeIndex ? styles.rowActive : ""}`}
                          href={`/franchises/${franchise.slug}`}
                          key={franchise.slug}
                          onClick={close}
                          {...optionProps(index)}
                        >
                          <span className={`${styles.thumb} ${styles.thumbFlat}`} aria-hidden="true">
                            {franchise.name.slice(0, 1).toUpperCase()}
                          </span>
                          <span className={styles.rowBody}>
                            <strong>{franchise.name}</strong>
                            <small>{t("franchise.count", { count: franchise.title_count })}</small>
                          </span>
                        </Link>
                      );
                    })}
                  </section>
                )}
                <Link
                  className={`${styles.allResults} ${
                    activeIndex === options.length - 1 ? styles.rowActive : ""
                  }`}
                  href={`/catalog?q=${encodeURIComponent(trimmed)}`}
                  onClick={close}
                  {...optionProps(options.length - 1)}
                >
                  {t("search.allResults")}
                </Link>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
