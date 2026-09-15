import Link from "next/link";
import { getI18n } from "../i18n/server";
import { BrandLockup } from "./brand-lockup";

/** The project's only public contact channel. */
const SUPPORT_EMAIL = "support@anicast.online";

/**
 * Service footer: brand, a one-line description of the project and the two
 * channels that are not already in the header — community and support.
 *
 * Primary routes (catalog, schedule, franchises, collections) deliberately do
 * not appear here. They live in the header and in the catalog, and repeating
 * them turned the footer into a second navigation bar to keep in sync.
 */
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
          <Link href="/community">{t("nav.community")}</Link>
          <a href={`mailto:${SUPPORT_EMAIL}`}>{t("footer.support")}</a>
        </nav>
        <div className="site-footer-meta">
          <small>© {new Date().getUTCFullYear()} Anicast</small>
        </div>
      </div>
    </footer>
  );
}
