"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getFollowingFeed, getPublicReviews, type FollowingFeedItem, type Review } from "../lib/community";
import { useI18n } from "./i18n-provider";
import styles from "../app/community/community.module.css";

export function CommunityFeed() {
  const { t } = useI18n();
  const [reviews, setReviews] = useState<Review[]>();
  const [following, setFollowing] = useState<FollowingFeedItem[] | null>();
  const [mode, setMode] = useState<"all" | "following">("all");

  useEffect(() => {
    const controller = new AbortController();
    getPublicReviews(controller.signal).then((response) => setReviews(response.results)).catch(() => setReviews([]));
    getFollowingFeed(controller.signal).then((response) => setFollowing(response?.results ?? null)).catch(() => setFollowing([]));
    return () => controller.abort();
  }, []);

  if (!reviews || following === undefined) return <div className="empty-state">{t("common.loading")}</div>;

  const tabs = following !== null && <div className={styles.feedTabs} role="group" aria-label={t("social.feedTabs")}>
    <button className={mode === "all" ? styles.feedTabActive : ""} type="button" aria-pressed={mode === "all"} onClick={() => setMode("all")}>{t("social.feedAll")}</button>
    <button className={mode === "following" ? styles.feedTabActive : ""} type="button" aria-pressed={mode === "following"} onClick={() => setMode("following")}>{t("social.feedFollowing")}</button>
  </div>;

  if (mode === "following" && following !== null) return <>{tabs}{following.length ? (
    <div className={styles.feed}>{following.map((item) => <FollowingFeedCard item={item} key={`${item.kind}-${item.author.public_id}-${item.occurred_at}-${item.kind === "review" ? item.review.id : item.collection.slug}`} />)}</div>
  ) : <div className="empty-state"><strong>{t("social.feedEmpty")}</strong><p>{t("social.feedEmptyHint")}</p></div>}</>;

  if (!reviews.length) return <>{tabs}<div className="empty-state"><strong>{t("community.noReviews")}</strong></div></>;

  return <>{tabs}<div className={styles.feed}>{reviews.map((review) => (
    <article className={styles.review} key={review.id}>
      <div className={styles.reviewHeader}>
        <Link href={`/titles/${review.title.slug}`}><strong>{review.title.name}</strong></Link>
        {review.author_public_id ? (
          <Link className={styles.author} href={`/users/${review.author_public_id}`}>{authorLabel(review, t)}</Link>
        ) : <span className={styles.author}>{authorLabel(review, t)}</span>}
      </div>
      {review.contains_spoilers ? <details><summary>{t("community.showSpoiler")}</summary><p>{review.body}</p></details> : <p>{review.body}</p>}
    </article>
  ))}</div></>;
}

/**
 * A reviewer who never set a display name is shown as a generic viewer.
 *
 * The API returns the name verbatim, including empty, because the placeholder is
 * a locale decision. It used to substitute the account's internal primary key,
 * which put registration order and a rough user count into a public payload.
 */
function authorLabel(review: Review, t: (key: string) => string) {
  return review.author_name.trim() || t("account.viewer");
}

function FollowingFeedCard({ item }: { item:FollowingFeedItem }) {
  const { t } = useI18n();
  if (item.kind === "collection") return <article className={`${styles.review} ${styles.collectionEvent}`}>
    <div className={styles.eventLabel}>{t("social.collectionUpdated")}</div>
    <Link className={styles.eventTitle} href={`/collections/${item.author.public_id}/${item.collection.slug}`}>
      <strong>{item.collection.name}</strong><span aria-hidden="true">→</span>
    </Link>
    {item.collection.description && <p>{item.collection.description}</p>}
    <div className={styles.eventMeta}>
      <Link href={`/users/${item.author.public_id}`}>{item.author.display_name}</Link>
      <span>{t("collections.itemCount", { count:item.collection.item_count })}</span>
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
