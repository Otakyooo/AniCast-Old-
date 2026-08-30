"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { deleteTitleNote, getTitleNote, NoteApiError, putTitleNote } from "../lib/notes";
import styles from "../app/notes/notes.module.css";
import { useI18n } from "./i18n-provider";

export function TitleNoteControl({ slug }: { slug: string }) {
  const { t } = useI18n();
  const [body, setBody] = useState("");
  const [exists, setExists] = useState(false);
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState<"save" | "delete" | null>(null);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const noteId = useId();
  useEffect(() => {
    const controller = new AbortController();
    getTitleNote(slug, controller.signal).then(note => { if (note) { setBody(note.body); setExists(true); } }).catch(reason => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof NoteApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(t("common.error"));
    });
    return () => controller.abort();
  }, [slug, t]);
  async function save() {
    setPending("save"); setError(""); setFeedback("");
    try { await putTitleNote(slug, body); setExists(true); setFeedback(t("notes.saved")); }
    catch { setError(t("common.error")); }
    finally { setPending(null); }
  }
  async function remove() {
    setPending("delete"); setError(""); setFeedback("");
    try { await deleteTitleNote(slug); setBody(""); setExists(false); setFeedback(t("notes.deleted")); }
    catch { setError(t("common.error")); }
    finally { setPending(null); }
  }
  if (guest) return <section className={styles.control}><p><Link href="/login">{t("common.login")}</Link>: {t("notes.guest")}</p></section>;
  return <section className={styles.control} aria-busy={pending !== null}><div className={styles.heading}><h2><label htmlFor={noteId}>{t("notes.personal")}</label></h2><span>{body.length}/2000</span></div><textarea id={noteId} value={body} onChange={event => { setBody(event.target.value); setFeedback(""); }} maxLength={2000} rows={5} placeholder={t("notes.placeholder")} /><div className={styles.actions}><button type="button" disabled={pending !== null || !body.trim()} onClick={save}>{pending === "save" ? t("notes.saving") : t("common.save")}</button>{exists && <button type="button" disabled={pending !== null} onClick={remove}>{pending === "delete" ? t("notes.deleting") : t("common.delete")}</button>}</div>{feedback && <span className={styles.feedback} role="status">{feedback}</span>}{error && <span className={styles.error} role="alert">{error}</span>}</section>;
}
