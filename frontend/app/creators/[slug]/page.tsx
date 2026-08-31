import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";
import { User } from "@phosphor-icons/react/dist/ssr";
import { CatalogCard } from "../../../components/catalog-card";
import { PageShell } from "../../../components/page-shell";
import { ApiUnavailableState } from "../../../components/api-unavailable";
import { apiErrorStatus, getCreator } from "../../../lib/api";
import { hasCharacterArt } from "../../../lib/character-image";
import { getI18n } from "../../../i18n/server";
import styles from "../creator.module.css";

export const dynamic = "force-dynamic";

function decodeRouteSlug(slug: string) {
  try {
    return decodeURIComponent(slug);
  } catch {
    return slug;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  try {
    const creator = await getCreator(decodeRouteSlug(slug));
    return { title: creator.name, alternates: { canonical: `/creators/${creator.slug}` } };
  } catch {
    return { title: "AniCast" };
  }
}

export default async function CreatorPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { t } = await getI18n();
  let creator;
  try { creator = await getCreator(decodeRouteSlug(slug)); }
  catch (error) {
    if (apiErrorStatus(error) === 404) notFound();
    return <ApiUnavailableState />;
  }

  return (
    <PageShell active="catalog" back={{ href: "/catalog", label: t("catalog.title") }}>
      <header className={styles.header}>
        <span className={styles.portrait} aria-hidden="true">
          {hasCharacterArt(creator.image_url) ? (
            <Image src={creator.image_url} alt="" fill sizes="92px" quality={92} referrerPolicy="no-referrer" priority />
          ) : <User size={38} weight="bold" />}
        </span>
        <div>
          <p className="eyebrow">{t("creator.eyebrow")}</p>
          <h1>{creator.name}</h1>
          <p>{t("creator.worksCount", { count: creator.title_credits.length })}</p>
        </div>
      </header>
      <section className={styles.works}>
        <h2>{t("creator.works")}</h2>
        <div className={styles.grid}>
          {creator.title_credits.map((credit) => (
            <article className={styles.work} key={`${credit.title.slug}-${credit.role}`}>
              <CatalogCard item={credit.title} variant="media" />
              <span>{credit.role_label}</span>
            </article>
          ))}
        </div>
      </section>
    </PageShell>
  );
}
