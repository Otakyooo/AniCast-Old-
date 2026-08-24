import { PageShell } from "../../../components/page-shell";
import { getI18n } from "../../../i18n/server";
import styles from "../title.module.css";

export default async function CatalogDetailLoading() {
  const { t } = await getI18n();
  return <PageShell active="catalog" back={{ href: "/catalog", label: t("catalog.title") }}>
    <div className={`${styles.hero} skeleton-detail`} aria-label={t("common.loading")} aria-busy="true">
      <div className={styles.heroPoster} />
      <div className={styles.heroCopy}>
        <span className="skeleton-line short" />
        <span className="skeleton-line title" />
        <span className="skeleton-line" />
        <span className="skeleton-line small" />
      </div>
    </div>
  </PageShell>;
}
