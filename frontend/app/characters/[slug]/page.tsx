import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ApiUnavailableState } from "../../../components/api-unavailable";
import { BreadcrumbsJsonLd } from "../../../components/breadcrumbs-jsonld";
import { CatalogCard } from "../../../components/catalog-card";
import { CharacterAvatar } from "../../../components/character-avatar";
import { PageShell } from "../../../components/page-shell";
import { getI18n } from "../../../i18n/server";
import { apiErrorStatus, getCharacter } from "../../../lib/api";
import { hasCharacterArt } from "../../../lib/character-image";
import { absoluteUrl, metaDescription } from "../../../lib/site";
import styles from "../../discovery.module.css";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const { t } = await getI18n();
  try {
    const character = await getCharacter(slug);
    const description = metaDescription(character.description, t("character.descriptionMissing"));
    return {
      title: character.name,
      description,
      alternates: { canonical: `/characters/${character.slug}` },
      openGraph: {
        type: "profile",
        url: `/characters/${character.slug}`,
        title: character.name,
        description,
        ...(hasCharacterArt(character.image_url) ? { images: [{ url: absoluteUrl(character.image_url), alt: character.name }] } : {}),
      },
    };
  } catch (error) {
    // The page component owns the 404: notFound() inside generateMetadata
    // races the render and can answer 200 with the not-found UI.
    return {};
  }
}

export default async function CharacterPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { t } = await getI18n();
  let character;
  try { character = await getCharacter(slug); }
  catch (error) { if (apiErrorStatus(error) === 404) notFound(); return <ApiUnavailableState />; }

  return <PageShell active="catalog" back={{ href: "/catalog", label: t("catalog.title") }}>
    <BreadcrumbsJsonLd
      items={[
        { name: t("account.home"), href: "/" },
        { name: t("catalog.title"), href: "/catalog" },
        { name: character.name, href: `/characters/${character.slug}` },
      ]}
    />
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "Person",
          name: character.name,
          ...(character.original_name ? { alternateName: character.original_name } : {}),
          ...(character.description ? { description: character.description } : {}),
          ...(hasCharacterArt(character.image_url) ? { image: absoluteUrl(character.image_url) } : {}),
          url: absoluteUrl(`/characters/${character.slug}`),
        }),
      }}
    />
    <div className={styles.hero}>
      <div className={styles.portraitWrap}>
        <CharacterAvatar imageUrl={character.image_url} alt={character.name} sizes="220px" />
      </div>
      <div className={styles.copy}>
        <p className="eyebrow">{t("character.title")}</p>
        <h1>{character.name}</h1>
        {character.original_name && <span className="muted">{character.original_name}</span>}
        <p>{character.description || t("character.descriptionMissing")}</p>
      </div>
    </div>
    <section className="section">
      <div className="section-heading"><h2>{t("character.titles")}</h2></div>
      {character.title_links.length ? (
        <div className="catalog-grid">
          {character.title_links.map(link => (
            <div key={link.title.slug}>
              <CatalogCard item={link.title} />
              <span className={styles.score}>{t(`role.${link.role}`)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">{t("franchise.unlinked")}</div>
      )}
    </section>
  </PageShell>;
}
