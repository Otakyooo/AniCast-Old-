"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getNotes, NoteApiError, type NotesResponse } from "../lib/notes";
import styles from "../app/notes/notes.module.css";
import { intlLocale } from "../i18n/config";
import { useI18n } from "./i18n-provider";

export function NotesView() {
  const { t, locale } = useI18n();
  const [notes, setNotes] = useState<NotesResponse>();
  const [guest, setGuest] = useState(false);
  const [error, setError] = useState(false);
  useEffect(() => { const controller = new AbortController(); getNotes(controller.signal).then(setNotes).catch(reason => { if (reason instanceof DOMException && reason.name === "AbortError") return; if (reason instanceof NoteApiError && [401,403].includes(reason.status)) setGuest(true); else setError(true); }); return () => controller.abort(); }, []);
  if (guest) return <div className="empty-state"><strong>{t("common.login")}</strong><Link href="/login">{t("common.login")}</Link></div>;
  if (error) return <div className="empty-state" role="alert"><strong>{t("history.failed")}</strong></div>;
  if (!notes) return <div className="empty-state">{t("notes.loading")}</div>;
  if (!notes.results.length) return <div className="empty-state"><strong>{t("notes.empty")}</strong><span>{t("notes.emptyText")}</span></div>;
  return <div className={styles.grid}>{notes.results.map(note => <Link className={styles.card} href={`/titles/${note.title.slug}`} key={note.title.slug}><strong>{note.title.name}</strong><p>{note.body}</p><small>{new Date(note.updated_at).toLocaleDateString(intlLocale[locale])}</small></Link>)}</div>;
}
