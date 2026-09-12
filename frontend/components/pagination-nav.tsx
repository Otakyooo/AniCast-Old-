import Link from "next/link";
import { getI18n } from "../i18n/server";
import { paginationWindow } from "../lib/pagination";
import styles from "./pagination-nav.module.css";

/**
 * Numbered pagination shared by secondary lists (franchises, community).
 *
 * The catalog keeps its own local variant with filter-aware hrefs; point new
 * lists here instead of copying the window logic again. Renders nothing for a
 * single page so callers can mount it unconditionally.
 */
export async function PaginationNav({
  currentPage,
  pageCount,
  makeHref,
}: {
  currentPage: number;
  pageCount: number;
  makeHref: (page: number) => string;
}) {
  if (pageCount <= 1) return null;
  const { t } = await getI18n();
  const pages = paginationWindow(currentPage, pageCount);
  return (
    <nav className={styles.pagination} aria-label={t("common.pagination")}>
      {currentPage > 1 ? (
        <Link className={styles.pageLink} href={makeHref(currentPage - 1)}>{t("common.back")}</Link>
      ) : (
        <span className={styles.pageDisabled} aria-hidden="true">{t("common.back")}</span>
      )}
      {pages.flatMap((page, index) => {
        const previous = pages[index - 1];
        const gap = previous !== undefined && page - previous > 1;
        const link = page === currentPage ? (
          <span className={`${styles.pageLink} ${styles.pageLinkCurrent}`} aria-current="page" key={page}>
            {page}
          </span>
        ) : (
          <Link className={styles.pageLink} href={makeHref(page)} key={page}>
            {page}
          </Link>
        );
        return gap ? [(
          <span className={styles.pageGap} aria-hidden="true" key={`gap-${previous}-${page}`}>…</span>
        ), link] : [link];
      })}
      {currentPage < pageCount ? (
        <Link className={styles.pageLink} href={makeHref(currentPage + 1)}>{t("common.next")}</Link>
      ) : (
        <span className={styles.pageDisabled} aria-hidden="true">{t("common.next")}</span>
      )}
    </nav>
  );
}
