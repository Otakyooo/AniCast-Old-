"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { globalSearch, SEARCH_MIN_LENGTH, type GlobalSearchResponse } from "../lib/api";
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
 * collapses into a trigger that opens a full-width sheet.
 */
export function GlobalSearch() {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [state, setState] = useState<SearchState>({ kind: "idle" });
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelId = useId();
  const trimmed = query.trim();

  useEffect(() => {
    if (trimmed.length < SEARCH_MIN_LENGTH) {
      setState({ kind: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ kind: "loading" });
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

  const close = useCallback(() => {
    setOpen(false);
    setExpanded(false);
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

  return (
    <div className={`${styles.wrap} ${expanded ? styles.wrapExpanded : ""}`} ref={containerRef}>
      <button
        className={styles.trigger}
        type="button"
        aria-label={expanded ? t("nav.closeSearch") : t("nav.openSearch")}
        aria-expanded={expanded}
        onClick={toggleExpanded}
      >
        <span aria-hidden="true">⌕</span>
      </button>

      <div className={styles.field}>
        <form className={`global-search ${styles.form}`} action="/catalog" role="search" onSubmit={close}>
          <span aria-hidden="true">⌕</span>
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
            placeholder={t("search.placeholder")}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
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
                  <section className={styles.group}>
                    <h3>{t("search.titles")}</h3>
                    {state.data.titles.map((item) => (
                      <Link className={styles.row} href={`/titles/${item.slug}`} key={item.slug} onClick={close}>
                        <span className={styles.thumb}>
                          {item.poster_url ? (
                            <Image
                              className={styles.thumbImage}
                              src={item.poster_url}
                              alt=""
                              fill
                              sizes="40px"
                              referrerPolicy="no-referrer"
                            />
                          ) : (
                            <span aria-hidden="true">{item.name.slice(0, 1).toUpperCase()}</span>
                          )}
                        </span>
                        <span className={styles.rowBody}>
                          <strong>{item.name}</strong>
                          <small>
                            {item.year ?? t("year.unknown")}
                            {item.title_type ? ` · ${t(`type.${item.title_type}`)}` : ""}
                          </small>
                        </span>
                      </Link>
                    ))}
                  </section>
                )}
                {state.data.characters.length > 0 && (
                  <section className={styles.group}>
                    <h3>{t("search.characters")}</h3>
                    {state.data.characters.map((character) => (
                      <Link
                        className={styles.row}
                        href={`/characters/${character.slug}`}
                        key={character.slug}
                        onClick={close}
                      >
                        <span className={`${styles.thumb} ${styles.thumbRound}`}>
                          {character.image_url ? (
                            <Image
                              className={styles.thumbImage}
                              src={character.image_url}
                              alt=""
                              fill
                              sizes="40px"
                              referrerPolicy="no-referrer"
                            />
                          ) : (
                            <span aria-hidden="true">{character.name.slice(0, 1).toUpperCase()}</span>
                          )}
                        </span>
                        <span className={styles.rowBody}>
                          <strong>{character.name}</strong>
                          <small>{t("franchise.count", { count: character.title_count })}</small>
                        </span>
                      </Link>
                    ))}
                  </section>
                )}
                {state.data.franchises.length > 0 && (
                  <section className={styles.group}>
                    <h3>{t("search.franchises")}</h3>
                    {state.data.franchises.map((franchise) => (
                      <Link
                        className={styles.row}
                        href={`/franchises/${franchise.slug}`}
                        key={franchise.slug}
                        onClick={close}
                      >
                        <span className={`${styles.thumb} ${styles.thumbFlat}`} aria-hidden="true">
                          {franchise.name.slice(0, 1).toUpperCase()}
                        </span>
                        <span className={styles.rowBody}>
                          <strong>{franchise.name}</strong>
                          <small>{t("franchise.count", { count: franchise.title_count })}</small>
                        </span>
                      </Link>
                    ))}
                  </section>
                )}
                <Link className={styles.allResults} href={`/catalog?q=${encodeURIComponent(trimmed)}`} onClick={close}>
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
