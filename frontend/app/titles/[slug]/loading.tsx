import { PageShell } from "../../../components/page-shell";
import { getI18n } from "../../../i18n/server";

export default async function CatalogDetailLoading() {
  const { t } = await getI18n();
  return <PageShell active="catalog" back={{ href: "/catalog", label: t("catalog.title") }}>
    <div className="detail skeleton-detail" aria-label={t("common.loading")} aria-busy="true">
      <div className="detail-poster poster-placeholder" />
      <div className="detail-copy">
        <span className="skeleton-line short" />
        <span className="skeleton-line title" />
        <span className="skeleton-line" />
        <span className="skeleton-line" />
      </div>
    </div>
  </PageShell>;
}
