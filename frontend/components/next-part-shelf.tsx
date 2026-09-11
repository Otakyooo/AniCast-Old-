"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import type { CatalogItem } from "../lib/api";
import {
  getContinueWatching,
  type ContinueWatchingEntry,
} from "../lib/continue-watching";
import { formatPlaybackTime } from "../lib/playback";
import { RailScroller } from "./rail-scroller";
import { useI18n } from "./i18n-provider";
import styles from "../app/home.module.css";

interface NextPart {
  current: ContinueWatchingEntry;
  next: NonNullable<NonNullable<ContinueWatchingEntry["franchise_next"]>>;
}

/**
 * The "next part of your story" shelf: separate from recommendations for new
 * stories. An entry appears when the viewer's started title belongs to a
 * franchise and the next part exists. With it comes the current context
 * («После …») and a link to the watch order, so a late season stop reading
 * as a random guess.
 */
export function NextPartShelf() {
  const { t } = useI18n();
  const [items, setItems] = useState<NextPart[] | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getContinueWatching(controller.signal)
      .then((entries) => {
        if (!entries || controller.signal.aborted) return;
        const seen = new Set<string>();
        const parts = entries.flatMap((entry): NextPart[] => {
          const next = entry.franchise_next;
          if (!next) return [];
          if (seen.has(next.slug)) return [];
          seen.add(next.slug);
          return [{ current: entry, next }];
        });
        setItems(parts);
      })
      .catch(() => setItems(null));
    return () => controller.abort();
  }, []);

  if (!items || items.length === 0) return null;

  return (
    <section className="section" aria-label={t("home.nextPartTitle")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.nextPartTitle")}</h2>
          <p>{t("home.nextPartText")}</p>
        </div>
        <Link href="/history">{t("home.allStarted")}</Link>
      </div>
      <RailScroller railClassName={styles.nextPartRail}>
        <ul className={styles.railList}>
          {items.map(({ current, next }) => (
            <li className={styles.nextPartItem} key={next.slug}>
              <Link className={styles.nextPartLink} href={`/titles/${next.slug}#watch-order`}>
                <span className={styles.nextPartPoster}>
                  {next.poster_url ? (
                    <Image
                      className={styles.nextPartPosterArt}
                      src={next.poster_url}
                      alt=""
                      fill
                      sizes="(max-width: 768px) 42vw, 176px"
                      quality={92}
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <span aria-hidden="true">{next.name.slice(0, 1).toUpperCase()}</span>
                  )}
                </span>
                <span className={styles.nextPartBody}>
                  <strong title={next.name}>{next.name}</strong>
                  <small>
                    {t("home.nextPartAfter", { name: current.title.name })}
                    {typeof current.resume_at_seconds === "number" && current.resume_at_seconds > 0 && (
                      <>{t("home.nextPartWatching", { time: formatPlaybackTime(current.resume_at_seconds) })}</>
                    )}
                  </small>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </RailScroller>
    </section>
  );
}
