import Link from "next/link";
import type { PublicReview } from "../lib/api";
import { getI18n } from "../i18n/server";
import styles from "../app/community/community.module.css";

/**
 * Server-rendered list of approved reviews.
 *
 * The community page used to fetch this in `useEffect`, so a crawler received
 * only a loading placeholder. That mattered beyond the page itself: `/community`
 * is the only crawlable path to `/users/<id>` and `/collections/<owner>/<slug>`,
 * both of which are declared indexable, so those pages had no incoming links at
 * all. The interactive "following" tab stays client-side — it needs a session —
 * and is layered on top of this markup.
 */
export async function ReviewFeed({ reviews }: { reviews: PublicReview[] }) {
  const { t } = await getI18n();
  if (!reviews.length) {
    return <div className="empty-state" role="status"><strong>{t("community.noReviews")}</strong></div>;
  }
  return (
    <div className={styles.feed}>
      {reviews.map((review) => (
        <article className={styles.review} key={review.id}>
          <div className={styles.reviewHeader}>
            <Link href={`/titles/${review.title.slug}`}><strong>{review.title.name}</strong></Link>
            {review.author_public_id ? (
              <Link className={styles.author} href={`/users/${review.author_public_id}`}>
                {review.author_name.trim() || t("account.viewer")}
              </Link>
            ) : (
              <span className={styles.author}>{review.author_name.trim() || t("account.viewer")}</span>
            )}
          </div>
          {review.contains_spoilers ? (
            <details>
              <summary>{t("community.showSpoiler")}</summary>
              <p>{review.body}</p>
            </details>
          ) : (
            <p>{review.body}</p>
          )}
        </article>
      ))}
    </div>
  );
}
