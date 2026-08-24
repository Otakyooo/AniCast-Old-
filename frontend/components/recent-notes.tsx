"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getNotes, type TitleNote } from "../lib/notes";
import { useI18n } from "./i18n-provider";
import styles from "../app/profile.module.css";

const RECENT_NOTES_LIMIT = 3;

/**
 * Latest personal notes for the account hub. Collapses entirely for guests,
 * failures and empty lists so the cabinet never shows placeholder blocks.
 */
export function RecentNotes() {
  const { t } = useI18n();
  const [notes, setNotes] = useState<TitleNote[] | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getNotes(controller.signal)
      .then((page) => setNotes(page.results.slice(0, RECENT_NOTES_LIMIT)))
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setNotes([]);
      });
    return () => controller.abort();
  }, []);

  if (!notes || notes.length === 0) return null;

  return (
    <section aria-label={t("account.recentNotes")}>
      <div className={styles.notesHeading}>
        <h2>{t("account.recentNotes")}</h2>
        <Link href="/notes">{t("notes.title")} →</Link>
      </div>
      <ul className={styles.notesList}>
        {notes.map((note) => (
          <li key={note.title.slug}>
            <Link className={styles.noteCard} href={`/titles/${note.title.slug}`}>
              <span className={styles.noteTitle}>{note.title.name}</span>
              <span className={styles.noteBody}>{note.body}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
