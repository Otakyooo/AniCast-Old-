import type { Metadata } from "next";
import { CommunityFeed } from "../../components/community-feed";
import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";

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
  return <PageShell active="community" heading={{ eyebrow: t("nav.community"), title: t("community.title"), subtitle: t("community.subtitle") }}>
    <CommunityFeed />
  </PageShell>;
}
