import type { Metadata } from "next";
import { FollowingFeed } from "../../components/following-feed";
import { PageShell } from "../../components/page-shell";
import { ReviewFeed } from "../../components/review-feed";
import { getI18n } from "../../i18n/server";
import { emptyPage, getPublicReviewsPage, type PublicReview } from "../../lib/api";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getI18n();
  return {
    title: t("community.title"),
    description: t("meta.communityDescription"),
    alternates: { canonical: "/community" },
  };
}

export default async function CommunityPage() {
  const { t } = await getI18n();
  // Reviews are fetched on the server: this page is the only crawlable path to
  // public profiles and collections, and it used to render a loading placeholder
  // for anyone without JavaScript. A degraded API falls back to the empty state
  // rather than failing the page — the tab strip below still works.
  const reviews = await getPublicReviewsPage().catch(() => emptyPage<PublicReview>());
  return <PageShell active="community" heading={{ eyebrow: t("nav.community"), title: t("community.title"), subtitle: t("community.subtitle") }}>
    <FollowingFeed>
      <ReviewFeed reviews={reviews.results} />
    </FollowingFeed>
  </PageShell>;
}
