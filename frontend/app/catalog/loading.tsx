import { getI18n } from "../../i18n/server";

export default async function CatalogLoading() {
  const { t } = await getI18n();
  return <main className="shell"><section className="content"><div className="page-heading"><p className="eyebrow">{t("catalog.eyebrow")}</p><h1>{t("catalog.title")}</h1></div><div className="catalog-grid" aria-label={t("common.loading")} aria-busy="true">{[1, 2, 3, 4].map(item => <div className="catalog-card skeleton-card" key={item}><div className="poster-placeholder" /><div className="catalog-card-body"><span className="skeleton-line short" /><span className="skeleton-line" /><span className="skeleton-line small" /></div></div>)}</div></section></main>;
}
