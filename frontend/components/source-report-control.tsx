"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { createSourceReport, SourceReportApiError, type SourceReportReason } from "../lib/reports";
import styles from "../app/reports.module.css";

export function SourceReportControl({ sourceId }: { sourceId: number }) {
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
      else setError(reason instanceof Error ? reason.message : "Не удалось отправить жалобу.");
    } finally { setPending(false); }
  }

  if (submitted) return <span className={styles.success}>Жалоба отправлена</span>;
  if (guest) return <span className={styles.guest}><Link href="/login">Войдите</Link>, чтобы сообщить о проблеме.</span>;
  if (!open) return <button className={styles.open} type="button" onClick={() => setOpen(true)}>Сообщить о проблеме</button>;
  return <form className={styles.form} onSubmit={submit}>
    <label><span>Что случилось</span><select name="reason" defaultValue="unavailable"><option value="unavailable">Источник не открывается</option><option value="wrong_content">Неверный эпизод или контент</option><option value="geo_blocked">Недоступно в регионе</option><option value="quality">Проблема качества</option><option value="other">Другое</option></select></label>
    <label><span>Комментарий</span><textarea name="message" maxLength={500} rows={3} placeholder="Дополнительные детали" /></label>
    <div className={styles.actions}><button type="submit" disabled={pending}>{pending ? "Отправляем..." : "Отправить"}</button><button type="button" disabled={pending} onClick={() => setOpen(false)}>Отмена</button></div>
    {error && <span className={styles.error} role="alert">{error}</span>}
  </form>;
}
