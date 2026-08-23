import Image from "next/image";
import { notFound } from "next/navigation";
import { ApiUnavailableState } from "../../../components/api-unavailable";
import { CatalogCard } from "../../../components/catalog-card";
import { PageShell } from "../../../components/page-shell";
import { getI18n } from "../../../i18n/server";
import { apiErrorStatus, getCharacter } from "../../../lib/api";
import styles from "../../discovery.module.css";

export const dynamic = "force-dynamic";

export default async function CharacterPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { t } = await getI18n();
  let character;
  try { character = await getCharacter(slug); }
  catch (error) { if (apiErrorStatus(error) === 404) notFound(); return <ApiUnavailableState />; }

  return <PageShell active="characters" back={{ href: "/characters", label: t("character.title") }}>
    <div className={styles.hero}>
      <div className={styles.portraitWrap}>
        {character.image_url
          ? <Image className="poster-image" src={character.image_url} alt={character.name} fill sizes="220px" referrerPolicy="no-referrer" />
          : <div>{character.name.slice(0, 1)}</div>}
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
