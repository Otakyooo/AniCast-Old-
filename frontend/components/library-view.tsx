"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CatalogCard } from "./catalog-card";
import { getLibrary, LibraryApiError, type LibraryResponse } from "../lib/library";
import styles from "../app/library/library.module.css";

const filters = [
  ["Все", "/library"], ["Смотрю", "/library?status=watching"], ["Запланировано", "/library?status=planned"],
  ["Просмотрено", "/library?status=completed"], ["Отложено", "/library?status=on_hold"], ["Брошено", "/library?status=dropped"], ["Избранное", "/library?favorite=true"],
];
const statusLabels: Record<string, string> = { planned: "Запланировано", watching: "Смотрю", completed: "Просмотрено", on_hold: "Отложено", dropped: "Брошено" };

export function LibraryView() {
  const params = useSearchParams();
  const [data, setData] = useState<LibraryResponse>();
  const [guest, setGuest] = useState(false);
  const [error, setError] = useState("");
  const status = params.get("status") ?? undefined;
  const favorite = params.get("favorite") === "true";
  const page = Math.max(1, Number(params.get("page")) || 1);

  useEffect(() => {
    const controller = new AbortController();
    setData(undefined); setError(""); setGuest(false);
    getLibrary({ status, favorite, page }, controller.signal).then(setData).catch((reason) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof LibraryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError("Не удалось загрузить библиотеку.");
    });
    return () => controller.abort();
  }, [status, favorite, page]);

  if (guest) return <div className="empty-state"><strong>Войдите в аккаунт</strong><span>Личная библиотека синхронизируется между устройствами.</span><Link className={styles.primary} href="/login">Войти</Link></div>;
  if (error) return <div className="empty-state" role="alert"><strong>{error}</strong><span>Обновите страницу или попробуйте позже.</span></div>;
  if (!data) return <div className="empty-state" role="status"><strong>Загружаем библиотеку...</strong></div>;

  const filterQuery = status ? `status=${status}` : favorite ? "favorite=true" : "";
  const pageHref = (target: number) => `/library?${filterQuery}${filterQuery ? "&" : ""}page=${target}`;
  const pageCount = Math.max(1, Math.ceil(data.count / 20));
  return <>
    <nav className={styles.filters} aria-label="Фильтры библиотеки">{filters.map(([label, href]) => <Link href={href} key={label}>{label}</Link>)}</nav>
    {data.results.length ? <div className={styles.grid}>{data.results.map((entry) => <div className={styles.entry} key={entry.title.slug}><CatalogCard item={entry.title} /><div className={styles.entryMeta}><span>{statusLabels[entry.status]}</span>{entry.is_favorite && <span>Избранное</span>}</div></div>)}</div> : <div className="empty-state"><strong>Здесь пока пусто</strong><span>Добавляйте тайтлы из каталога и распределяйте их по статусам.</span><Link className={styles.primary} href="/catalog">Открыть каталог</Link></div>}
    {pageCount > 1 && <div className={styles.pagination}>{page > 1 && <Link href={pageHref(page - 1)}>← Назад</Link>}<span>{page} из {pageCount}</span>{page < pageCount && <Link href={pageHref(page + 1)}>Вперёд →</Link>}</div>}
  </>;
}
