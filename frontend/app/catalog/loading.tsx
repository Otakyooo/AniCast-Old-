import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";

export default async function CatalogLoading() {
  const { t } = await getI18n();
  return <PageShell active="catalog" heading={{ eyebrow: t("catalog.eyebrow"), title: t("catalog.title") }}>
    <div className="catalog-grid" aria-label={t("common.loading")} aria-busy="true">
      {[1, 2, 3, 4, 5, 6].map(item => (
        <div className="catalog-card skeleton-card" key={item}>
          <div className="poster-placeholder" />
          <div className="catalog-card-body">
            <span className="skeleton-line short" />
            <span className="skeleton-line" />
            <span className="skeleton-line small" />
          </div>
        </div>
      ))}
    </div>
  </PageShell>;
}
