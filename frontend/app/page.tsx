import Link from "next/link";
import type { Metadata } from "next";
import { CatalogCard } from "../components/catalog-card";
import { ContinueWatchingBlock } from "../components/continue-watching-block";
import { ScheduleStrip } from "../components/schedule-strip";
import { PageShell } from "../components/page-shell";
import { emptyPage, getCatalog, getSchedule, type CatalogItem, type ScheduleResponse } from "../lib/api";
import { addDays, localDayKey } from "../lib/schedule";
import { getI18n } from "../i18n/server";
import { websiteJsonLd } from "../lib/seo";
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
        <div className="catalog-shelf">{items.map((item) => <CatalogCard item={item} key={item.slug} />)}</div>
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

  return <PageShell active="home">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd(locale)) }} />
    <ContinueWatchingBlock catalogCount={popular.count} />

    {schedule.results.length > 0 && (
      <section className="section">
        <div className="section-heading">
          <div className={styles.shelfHeading}>
            <h2>{t("schedule.title")}</h2>
            <p>{t("schedule.subtitle")}</p>
          </div>
          <Link href="/schedule">{t("home.showAll")}</Link>
        </div>
        <ScheduleStrip items={schedule.results} serverTodayKey={todayKey} />
      </section>
    )}

    <CatalogShelf
      title={t("home.airingNow")}
      subtitle={t("home.airingNowText")}
      items={ongoing.results}
      href="/catalog?status=ongoing"
      linkLabel={t("home.showAll")}
      emptyLabel={t("home.sectionEmpty")}
    />

    <CatalogShelf
      title={t("home.popular")}
      subtitle={t("home.popularText")}
      items={popular.results}
      href="/catalog"
      linkLabel={t("home.allCatalog")}
      emptyLabel={t("home.empty")}
    />

    <CatalogShelf
      title={t("home.newest")}
      subtitle={t("home.newestText")}
      items={newest.results}
      href="/catalog"
      linkLabel={t("home.allCatalog")}
      emptyLabel={t("home.sectionEmpty")}
    />
  </PageShell>;
}
