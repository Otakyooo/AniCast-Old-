import Link from "next/link";
import { getI18n } from "../i18n/server";
import { BrandLockup } from "./brand-lockup";

export async function SiteFooter() {
  const { t } = await getI18n();

  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="site-footer-brand">
          <BrandLockup className="footer-brand" />
          <p>{t("footer.aboutText")}</p>
        </div>
        <nav className="site-footer-links" aria-label={t("footer.navigation")}>
          <Link href="/catalog">{t("nav.catalog")}</Link>
          <Link href="/schedule">{t("nav.schedule")}</Link>
          <Link href="/franchises">{t("nav.franchises")}</Link>
          <Link href="/collections">{t("nav.collections")}</Link>
          <Link href="/community">{t("nav.community")}</Link>
        </nav>
        <div className="site-footer-meta">
          <small>© {new Date().getUTCFullYear()} Anicast</small>
        </div>
      </div>
    </footer>
  );
}
