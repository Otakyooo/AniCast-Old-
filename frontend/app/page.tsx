import Link from "next/link";
import { AccountLink } from "../components/account-link";
import { CatalogCard } from "../components/catalog-card";
import { HistoryView } from "../components/history-view";
import { Sidebar } from "../components/sidebar";
import { getCatalog } from "../lib/api";
import { getI18n } from "../i18n/server";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const catalog = await getCatalog({ pageSize: 4 });
  const { t } = await getI18n();

  return <main className="shell">
    <Sidebar active="home" />
    <section className="content"><header className="topbar"><form className="search" action="/catalog"><span aria-hidden="true">⌕</span><input name="q" aria-label={t("catalog.searchLabel")} placeholder={t("catalog.searchPlaceholder")} /><button type="submit" className="search-submit">{t("common.search")}</button></form><AccountLink /></header><div className="hero"><p className="eyebrow">{t("home.eyebrow")}</p><h1>{t("home.title")}</h1><p className="muted">{t("home.subtitle")}</p><Link className="primary inline-button" href="/catalog">{t("home.openCatalog")}</Link></div><HistoryView compact /><section className="section"><div className="section-heading"><h2>{t("home.discover")}</h2><Link href="/catalog">{t("home.allCatalog")}</Link></div>{catalog.results.length ? <div className="catalog-grid">{catalog.results.map(item => <CatalogCard item={item} key={item.slug} />)}</div> : <div className="empty-state"><strong>{t("home.empty")}</strong><span>{t("home.emptyText")}</span></div>}</section></section>
  </main>;
}
