import Image from "next/image";
import Link from "next/link";
import type { PublicProfileData } from "../lib/public-profile";
import { getI18n } from "../i18n/server";
import { FollowButton } from "./follow-button";
import styles from "../app/users/[publicId]/profile.module.css";

export async function PublicProfile({ data }: { data: PublicProfileData }) {
  const { t } = await getI18n();
  const initial = data.profile.display_name.slice(0, 1).toUpperCase();

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.banner} aria-hidden="true" />
        <div className={styles.identity}>
          <div className={styles.avatar} aria-hidden="true">{initial}</div>
          <div>
            <p className="eyebrow">{t("social.publicBadge")}</p>
            <h1>{data.profile.display_name}</h1>
            {data.profile.bio && <p className={styles.bio}>{data.profile.bio}</p>}
            <FollowButton publicId={data.profile.public_id} initialFollowers={data.stats.followers} />
          </div>
          <dl className={styles.stats}>
            <div><dt>{t("social.collections")}</dt><dd>{data.stats.collections}</dd></div>
            <div><dt>{t("social.reviews")}</dt><dd>{data.stats.reviews}</dd></div>
          </dl>
        </div>
      </section>

      <section aria-labelledby="profile-collections">
        <div className={styles.sectionHeading}>
          <div><p className="eyebrow">{t("nav.collections")}</p><h2 id="profile-collections">{t("social.publicCollections")}</h2></div>
        </div>
        {data.collections.length ? (
          <div className={styles.collectionGrid}>
            {data.collections.map((collection) => (
              <Link className={styles.collectionCard} href={`/collections/${data.profile.public_id}/${collection.slug}`} key={collection.slug}>
                <div className={styles.mosaic} aria-hidden="true">
                  {collection.preview_titles.length ? collection.preview_titles.map((title) => (
                    title.poster_url ? <Image key={title.slug} src={title.poster_url} alt="" fill={false} width={90} height={126} quality={92} referrerPolicy="no-referrer" /> : <span key={title.slug}>{title.name.slice(0, 1)}</span>
                  )) : <span className={styles.emptyMosaic}>＋</span>}
                </div>
                <div className={styles.collectionBody}>
                  <h3>{collection.name}</h3>
                  {collection.description && <p>{collection.description}</p>}
                  <small>{t("collections.itemCount", { count: collection.item_count })} <span aria-hidden="true">→</span></small>
                </div>
              </Link>
            ))}
          </div>
        ) : <div className={styles.empty}>{t("social.noPublicCollections")}</div>}
      </section>

      <section aria-labelledby="profile-reviews">
        <div className={styles.sectionHeading}>
          <div><p className="eyebrow">{t("nav.community")}</p><h2 id="profile-reviews">{t("social.publishedReviews")}</h2></div>
        </div>
        {data.reviews.length ? (
          <div className={styles.reviewList}>
            {data.reviews.map((review) => (
              <article className={styles.review} key={review.id}>
                <Link href={`/titles/${review.title.slug}`}><strong>{review.title.name}</strong><span aria-hidden="true">→</span></Link>
                {review.contains_spoilers ? <details><summary>{t("community.showSpoiler")}</summary><p>{review.body}</p></details> : <p>{review.body}</p>}
              </article>
            ))}
          </div>
        ) : <div className={styles.empty}>{t("social.noPublishedReviews")}</div>}
      </section>
    </div>
  );
}
