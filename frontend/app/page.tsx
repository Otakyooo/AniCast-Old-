import { headers } from "next/headers";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import { CatalogCard } from "../components/catalog-card";
import { ContinueWatchingBlock } from "../components/continue-watching-block";
import { RailScroller } from "../components/rail-scroller";
import { ScheduleStrip } from "../components/schedule-strip";
import { PageShell } from "../components/page-shell";
import {
  emptyPage,
  getCatalog,
  getFranchises,
  getSchedule,
  type CatalogItem,
  type FranchiseSummary,
  type ScheduleResponse,
} from "../lib/api";
import { addDays, localDayKey } from "../lib/schedule";
import { dedupeShelf } from "../lib/home-shelves";
import { getI18n } from "../i18n/server";
import { jsonLdScript, websiteJsonLd } from "../lib/seo";
import styles from "./home.module.css";

export const dynamic = "force-dynamic";

const SHELF_SIZE = 12;
const FRANCHISE_SHELF_SIZE = 8;
/** Below this size a shelf reads as abandoned rather than curated. */
const MIN_FULL_SHELF = 6;
/** A shelf with fewer cards is dropped: a titled one-card strip looks broken. */
const MIN_VISIBLE_SHELF = 4;

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getI18n();
  return {
    title: { absolute: t("meta.homeTitle") },
    description: t("meta.homeDescription"),
    alternates: { canonical: "/" },
  };
}

function CatalogShelf({
  title,
  subtitle,
  items,
  href,
  linkLabel,
  emptyLabel,
}: {
  title: string;
  subtitle: string;
  items: CatalogItem[];
  href: string;
  linkLabel: string;
  emptyLabel: string;
}) {
  return (
    <section className="section">
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <Link href={href}>{linkLabel}</Link>
      </div>
      {items.length ? (
        <RailScroller railClassName={styles.posterRail}>{items.map((item) => <CatalogCard item={item} key={item.slug} variant="media" />)}</RailScroller>
      ) : (
        <div className="empty-state" role="status"><strong>{emptyLabel}</strong></div>
      )}
    </section>
  );
}

function FranchiseCard({
  item,
  countLabel,
  yearsLabel,
}: {
  item: FranchiseSummary;
  countLabel: string;
  yearsLabel: string;
}) {
  const posters = item.poster_urls.slice(0, 3);
  return (
    <Link className={styles.franchiseCard} href={`/franchises/${item.slug}`} title={item.name}>
      {/* Three-poster strip: a franchise is many works, and the collage says
          so before any text does. */}
      <span className={styles.franchiseStrip} aria-hidden="true">
        {posters.length ? posters.map((url) => (
          <span className={styles.franchiseStripFrame} key={url}>
            <Image src={url} alt="" fill sizes="120px" quality={92} referrerPolicy="no-referrer" />
          </span>
        )) : <span className={styles.franchiseFallback}>{item.name.slice(0, 1).toUpperCase()}</span>}
      </span>
      <span className={styles.franchiseBody}>
        <strong>{item.name}</strong>
        <small>{[countLabel, yearsLabel].filter(Boolean).join(" · ")}</small>
      </span>
    </Link>
  );
}

export default async function HomePage() {
  const todayKey = localDayKey(new Date());
  // Every block degrades to an empty shelf instead of a 500 when the API is
  // briefly unreachable, which also keeps the container healthcheck independent
  // from the Caddy -> API chain during cold starts.
  const [ongoing, popular, newest, franchises, schedule, { locale, t }] = await Promise.all([
    getCatalog({ status: "ongoing", ordering: "popular", pageSize: SHELF_SIZE }).catch(() => emptyPage<CatalogItem>()),
    getCatalog({ ordering: "popular", pageSize: SHELF_SIZE }).catch(() => emptyPage<CatalogItem>()),
    getCatalog({ ordering: "recent", pageSize: SHELF_SIZE }).catch(() => emptyPage<CatalogItem>()),
    getFranchises(1, "", FRANCHISE_SHELF_SIZE).catch(() => emptyPage<FranchiseSummary>()),
    getSchedule(todayKey, addDays(todayKey, 2)).catch((): ScheduleResponse => emptyPage()),
    getI18n(),
  ]);
  const hasDenseAiringShelf = ongoing.results.length >= 4;
  const leadShelfItems = hasDenseAiringShelf ? ongoing.results : popular.results;
  // The shelves are filled from independent queries, so the same title can be
  // "ongoing" and "popular" at once. A repeated card on one screen reads as a
  // data bug, so each follower shelf drops what an earlier shelf already took.
  const popularShelfItems = dedupeShelf(leadShelfItems, popular.results);
  // The newest shelf prefers zero repeats, but deleting it whole left the
  // home page with nothing that pushes toward new titles. When a full dedup
  // leaves too few cards, it keeps only the lead shelf's exclusions and
  // tolerates overlap with "Популярное" — a repeated card is the lesser evil
  // next to an empty page.
  const newestFullyDeduped = dedupeShelf([...leadShelfItems, ...popularShelfItems], newest.results);
  const newestShelfItems = newestFullyDeduped.length >= MIN_FULL_SHELF
    ? newestFullyDeduped
    : dedupeShelf(leadShelfItems, newest.results);

  return <PageShell active="home">
    <script nonce={(await headers()).get("x-nonce") ?? undefined} type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(websiteJsonLd(locale)) }} />
    <div className={styles.homeColumn}>
      <ContinueWatchingBlock catalogCount={popular.count} featured={popular.results[0] ?? ongoing.results[0]} />

      {/* The strip owns its section: it disappears whole when nothing upcoming
          is left for the window, so the page never shows an empty heading. */}
      <ScheduleStrip items={schedule.results} serverTodayKey={todayKey} />

      <CatalogShelf
        title={hasDenseAiringShelf ? t("home.airingNow") : t("home.popular")}
        subtitle={hasDenseAiringShelf ? t("home.airingNowText") : t("home.popularText")}
        items={leadShelfItems}
        href={hasDenseAiringShelf ? "/catalog?status=ongoing" : "/catalog"}
        linkLabel={t("home.showAll")}
        emptyLabel={t("home.sectionEmpty")}
      />

      {hasDenseAiringShelf && <CatalogShelf
        title={t("home.popular")}
        subtitle={t("home.popularText")}
        items={popularShelfItems}
        href="/catalog"
        linkLabel={t("home.showAll")}
        emptyLabel={t("home.empty")}
      />}

      {/* Franchises are pure discovery: whole universes instead of single
          titles, and by construction they never duplicate the shelves above. */}
      {franchises.results.length >= MIN_VISIBLE_SHELF && (
        <section className="section">
          <div className="section-heading">
            <div className={styles.shelfHeading}>
              <h2>{t("nav.franchises")}</h2>
              <p>{t("franchise.subtitle")}</p>
            </div>
            <Link href="/franchises">{t("home.showAll")}</Link>
          </div>
          <RailScroller railClassName={styles.franchiseRail}>
            {franchises.results.map((franchise) => (
              <FranchiseCard
                item={franchise}
                key={franchise.slug}
                countLabel={t("franchise.titlesCount", { count: franchise.title_count })}
                yearsLabel={
                  franchise.year_from
                    ? franchise.year_to && franchise.year_to !== franchise.year_from
                      ? `${franchise.year_from}–${franchise.year_to}`
                      : franchise.year_to === franchise.year_from
                        ? String(franchise.year_from)
                        : t("title.yearsOngoing", { year: franchise.year_from })
                    : ""
                }
              />
            ))}
          </RailScroller>
        </section>
      )}

      {newestShelfItems.length >= MIN_VISIBLE_SHELF && <CatalogShelf
        title={t("home.newest")}
        subtitle={t("home.newestText")}
        items={newestShelfItems}
        href="/catalog"
        linkLabel={t("home.showAll")}
        emptyLabel={t("home.sectionEmpty")}
      />}
    </div>
  </PageShell>;
}
