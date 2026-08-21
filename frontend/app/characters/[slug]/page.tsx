import Link from "next/link";
import { notFound } from "next/navigation";
import { AccountLink } from "../../../components/account-link";
import { CatalogCard } from "../../../components/catalog-card";
import { Sidebar } from "../../../components/sidebar";
import { getI18n } from "../../../i18n/server";
import { getCharacter } from "../../../lib/api";
import styles from "../../discovery.module.css";

export const dynamic = "force-dynamic";

export default async function CharacterPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let character;
  try { character = await getCharacter(slug); } catch { notFound(); }
  const { t } = await getI18n();
  return <main className="shell"><Sidebar active="characters" /><section className="content"><header className="topbar"><Link className="back-link" href="/characters">← {t("character.title")}</Link><AccountLink /></header><div className={styles.hero}><div className={styles.portrait}>{character.name.slice(0,1)}</div><div className={styles.copy}><p className="eyebrow">{t("character.title")}</p><h1>{character.name}</h1>{character.original_name && <span className="muted">{character.original_name}</span>}<p>{character.description || t("character.descriptionMissing")}</p></div></div><section><div className="section-heading"><h2>{t("character.titles")}</h2></div>{character.title_links.length ? <div className="catalog-grid">{character.title_links.map(link => <div key={link.title.slug}><CatalogCard item={link.title} /><span className={styles.score}>{t(`role.${link.role}`)}</span></div>)}</div> : <div className="empty-state">{t("franchise.unlinked")}</div>}</section></section></main>;
}
