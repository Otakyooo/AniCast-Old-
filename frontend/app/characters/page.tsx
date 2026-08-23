import Image from "next/image";
import Link from "next/link";
import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";
import { emptyPage, getCharacters, type CharacterResponse } from "../../lib/api";
import styles from "../discovery.module.css";

export const dynamic = "force-dynamic";

export default async function CharactersPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const query = (await searchParams).q?.trim() ?? "";
  const [data, { t }] = await Promise.all([getCharacters(query).catch((): CharacterResponse => emptyPage()), getI18n()]);

  return <PageShell active="characters" heading={{ eyebrow: t("character.title"), title: t("character.title"), subtitle: t("character.subtitle") }}>
    <form className={styles.searchRow} action="/characters">
      <input name="q" defaultValue={query} aria-label={t("character.search")} placeholder={t("character.search")} />
      <button type="submit">{t("common.search")}</button>
    </form>
    {data.results.length ? (
      <div className={styles.grid}>
        {data.results.map(character => (
          <Link className={styles.card} href={`/characters/${character.slug}`} key={character.slug}>
            <div className={styles.avatarWrap}>
              {character.image_url
                ? <Image className="poster-image" src={character.image_url} alt="" fill sizes="220px" referrerPolicy="no-referrer" />
                : <div>{character.name.slice(0, 1)}</div>}
            </div>
            <h2>{character.name}</h2>
            <p>{character.description || t("character.descriptionMissing")}</p>
            <small>{t("franchise.count", { count: character.title_count })}</small>
          </Link>
        ))}
      </div>
    ) : (
      <div className="empty-state"><strong>{t("character.empty")}</strong></div>
    )}
  </PageShell>;
}
