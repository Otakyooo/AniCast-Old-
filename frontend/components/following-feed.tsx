"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getFollowingFeed, type FollowingFeedItem } from "../lib/community";
import { useI18n } from "./i18n-provider";
import styles from "../app/community/community.module.css";

/**
 * Signed-in overlay for the community page: tabs plus the following feed.
 *
 * The public review list is server-rendered (`ReviewFeed`) so crawlers and
 * first paint get real content. This component only adds what needs a session:
 * it stays invisible for guests, and switching to "following" replaces the
 * server-rendered children client-side.
 */
export function FollowingFeed({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  const [following, setFollowing] = useState<FollowingFeedItem[] | null>();
  const [mode, setMode] = useState<"all" | "following">("all");

  useEffect(() => {
    const controller = new AbortController();
    getFollowingFeed(controller.signal)
      .then((response) => setFollowing(response?.results ?? null))
      .catch(() => setFollowing(null));
    return () => controller.abort();
  }, []);

  // Guests and viewers who follow nobody see the public list unchanged, with no
  // tab strip and no layout shift once the session check resolves.
  if (following === undefined || following === null) return <>{children}</>;

  return (
    <>
      <div className={styles.feedTabs} role="group" aria-label={t("social.feedTabs")}>
        <button
          className={mode === "all" ? styles.feedTabActive : ""}
          type="button"
          aria-pressed={mode === "all"}
          onClick={() => setMode("all")}
        >
          {t("social.feedAll")}
        </button>
        <button
          className={mode === "following" ? styles.feedTabActive : ""}
          type="button"
          aria-pressed={mode === "following"}
          onClick={() => setMode("following")}
        >
          {t("social.feedFollowing")}
        </button>
      </div>
      {mode === "all" ? children : following.length ? (
        <div className={styles.feed}>
          {following.map((item) => (
            <FollowingFeedCard
              item={item}
              key={`${item.kind}-${item.author.public_id}-${item.occurred_at}-${item.kind === "review" ? item.review.id : item.collection.slug}`}
            />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>{t("social.feedEmpty")}</strong>
          <p>{t("social.feedEmptyHint")}</p>
        </div>
      )}
    </>
  );
}

function FollowingFeedCard({ item }: { item: FollowingFeedItem }) {
  const { t } = useI18n();
  if (item.kind === "collection") return <article className={`${styles.review} ${styles.collectionEvent}`}>
    <div className={styles.eventLabel}>{t("social.collectionUpdated")}</div>
    <Link className={styles.eventTitle} href={`/collections/${item.author.public_id}/${item.collection.slug}`}>
      <strong>{item.collection.name}</strong><span aria-hidden="true">→</span>
    </Link>
    {item.collection.description && <p>{item.collection.description}</p>}
    <div className={styles.eventMeta}>
      <Link href={`/users/${item.author.public_id}`}>{item.author.display_name}</Link>
      <span>{t("collections.itemCount", { count: item.collection.item_count })}</span>
    </div>
  </article>;

  const review = item.review;
  return <article className={styles.review}>
    <div className={styles.eventLabel}>{t("social.reviewPublished")}</div>
    <div className={styles.reviewHeader}>
      <Link href={`/titles/${review.title.slug}`}><strong>{review.title.name}</strong></Link>
      <Link className={styles.author} href={`/users/${item.author.public_id}`}>{item.author.display_name}</Link>
    </div>
    {review.contains_spoilers ? <details><summary>{t("community.showSpoiler")}</summary><p>{review.body}</p></details> : <p>{review.body}</p>}
  </article>;
}
