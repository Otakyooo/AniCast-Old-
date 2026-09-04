import Link from "next/link";
import type { Metadata } from "next";
import { CatalogCard } from "../components/catalog-card";
import { ContinueWatchingBlock } from "../components/continue-watching-block";
import { ScheduleStrip } from "../components/schedule-strip";
import { PageShell } from "../components/page-shell";
import { emptyPage, getCatalog, getSchedule, type CatalogItem, type ScheduleResponse } from "../lib/api";
import { addDays, localDayKey } from "../lib/schedule";
import { dedupeShelf } from "../lib/home-shelves";
import { getI18n } from "../i18n/server";
import { jsonLdScript, websiteJsonLd } from "../lib/seo";
import styles from "./home.module.css";

export const dynamic = "force-dynamic";

const SHELF_SIZE = 12;

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
        <div className={styles.posterRail}>{items.map((item) => <CatalogCard item={item} key={item.slug} variant="media" />)}</div>
      ) : (
        <div className="empty-state" role="status"><strong>{emptyLabel}</strong></div>
      )}
    </section>
  );
}

export default async function HomePage() {
  const todayKey = localDayKey(new Date());
  // Every block degrades to an empty shelf instead of a 500 when the API is
  // briefly unreachable, which also keeps the container healthcheck independent
  // from the Caddy -> API chain during cold starts.
  const [ongoing, popular, newest, schedule, { locale, t }] = await Promise.all([
    getCatalog({ status: "ongoing", ordering: "popular", pageSize: SHELF_SIZE }).catch(() => emptyPage<CatalogItem>()),
    getCatalog({ ordering: "popular", pageSize: SHELF_SIZE }).catch(() => emptyPage<CatalogItem>()),
    getCatalog({ ordering: "recent", pageSize: SHELF_SIZE }).catch(() => emptyPage<CatalogItem>()),
    getSchedule(todayKey, addDays(todayKey, 2)).catch((): ScheduleResponse => emptyPage()),
    getI18n(),
  ]);
  const hasDenseAiringShelf = ongoing.results.length >= 4;
  const leadShelfItems = hasDenseAiringShelf ? ongoing.results : popular.results;
  // The shelves are filled from independent queries, so the same title can be
  // "ongoing" and "popular" at once. A repeated card on one screen reads as a
  // data bug, so each follower shelf drops what an earlier shelf already took.
  const popularShelfItems = dedupeShelf(leadShelfItems, popular.results);
  const newestShelfItems = dedupeShelf([...leadShelfItems, ...popularShelfItems], newest.results);

  return <PageShell active="home">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(websiteJsonLd(locale)) }} />
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

      <CatalogShelf
        title={t("home.newest")}
        subtitle={t("home.newestText")}
        items={newestShelfItems}
        href="/catalog"
        linkLabel={t("home.showAll")}
        emptyLabel={t("home.sectionEmpty")}
      />
    </div>
  </PageShell>;
}
