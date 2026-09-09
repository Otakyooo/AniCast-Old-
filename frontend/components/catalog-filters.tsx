"use client";

import Link from "next/link";
import type { ChangeEvent } from "react";
import type { CatalogOrdering, GenreOption } from "../lib/api";
import { useI18n } from "./i18n-provider";
import styles from "../app/catalog/catalog.module.css";

export interface CatalogFilterValues {
  q: string;
  type: string;
  status: string;
  genre: string;
  ordering?: CatalogOrdering;
}

const TYPE_LABEL_KEYS: Record<string, string> = {
  anime: "catalog.series",
  movie: "catalog.movie",
  ova: "catalog.special",
  special: "catalog.special",
};

const STATUS_LABEL_KEYS: Record<string, string> = {
  ongoing: "status.ongoing",
  finished: "status.finished",
  planned: "status.planned",
};

const ORDERING_LABEL_KEYS: Record<CatalogOrdering, string> = {
  popular: "catalog.sortPopular",
  recent: "catalog.sortRecent",
  name: "catalog.sortName",
};

/**
 * The catalog filter bar. Server-rendered GET form keeps working without
 * JavaScript; selects auto-submit on change for the common no-typing path.
 * Active filters render as removable chips that preserve every other param.
 */
export function CatalogFiltersForm({ values, genres }: { values: CatalogFilterValues; genres: GenreOption[] }) {
  const { t } = useI18n();

  const autoSubmit = (event: ChangeEvent<HTMLSelectElement>) => {
    // Native submission of the GET form navigates to /catalog without the
    // page param, so every filter change lands back on page one.
    event.currentTarget.form?.requestSubmit();
  };

  const hrefWithout = (key: keyof CatalogFilterValues) => {
    const next: Record<string, string | undefined> = { ...values, [key]: undefined };
    const query = new URLSearchParams();
    if (next.q) query.set("q", next.q);
    if (next.type) query.set("type", next.type);
    if (next.status) query.set("status", next.status);
    if (next.genre) query.set("genre", next.genre);
    if (next.ordering) query.set("ordering", next.ordering);
    const suffix = query.toString();
    return suffix ? `/catalog?${suffix}` : "/catalog";
  };

  const chips: Array<{ key: string; label: string; value: string; href: string }> = [];
  const hasFilters = Boolean(values.q || values.type || values.status || values.genre || values.ordering);
  if (values.q) chips.push({ key: "q", label: t("catalog.searchLabel"), value: values.q, href: hrefWithout("q") });
  if (values.type)
    chips.push({
      key: "type",
      label: t("catalog.format"),
      value: values.type === "ova" ? "OVA" : t(TYPE_LABEL_KEYS[values.type] ?? ""),
      href: hrefWithout("type"),
    });
  if (values.status)
    chips.push({
      key: "status",
      label: t("catalog.status"),
      value: t(STATUS_LABEL_KEYS[values.status] ?? ""),
      href: hrefWithout("status"),
    });
  if (values.genre) {
    const genre = genres.find((option) => option.slug === values.genre);
    chips.push({
      key: "genre",
      label: t("catalog.genre"),
      value: genre ? genre.name : values.genre,
      href: hrefWithout("genre"),
    });
  }
  if (values.ordering)
    chips.push({
      key: "ordering",
      label: t("catalog.sortLabel"),
      value: t(ORDERING_LABEL_KEYS[values.ordering]),
      href: hrefWithout("ordering"),
    });

  return (
    <form className={styles.filters} action="/catalog">
      {chips.length > 0 && <div className={styles.chipsRow}>
        {chips.map((chip) => (
          <Link className={styles.chip} href={chip.href} key={chip.key} aria-label={`${t("catalog.reset")}: ${chip.label}`}>
            <b>{chip.label}:</b>
            <span>{chip.value}</span>
            <span aria-hidden="true">×</span>
          </Link>
        ))}
      </div>}
      <label className={`${styles.field} ${styles.searchField}`}>
        <span>{t("catalog.searchLabel")}</span>
        <input name="q" defaultValue={values.q} placeholder={t("catalog.searchPlaceholder")} />
      </label>
      <label className={styles.field}>
        <span>{t("catalog.format")}</span>
        <select name="type" defaultValue={values.type} onChange={autoSubmit}>
          <option value="">{t("catalog.allFormats")}</option>
          <option value="anime">{t("catalog.series")}</option>
          <option value="movie">{t("catalog.movie")}</option>
          <option value="ova">OVA</option>
          <option value="special">{t("catalog.special")}</option>
        </select>
      </label>
      <label className={styles.field}>
        <span>{t("catalog.status")}</span>
        <select name="status" defaultValue={values.status} onChange={autoSubmit}>
          <option value="">{t("catalog.anyStatus")}</option>
          <option value="ongoing">{t("status.ongoing")}</option>
          <option value="finished">{t("status.finished")}</option>
          <option value="planned">{t("status.planned")}</option>
        </select>
      </label>
      {genres.length > 0 && (
        <label className={styles.field}>
          <span>{t("catalog.genre")}</span>
          <select name="genre" defaultValue={values.genre} onChange={autoSubmit}>
            <option value="">{t("catalog.allGenres")}</option>
            {genres.map((genre) => (
              <option key={genre.slug} value={genre.slug}>
                {genre.name} ({genre.titles_count})
              </option>
            ))}
          </select>
        </label>
      )}
      <label className={styles.field}>
        <span>{t("catalog.sortLabel")}</span>
        <select name="ordering" defaultValue={values.ordering ?? ""} onChange={autoSubmit}>
          <option value="">{t("catalog.sortDefault")}</option>
          <option value="popular">{t("catalog.sortPopular")}</option>
          <option value="recent">{t("catalog.sortRecent")}</option>
          <option value="name">{t("catalog.sortName")}</option>
        </select>
      </label>
      <button className={styles.submit} type="submit">{t("catalog.apply")}</button>
      {hasFilters && <Link className={styles.reset} href="/catalog">{t("catalog.reset")}</Link>}
    </form>
  );
}
