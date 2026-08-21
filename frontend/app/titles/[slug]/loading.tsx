import { getI18n } from "../../../i18n/server";

export default async function CatalogDetailLoading() {
  const { t } = await getI18n();
  return <main className="shell"><section className="content"><div className="detail skeleton-detail" aria-label={t("common.loading")} aria-busy="true"><div className="detail-poster poster-placeholder" /><div className="detail-copy"><span className="skeleton-line short" /><span className="skeleton-line title" /><span className="skeleton-line" /><span className="skeleton-line" /></div></div></section></main>;
}
