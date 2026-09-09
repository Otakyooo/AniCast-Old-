"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "./i18n-provider";

/** Keep the page and its filters available when a public data request fails. */
export function SectionUnavailable() {
  const { t } = useI18n();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return <div className="empty-state" role="alert" aria-busy={pending}>
    <strong>{t("common.loadFailed")}</strong>
    <span>{t("common.loadFailedText")}</span>
    <button className="secondary" type="button" disabled={pending} onClick={() => startTransition(() => router.refresh())}>
      {t(pending ? "common.loading" : "common.retry")}
    </button>
  </div>;
}
