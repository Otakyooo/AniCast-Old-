import Link from "next/link";
import { getI18n } from "../i18n/server";

export default async function NotFound() {
  const { t } = await getI18n();
  return (
    <main className="shell">
      <section className="content">
        <div className="state-panel" role="status">
          <p className="eyebrow">404</p>
          <h1>{t("notFound.title")}</h1>
          <p className="muted">{t("notFound.text")}</p>
          <Link className="primary inline-button" href="/">{t("account.home")}</Link>
          <Link className="secondary" href="/catalog">{t("catalog.title")}</Link>
        </div>
      </section>
    </main>
  );
}
