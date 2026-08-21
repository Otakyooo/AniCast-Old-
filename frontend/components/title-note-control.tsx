"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { deleteTitleNote, getTitleNote, NoteApiError, putTitleNote } from "../lib/notes";
import styles from "../app/notes/notes.module.css";

export function TitleNoteControl({ slug }: { slug: string }) {
  const [body, setBody] = useState("");
  const [exists, setExists] = useState(false);
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    getTitleNote(slug, controller.signal).then(note => { if (note) { setBody(note.body); setExists(true); } }).catch(reason => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof NoteApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError("Не удалось загрузить заметку.");
    });
    return () => controller.abort();
  }, [slug]);
  async function save() { setPending(true); setError(""); try { await putTitleNote(slug, body); setExists(true); } catch { setError("Не удалось сохранить заметку."); } finally { setPending(false); } }
  async function remove() { setPending(true); try { await deleteTitleNote(slug); setBody(""); setExists(false); } catch { setError("Не удалось удалить заметку."); } finally { setPending(false); } }
  if (guest) return <section className={styles.control}><p><Link href="/login">Войдите</Link>, чтобы сохранить личную заметку.</p></section>;
  return <section className={styles.control}><div className={styles.heading}><h2>Личная заметка</h2><span>{body.length}/2000</span></div><textarea value={body} onChange={event => setBody(event.target.value)} maxLength={2000} rows={5} placeholder="Мысли, детали и контекст для себя" /><div className={styles.actions}><button type="button" disabled={pending || !body.trim()} onClick={save}>Сохранить</button>{exists && <button type="button" disabled={pending} onClick={remove}>Удалить</button>}</div>{error && <span className={styles.error}>{error}</span>}</section>;
}
