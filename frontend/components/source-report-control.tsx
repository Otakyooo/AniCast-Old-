"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { WarningCircle } from "@phosphor-icons/react";
import { createSourceReport, SourceReportApiError, type SourceReportReason } from "../lib/reports";
import styles from "../app/reports.module.css";
import { useI18n } from "./i18n-provider";

export function SourceReportControl({ sourceId }: { sourceId: number }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [guest, setGuest] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      await createSourceReport({
        source: sourceId,
        reason: String(data.get("reason")) as SourceReportReason,
        message: String(data.get("message") ?? ""),
      });
      setSubmitted(true);
    } catch (reason) {
      if (reason instanceof SourceReportApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(reason instanceof Error ? reason.message : t("common.error"));
    } finally { setPending(false); }
  }

  if (submitted) return <span className={styles.success} role="status">{t("report.sent")}</span>;
  if (guest) return <span className={styles.guest} role="status"><Link href="/login">{t("common.login")}</Link>: {t("report.guest")}</span>;
  // A real icon + explicit label next to the player controls: a broken source
  // is a critical feedback path, not a footnote.
  if (!open) return (
    <button className={styles.open} type="button" onClick={() => setOpen(true)}>
      <WarningCircle aria-hidden="true" weight="bold" size={16} />
      {t("report.videoProblem")}
    </button>
  );
  return <form className={styles.form} onSubmit={submit}>
    <label><span>{t("report.what")}</span><select name="reason" defaultValue="unavailable"><option value="unavailable">{t("report.unavailable")}</option><option value="wrong_content">{t("report.wrong")}</option><option value="geo_blocked">{t("report.geo")}</option><option value="quality">{t("report.quality")}</option><option value="other">{t("report.other")}</option></select></label>
    <label><span>{t("report.comment")}</span><textarea name="message" maxLength={500} rows={3} placeholder={t("report.details")} /></label>
    <div className={styles.actions}><button type="submit" disabled={pending}>{pending ? t("report.sending") : t("report.send")}</button><button type="button" disabled={pending} onClick={() => setOpen(false)}>{t("common.cancel")}</button></div>
    {error && <span className={styles.error} role="alert">{error}</span>}
  </form>;
}
