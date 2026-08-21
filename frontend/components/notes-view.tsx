"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getNotes, NoteApiError, type NotesResponse } from "../lib/notes";
import styles from "../app/notes/notes.module.css";

export function NotesView() {
  const [notes, setNotes] = useState<NotesResponse>();
  const [guest, setGuest] = useState(false);
  useEffect(() => { const controller = new AbortController(); getNotes(controller.signal).then(setNotes).catch(reason => { if (reason instanceof NoteApiError && [401,403].includes(reason.status)) setGuest(true); }); return () => controller.abort(); }, []);
  if (guest) return <div className="empty-state"><strong>Войдите в аккаунт</strong><Link href="/login">Войти</Link></div>;
  if (!notes) return <div className="empty-state">Загружаем заметки...</div>;
  if (!notes.results.length) return <div className="empty-state"><strong>Заметок пока нет</strong><span>Добавьте заметку на странице тайтла.</span></div>;
  return <div className={styles.grid}>{notes.results.map(note => <Link className={styles.card} href={`/titles/${note.title.slug}`} key={note.title.slug}><strong>{note.title.name}</strong><p>{note.body}</p><small>{new Date(note.updated_at).toLocaleDateString("ru-RU")}</small></Link>)}</div>;
}
