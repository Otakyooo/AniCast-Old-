"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { deleteTitleNote, getTitleNote, NoteApiError, putTitleNote } from "../lib/notes";
import styles from "../app/notes/notes.module.css";
import { useI18n } from "./i18n-provider";

export function TitleNoteControl({ slug }: { slug: string }) {
  const { t } = useI18n();
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
      else setError(t("common.error"));
    });
    return () => controller.abort();
  }, [slug, t]);
  async function save() { setPending(true); setError(""); try { await putTitleNote(slug, body); setExists(true); } catch { setError(t("common.error")); } finally { setPending(false); } }
  async function remove() { setPending(true); try { await deleteTitleNote(slug); setBody(""); setExists(false); } catch { setError(t("common.error")); } finally { setPending(false); } }
  if (guest) return <section className={styles.control}><p><Link href="/login">{t("common.login")}</Link>: {t("notes.guest")}</p></section>;
  return <section className={styles.control}><div className={styles.heading}><h2>{t("notes.personal")}</h2><span>{body.length}/2000</span></div><textarea value={body} onChange={event => setBody(event.target.value)} maxLength={2000} rows={5} placeholder={t("notes.placeholder")} /><div className={styles.actions}><button type="button" disabled={pending || !body.trim()} onClick={save}>{t("common.save")}</button>{exists && <button type="button" disabled={pending} onClick={remove}>{t("common.delete")}</button>}</div>{error && <span className={styles.error}>{error}</span>}</section>;
}
