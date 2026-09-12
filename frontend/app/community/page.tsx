import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FollowingFeed } from "../../components/following-feed";
import { PageShell } from "../../components/page-shell";
import { PaginationNav } from "../../components/pagination-nav";
import { ReviewFeed } from "../../components/review-feed";
import { SectionUnavailable } from "../../components/section-unavailable";
import { getI18n } from "../../i18n/server";
import { apiErrorStatus, getPublicReviewsPage } from "../../lib/api";
import { catalogPageExists, communitySeoState, NO_INDEX_ROBOTS } from "../../lib/seo";

export const dynamic = "force-dynamic";

// Mirrors CommunityPagination.page_size on the backend; page math below and
// catalogPageExists both depend on it.
const PAGE_SIZE = 20;

type SearchParams = { page?: string };

function readPage(params: SearchParams) {
  const parsed = Number.parseInt(params.page ?? "1", 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}): Promise<Metadata> {
  const { t } = await getI18n();
  const page = readPage(await searchParams);
  let pageExists = true;
  try {
    const snapshot = await getPublicReviewsPage(page);
    pageExists = catalogPageExists(snapshot.count, page, PAGE_SIZE);
  } catch (error) {
    pageExists = apiErrorStatus(error) !== 404;
  }
  const seo = communitySeoState(page, pageExists);
  return {
    title: t("community.title"),
    description: t("meta.communityDescription"),
    alternates: { canonical: seo.canonical },
    ...(!seo.index ? { robots: NO_INDEX_ROBOTS } : {}),
  };
}

export default async function CommunityPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const { t } = await getI18n();
  const page = readPage(await searchParams);
  // Reviews are fetched on the server: this page is the only crawlable path to
  // public profiles and collections, and it used to render a loading placeholder
  // for anyone without JavaScript. A degraded API falls back to the retryable
  // section state rather than the empty state — "no reviews" must stay honest.
  // DRF answers 404 past the last page, which becomes a real 404.
  const reviews = await getPublicReviewsPage(page).catch((error) => {
    if (apiErrorStatus(error) === 404) notFound();
    return null;
  });
  const pageCount = reviews ? Math.max(1, Math.ceil(reviews.count / PAGE_SIZE)) : 1;
  if (reviews && page > pageCount) notFound();
  const href = (target: number) => (target > 1 ? `/community?page=${target}` : "/community");
  return <PageShell active="community" heading={{ eyebrow: t("nav.community"), title: t("community.title"), subtitle: t("community.subtitle") }}>
    {!reviews ? <SectionUnavailable /> : (
      <FollowingFeed>
        <ReviewFeed reviews={reviews.results} />
        <PaginationNav currentPage={page} pageCount={pageCount} makeHref={href} />
      </FollowingFeed>
    )}
  </PageShell>;
}
