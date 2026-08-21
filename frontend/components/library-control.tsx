"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { deleteLibraryEntry, getLibraryEntry, LibraryApiError, putLibraryEntry, type LibraryEntry, type LibraryStatus } from "../lib/library";
import styles from "../app/library/library.module.css";

const labels: Record<LibraryStatus, string> = { planned: "Запланировано", watching: "Смотрю", completed: "Просмотрено", on_hold: "Отложено", dropped: "Брошено" };

export function LibraryControl({ slug }: { slug: string }) {
  const [entry, setEntry] = useState<LibraryEntry | null>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setEntry(undefined);
    setGuest(false);
    setError("");
    getLibraryEntry(slug, controller.signal).then(setEntry).catch((reason) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof LibraryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError("Не удалось загрузить состояние библиотеки.");
    });
    return () => controller.abort();
  }, [slug]);

  async function update(status: LibraryStatus, favorite: boolean) {
    setPending(true);
    setError("");
    try { setEntry(await putLibraryEntry(slug, { status, is_favorite: favorite })); }
    catch { setError("Не удалось сохранить изменение."); }
    finally { setPending(false); }
  }

  async function remove() {
    setPending(true);
    setError("");
    try { await deleteLibraryEntry(slug); setEntry(null); }
    catch { setError("Не удалось удалить тайтл из библиотеки."); }
    finally { setPending(false); }
  }

  if (guest) return <div className={styles.control}><p>Войдите, чтобы сохранить тайтл и синхронизировать библиотеку.</p><Link className={styles.primary} href="/login">Войти</Link></div>;
  if (entry === undefined) return <div className={styles.control} role="status">Загружаем библиотеку...</div>;
  if (entry === null) return <div className={styles.control}><p>Добавьте тайтл, чтобы вернуться к нему позже.</p><button className={styles.primary} type="button" disabled={pending} onClick={() => update("planned", false)}>Добавить в библиотеку</button>{error && <span className={styles.error} role="alert">{error}</span>}</div>;

  return <div className={styles.control}>
    <label><span>Мой статус</span><select value={entry.status} disabled={pending} onChange={(event) => update(event.target.value as LibraryStatus, entry.is_favorite)}>{Object.entries(labels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
    <button className={entry.is_favorite ? styles.favoriteActive : styles.secondary} type="button" disabled={pending} aria-pressed={entry.is_favorite} onClick={() => update(entry.status, !entry.is_favorite)}>{entry.is_favorite ? "В избранном" : "В избранное"}</button>
    <button className={styles.danger} type="button" disabled={pending} onClick={remove}>Удалить</button>
    {error && <span className={styles.error} role="alert">{error}</span>}
  </div>;
}
