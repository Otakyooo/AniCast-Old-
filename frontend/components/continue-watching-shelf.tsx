"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getContinueWatching, type ContinueWatchingEntry } from "../lib/continue-watching";
import { useI18n } from "./i18n-provider";
import styles from "../app/home.module.css";

type State =
  | { kind: "loading" }
  | { kind: "guest" }
  | { kind: "error" }
  | { kind: "ready"; entries: ContinueWatchingEntry[] };

/**
 * Resume shelf. Rendered only for signed-in viewers with recorded progress:
 * guests, failures and empty results collapse the whole section so the home
 * page never shows a placeholder shelf.
 */
export function ContinueWatchingShelf() {
  const { t } = useI18n();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    getContinueWatching(controller.signal)
      .then((entries) => setState(entries === null ? { kind: "guest" } : { kind: "ready", entries }))
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setState({ kind: "error" });
      });
    return () => controller.abort();
  }, []);

  if (state.kind !== "ready" || state.entries.length === 0) return null;

  return (
    <section className="section">
      <div className="section-heading">
        <h2>{t("home.continueWatching")}</h2>
        <Link href="/history">{t("history.all")}</Link>
      </div>
      <ul className={styles.resumeRow}>
        {state.entries.map((entry) => {
          const target = entry.next_episode ?? entry.last_episode;
          return (
            <li key={entry.title.slug}>
              <Link className={styles.resumeCard} href={`/titles/${entry.title.slug}/episodes/${target.number}`}>
                <span className={styles.resumePoster}>
                  {entry.title.poster_url ? (
                    <Image
                      className={styles.resumeImage}
                      src={entry.title.poster_url}
                      alt=""
                      fill
                      sizes="(max-width: 767px) 40vw, 200px"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <span className={styles.resumeFallback} aria-hidden="true">
                      {entry.title.name.slice(0, 1).toUpperCase()}
                    </span>
                  )}
                </span>
                <span className={styles.resumeBody}>
                  <strong>{entry.title.name}</strong>
                  <small>{t("home.watchNow", { number: target.number })}</small>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
