import Link from "next/link";
import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";
import { emptyPage, getMedia, type MediaResponse } from "../../lib/api";
import styles from "../discovery.module.css";

export const dynamic = "force-dynamic";

export default async function MediaPage({ searchParams }: { searchParams: Promise<{ kind?: string }> }) {
  const kind = (await searchParams).kind ?? "";
  const [data, { t }] = await Promise.all([getMedia(kind).catch((): MediaResponse => emptyPage()), getI18n()]);

  return <PageShell active="media" heading={{ eyebrow: t("media.title"), title: t("media.title"), subtitle: t("media.subtitle") }}>
    <nav className={styles.filters}>
      <Link href="/media">{t("media.all")}</Link>
      <Link href="/media?kind=image">{t("media.image")}</Link>
      <Link href="/media?kind=trailer">{t("media.trailer")}</Link>
      <Link href="/media?kind=promo">{t("media.promo")}</Link>
    </nav>
    {data.results.length ? (
      <div className={styles.grid}>
        {data.results.map(asset => (
          <a className={styles.mediaCard} href={asset.url} target="_blank" rel="noreferrer" key={asset.id}>
            <div className={styles.mediaPreview}>{t(`media.${asset.kind}`)}</div>
            <strong>{asset.caption || asset.title?.name || asset.character?.name}</strong>
            <small>{t("media.credit", { credit: asset.credit })}</small>
          </a>
        ))}
      </div>
    ) : (
      <div className="empty-state"><strong>{t("media.empty")}</strong></div>
    )}
  </PageShell>;
}
