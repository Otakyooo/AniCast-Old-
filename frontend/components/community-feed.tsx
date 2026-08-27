"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPublicReviews, type Review } from "../lib/community";
import { useI18n } from "./i18n-provider";
import styles from "../app/community/community.module.css";

export function CommunityFeed() {
  const { t } = useI18n();
  const [reviews, setReviews] = useState<Review[]>();

  useEffect(() => {
    const controller = new AbortController();
    getPublicReviews(controller.signal).then((response) => setReviews(response.results)).catch(() => setReviews([]));
    return () => controller.abort();
  }, []);

  if (!reviews) return <div className="empty-state">{t("common.loading")}</div>;
  if (!reviews.length) return <div className="empty-state"><strong>{t("community.noReviews")}</strong></div>;

  return <div className={styles.feed}>{reviews.map((review) => (
    <article className={styles.review} key={review.id}>
      <div className={styles.reviewHeader}>
        <Link href={`/titles/${review.title.slug}`}><strong>{review.title.name}</strong></Link>
        {review.author_public_id ? (
          <Link className={styles.author} href={`/users/${review.author_public_id}`}>{review.author_name}</Link>
        ) : <span className={styles.author}>{review.author_name}</span>}
      </div>
      {review.contains_spoilers ? <details><summary>{t("community.showSpoiler")}</summary><p>{review.body}</p></details> : <p>{review.body}</p>}
    </article>
  ))}</div>;
}
