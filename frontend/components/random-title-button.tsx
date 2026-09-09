"use client";

import { useRouter } from "next/navigation";
import { DiceFive } from "@phosphor-icons/react";
import { useEffect, useRef, useState, useTransition } from "react";
import { getCatalog, type CatalogFilters } from "../lib/api";
import { useI18n } from "./i18n-provider";
import styles from "../app/catalog/catalog.module.css";

/** Select one title uniformly from the applied filters; fetch only that row. */
export function RandomTitleButton({ count, filters }: { count: number; filters: CatalogFilters }) {
  const { t } = useI18n();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function roll() {
    if (request.current || pending || count < 1) return;
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError(false);
    try {
      const result = await getCatalog({ ...filters, pageSize: 1, page: 1 + Math.floor(Math.random() * count) }, controller.signal);
      if (controller.signal.aborted) return;
      const title = result.results[0];
      if (!title) throw new Error("No matching title");
      startTransition(() => router.push(`/titles/${encodeURIComponent(title.slug)}`));
    } catch {
      if (!controller.signal.aborted) setError(true);
    } finally {
      if (!controller.signal.aborted) {
        request.current = null;
        setLoading(false);
      }
    }
  }

  return <div className={styles.randomAction}>
    <button className={styles.randomButton} type="button" onClick={roll}
      disabled={count < 1 || loading || pending} aria-busy={loading || pending}>
      <DiceFive aria-hidden="true" size={20} weight="bold" />
      <span>{t(loading || pending ? "common.loading" : "catalog.random")}</span>
    </button>
    {error && <span role="alert">{t("catalog.randomFailed")}</span>}
  </div>;
}
