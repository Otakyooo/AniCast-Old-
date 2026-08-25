import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";
import { getI18n } from "../../../i18n/server";
import styles from "../../not-found.module.css";

export const metadata: Metadata = { title: "404 — AniCast" };

export default async function TitleNotFound() {
  const { t } = await getI18n();
  return (
    <main className={`shell ${styles.notFoundPage}`}>
      <div className={styles.panel} role="status">
        <Image
          className={styles.mascot}
          src="/not-found-mascot.webp"
          alt={t("notFound.mascotAlt")}
          width={800}
          height={731}
          priority
          sizes="(max-width: 640px) 70vw, 380px"
        />
        <p className="eyebrow">404</p>
        <h1>{t("title.notFound")}</h1>
        <p className="muted">{t("title.notFoundText")}</p>
        <div className={styles.actions}>
          <Link className="primary inline-button" href="/catalog">{t("catalog.title")}</Link>
          <Link className="secondary" href="/">{t("account.home")}</Link>
        </div>
      </div>
    </main>
  );
}
