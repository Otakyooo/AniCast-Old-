import Link from "next/link";
import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";
import { emptyPage, getMedia, type MediaResponse } from "../../lib/api";
import styles from "../discovery.module.css";

export const dynamic = "force-dynamic";

const KINDS = ["", "image", "trailer", "promo"] as const;

export default async function MediaPage({ searchParams }: { searchParams: Promise<{ kind?: string }> }) {
  const requested = (await searchParams).kind ?? "";
  // An unknown kind would make the API answer 400, so fall back to "all".
  const kind = (KINDS as readonly string[]).includes(requested) ? requested : "";
  const [data, { t }] = await Promise.all([getMedia(kind).catch((): MediaResponse => emptyPage()), getI18n()]);
  const label: Record<string, string> = {
    "": t("media.all"),
    image: t("media.image"),
    trailer: t("media.trailer"),
    promo: t("media.promo"),
  };

  return <PageShell active="media" heading={{ eyebrow: t("media.title"), title: t("media.title"), subtitle: t("media.subtitle") }}>
    <nav className={styles.filters} aria-label={t("media.title")}>
      {KINDS.map((value) => (
        <Link
          className={value === kind ? styles.filterActive : undefined}
          aria-current={value === kind ? "page" : undefined}
          href={value ? `/media?kind=${value}` : "/media"}
          key={value || "all"}
        >
          {label[value]}
        </Link>
      ))}
    </nav>
    {data.results.length ? (
      <div className={styles.grid}>
        {data.results.map(asset => (
          <a className={styles.mediaCard} href={asset.url} target="_blank" rel="noreferrer" key={asset.id}>
            <div className={styles.mediaPreview}>{t(`media.${asset.kind}`)}</div>
            <strong>{asset.caption || asset.title?.name || asset.character?.name || t("media.title")}</strong>
            <small>{t("media.credit", { credit: asset.credit })}</small>
          </a>
        ))}
      </div>
    ) : (
      <div className="empty-state" role="status"><strong>{t("media.empty")}</strong></div>
    )}
  </PageShell>;
}
