import Link from "next/link";
import { AccountLink } from "../../components/account-link";
import { CatalogCard } from "../../components/catalog-card";
import { Sidebar } from "../../components/sidebar";
import { getCatalog, type CatalogFilters } from "../../lib/api";
import styles from "./catalog.module.css";

export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;

function firstValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function catalogHref(filters: CatalogFilters, page: number) {
  const query = new URLSearchParams();
  if (filters.q) query.set("q", filters.q);
  if (filters.type) query.set("type", filters.type);
  if (filters.status) query.set("status", filters.status);
  if (page > 1) query.set("page", String(page));
  const suffix = query.toString();
  return suffix ? `/catalog?${suffix}` : "/catalog";
}

export default async function CatalogPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const requestedPage = Number.parseInt(firstValue(params.page), 10);
  const filters: CatalogFilters = {
    q: firstValue(params.q).trim(),
    type: firstValue(params.type),
    status: firstValue(params.status),
    page: Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1,
  };
  const catalog = await getCatalog(filters);
  const currentPage = filters.page ?? 1;
  const pageCount = Math.max(1, Math.ceil(catalog.count / 20));
  const hasFilters = Boolean(filters.q || filters.type || filters.status);

  return <main className="shell">
    <Sidebar active="catalog" />
    <section className="content"><header className="topbar"><form className="search" action="/catalog"><span aria-hidden="true">⌕</span><input name="q" defaultValue={filters.q} aria-label="Поиск по каталогу" placeholder="Поиск тайтлов, персонажей, франшиз..." />{filters.type && <input type="hidden" name="type" value={filters.type} />}{filters.status && <input type="hidden" name="status" value={filters.status} />}<button type="submit" className="search-submit">Найти</button></form><AccountLink /></header>
      <div className="page-heading"><p className="eyebrow">КОЛЛЕКЦИЯ ANICAST</p><h1>Каталог</h1><p className="muted">Находи новые миры и собирай библиотеку, к которой хочется возвращаться.</p></div>
      <form className={styles.filters} action="/catalog">
        {filters.q && <input type="hidden" name="q" value={filters.q} />}
        <label className={styles.field}><span>Формат</span><select name="type" defaultValue={filters.type}><option value="">Все форматы</option><option value="anime">Сериал</option><option value="movie">Фильм</option><option value="ova">OVA</option><option value="special">Спешл</option></select></label>
        <label className={styles.field}><span>Статус</span><select name="status" defaultValue={filters.status}><option value="">Любой статус</option><option value="ongoing">Выходит</option><option value="finished">Завершено</option><option value="planned">Запланировано</option></select></label>
        <button className={styles.submit} type="submit">Применить</button>
        {hasFilters && <Link className={styles.reset} href="/catalog">Сбросить</Link>}
      </form>
      {catalog.results.length ? <div className="catalog-grid">{catalog.results.map(item => <CatalogCard item={item} key={item.slug} />)}</div> : <div className="empty-state" role="status"><strong>{hasFilters ? "Ничего не найдено" : "Каталог пока пуст"}</strong><span>{hasFilters ? "Попробуй изменить параметры или посмотреть всю коллекцию." : "Скоро здесь появятся тайтлы AniCast."}</span>{hasFilters && <Link className="secondary" href="/catalog">Сбросить фильтры</Link>}</div>}
      {pageCount > 1 && <nav className={styles.pagination} aria-label="Пагинация каталога">{currentPage > 1 && <Link className={styles.pageLink} href={catalogHref(filters, currentPage - 1)}>← Назад</Link>}<span>Страница {currentPage} из {pageCount}</span>{currentPage < pageCount && <Link className={styles.pageLink} href={catalogHref(filters, currentPage + 1)}>Вперёд →</Link>}</nav>}
    </section>
  </main>;
}
