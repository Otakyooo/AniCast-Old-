"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { deleteReview, getCommunitySummary, saveReview, setRating, type CommunitySummary } from "../lib/community";
import { useI18n } from "./i18n-provider";
import styles from "../app/community/community.module.css";

export function CommunityPanel({ slug }: { slug: string }) {
  const { locale } = useI18n();
  return <CommunityContent key={`${slug}:${locale}`} slug={slug} />;
}

function CommunityContent({ slug }: { slug: string }) {
  const { t } = useI18n();
  const [data, setData] = useState<CommunitySummary>();
  const [error, setError] = useState("");
  const [pendingRating, setPendingRating] = useState<number | null>(null);
  const [formPending, setFormPending] = useState(false);

  const load = useCallback(async () => {
    const next = await getCommunitySummary(slug);
    setData(next);
    setError("");
  }, [slug]);

  useEffect(() => {
    let active = true;
    getCommunitySummary(slug)
      .then((next) => { if (active) setData(next); })
      .catch(() => { if (active) setError(t("common.error")); });
    return () => { active = false; };
  }, [slug, t]);

  async function rate(value: number) {
    setPendingRating(value);
    setError("");
    try {
      await setRating(slug, value);
      await load();
    } catch {
      setError(t("community.signIn"));
    } finally {
      setPendingRating(null);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setFormPending(true);
    setError("");
    try {
      await saveReview(slug, String(form.get("body") ?? ""), form.get("spoiler") === "on");
      await load();
    } catch {
      setError(t("community.signIn"));
    } finally {
      setFormPending(false);
    }
  }

  async function removeReview() {
    setFormPending(true);
    setError("");
    try {
      await deleteReview(slug);
      await load();
    } catch {
      setError(t("common.error"));
    } finally {
      setFormPending(false);
    }
  }

  if (!data) {
    return (
      <section className={styles.panel} role={error ? "alert" : "status"}>
        {error || t("common.loading")}
      </section>
    );
  }

  return (
    <section className={styles.panel} aria-busy={pendingRating !== null || formPending}>
      <div className={styles.summary}>
        <h2>{t("community.title")}</h2>
        <strong>{data.average_rating !== null ? t("community.average", { value: data.average_rating }) : t("community.noRating")}</strong>
        <span>({data.rating_count})</span>
      </div>

      <div className={styles.rating} role="group" aria-label={t("community.rating")}>
        <span aria-hidden="true">{t("community.rating")}</span>
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => (
          <button
            className={data.my_rating?.value === value ? styles.active : undefined}
            disabled={pendingRating !== null}
            onClick={() => rate(value)}
            type="button"
            key={value}
            aria-label={`${t("community.rating")}: ${value} / 10`}
            aria-pressed={data.my_rating?.value === value}
          >
            {value}
          </button>
        ))}
      </div>

      <form className={styles.form} onSubmit={submit}>
        <label>
          {t("community.review")}
          <textarea name="body" minLength={20} maxLength={5000} defaultValue={data.my_review?.body ?? ""} placeholder={t("community.reviewPlaceholder")} required />
        </label>
        <label className={styles.spoiler}>
          <input type="checkbox" name="spoiler" defaultChecked={data.my_review?.contains_spoilers} />
          {t("community.spoiler")}
        </label>
        <button type="submit" disabled={formPending}>{t("community.submit")}</button>
        {data.my_review && <button type="button" disabled={formPending} onClick={removeReview}>{t("common.delete")}</button>}
        {data.my_review?.status && <small role="status">{t(`community.${data.my_review.status}`)}</small>}
      </form>

      {error && <p role="alert">{error} <Link href="/login">{t("common.login")}</Link></p>}

      <div>
        <h3>{t("community.publicReviews")}</h3>
        {data.reviews.length ? data.reviews.map((review) => (
          <article className={styles.review} key={review.id}>
            {/* Empty means the reviewer never set a display name; the API returns
                it verbatim because the placeholder is a locale decision. */}
            <strong>{review.author_name.trim() || t("account.viewer")}</strong>
            {review.contains_spoilers ? <details><summary>{t("community.showSpoiler")}</summary><p>{review.body}</p></details> : <p>{review.body}</p>}
          </article>
        )) : <p>{t("community.noReviews")}</p>}
      </div>
    </section>
  );
}
