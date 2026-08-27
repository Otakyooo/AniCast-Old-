"use client";

import { useEffect, useState } from "react";
import { getCsrfToken } from "../lib/auth";
import { useI18n } from "./i18n-provider";

type VisitSummary = {
  total: number;
  today: number;
  counted: boolean;
};

export function VisitCounter() {
  const { locale, t } = useI18n();
  const [summary, setSummary] = useState<VisitSummary | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getCsrfToken()
      .then((csrf) => fetch("/api/v1/analytics/visit/", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json", "X-CSRFToken": csrf },
        signal: controller.signal,
      }))
      .then((response) => {
        if (!response.ok) throw new Error(`Visit counter returned ${response.status}`);
        return response.json() as Promise<VisitSummary>;
      })
      .then(setSummary)
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setSummary(null);
      });
    return () => controller.abort();
  }, []);

  if (!summary) return <span className="visit-counter-placeholder" aria-hidden="true" />;

  const format = new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US");
  return (
    <div className="visit-counter" aria-label={t("visits.label")}>
      <span><strong>{format.format(summary.total)}</strong> {t("visits.total")}</span>
      <span className="visit-counter-divider" aria-hidden="true" />
      <span><strong>{format.format(summary.today)}</strong> {t("visits.today")}</span>
    </div>
  );
}
