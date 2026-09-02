import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageShell } from "../../../../components/page-shell";
import { PublicCollection } from "../../../../components/public-collection";
import { ApiUnavailableState } from "../../../../components/api-unavailable";
import { getI18n } from "../../../../i18n/server";
import { getPublicCollectionServer, PublicCollectionError } from "../../../../lib/server-collections";
import { NO_INDEX_ROBOTS } from "../../../../lib/seo";
import { absoluteUrl, metaDescription } from "../../../../lib/site";

type Params = { ownerPublicId: string; slug: string };

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { ownerPublicId, slug } = await params;
  const { t } = await getI18n();
  try {
    const collection = await getPublicCollectionServer(ownerPublicId, slug);
    const description = metaDescription(collection.description, t("collections.subtitle"));
    const canonical = `/collections/${ownerPublicId}/${slug}`;
    const poster = collection.items.find((item) => item.title.poster_url)?.title.poster_url;
    return {
      title: collection.name,
      description,
      alternates: { canonical },
      openGraph: {
        type: "website",
        url: canonical,
        title: collection.name,
        description,
        ...(poster ? { images: [{ url: absoluteUrl(poster), alt: collection.name }] } : {}),
      },
    };
  } catch (error) {
    // The page owns the 404. A degraded API renders the unavailable shell at
    // 200, and that must stay out of the index.
    if (error instanceof PublicCollectionError && error.status === 404) {
      return { title: t("collections.title") };
    }
    return { title: t("collections.title"), robots: NO_INDEX_ROBOTS };
  }
}

export default async function PublicCollectionPage({ params }: { params: Promise<Params> }) {
  const { ownerPublicId, slug } = await params;
  const { t } = await getI18n();
  let collection;
  try {
    collection = await getPublicCollectionServer(ownerPublicId, slug);
  } catch (error) {
    if (error instanceof PublicCollectionError && error.status === 404) notFound();
    return <ApiUnavailableState />;
  }
  return <PageShell active="profile" back={{ href: "/collections", label: t("collections.title") }}>
    <PublicCollection collection={collection} />
  </PageShell>;
}
