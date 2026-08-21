"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getHistory, HistoryApiError, type HistoryResponse } from "../lib/history";
import styles from "../app/history.module.css";

export function HistoryView({ compact = false }: { compact?: boolean }) {
  const [history, setHistory] = useState<HistoryResponse>();
  const [guest, setGuest] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getHistory(compact ? 4 : 20, controller.signal).then(setHistory).catch((reason) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof HistoryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(true);
    });
    return () => controller.abort();
  }, [compact]);

  if (compact && (guest || error || (history && !history.results.length))) return null;
  if (guest) return <div className="empty-state"><strong>История доступна после входа</strong><span>Мы сохраняем только открытые эпизоды и явные отметки.</span><Link href="/login">Войти</Link></div>;
  if (error) return <div className="empty-state" role="alert"><strong>Историю не удалось загрузить</strong></div>;
  if (!history) return <div className="empty-state" role="status"><strong>Загружаем историю...</strong></div>;
  if (!history.results.length) return <div className="empty-state"><strong>История пока пуста</strong><span>Откройте страницу эпизода из карточки тайтла.</span></div>;

  const content = <div className={styles.historyGrid}>{history.results.map((entry) => <Link className={styles.historyCard} href={`/titles/${entry.title.slug}/episodes/${entry.episode.number}`} key={entry.episode.id}><span className={styles.number}>Эпизод {entry.episode.number}</span><strong>{entry.title.name}</strong><span>{entry.episode.name || "Без названия"}</span><small>{entry.is_watched ? "Просмотрено" : "Недавно открывали"}</small></Link>)}</div>;
  if (!compact) return content;
  return <section className="section"><div className="section-heading"><h2>Недавно открывали</h2><Link href="/history">Вся история →</Link></div>{content}</section>;
}
