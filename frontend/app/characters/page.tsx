import Link from "next/link";
import { AccountLink } from "../../components/account-link";
import { Sidebar } from "../../components/sidebar";
import { getI18n } from "../../i18n/server";
import { emptyPage, getCharacters, type CharacterResponse } from "../../lib/api";
import styles from "../discovery.module.css";

export const dynamic = "force-dynamic";

export default async function CharactersPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const query = (await searchParams).q?.trim() ?? "";
  const [data, { t }] = await Promise.all([getCharacters(query).catch((): CharacterResponse => emptyPage()), getI18n()]);
  return <main className="shell"><Sidebar active="characters" /><section className="content"><header className="topbar"><form className="search" action="/characters"><input name="q" defaultValue={query} placeholder={t("character.search")} /><button className="search-submit">{t("common.search")}</button></form><AccountLink /></header><div className="page-heading"><h1>{t("character.title")}</h1><p className="muted">{t("character.subtitle")}</p></div>{data.results.length ? <div className={styles.grid}>{data.results.map(character => <Link className={styles.card} href={`/characters/${character.slug}`} key={character.slug}><div className={styles.avatar}>{character.name.slice(0,1)}</div><h2>{character.name}</h2><p>{character.description || t("character.descriptionMissing")}</p><small>{t("franchise.count", { count: character.title_count })}</small></Link>)}</div> : <div className="empty-state"><strong>{t("character.empty")}</strong></div>}</section></main>;
}
