import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ApiUnavailableState } from "../../../components/api-unavailable";
import { PageShell } from "../../../components/page-shell";
import { PublicProfile } from "../../../components/public-profile";
import { getI18n } from "../../../i18n/server";
import { getPublicProfileServer, PublicProfileError } from "../../../lib/server-profile";
import { metaDescription } from "../../../lib/site";

type Params = { publicId: string };

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { publicId } = await params;
  const { t } = await getI18n();
  try {
    const data = await getPublicProfileServer(publicId);
    const canonical = `/users/${publicId}`;
    return {
      title: `${data.profile.display_name} — AniCast`,
      description: metaDescription(data.profile.bio, t("social.profileDescription", { name: data.profile.display_name })),
      alternates: { canonical },
      openGraph: { type: "profile", url: canonical, title: data.profile.display_name },
    };
  } catch {
    return { robots: { index: false, follow: false } };
  }
}

export default async function PublicProfilePage({ params }: { params: Promise<Params> }) {
  const { publicId } = await params;
  const { t } = await getI18n();
  let data;
  try {
    data = await getPublicProfileServer(publicId);
  } catch (error) {
    if (error instanceof PublicProfileError && error.status === 404) notFound();
    return <ApiUnavailableState />;
  }
  return <PageShell active="community" back={{ href: "/community", label: t("community.title") }}>
    <PublicProfile data={data} />
  </PageShell>;
}
