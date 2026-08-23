import { PageShell } from "../../../../components/page-shell";
import { PublicCollection } from "../../../../components/public-collection";
import { getI18n } from "../../../../i18n/server";

export default async function PublicCollectionPage({ params }: { params: Promise<{ ownerPublicId: string; slug: string }> }) {
  const { ownerPublicId, slug } = await params;
  const { t } = await getI18n();
  return <PageShell active="collections" back={{ href: "/collections", label: t("collections.title") }}>
    <PublicCollection ownerPublicId={ownerPublicId} slug={slug} />
  </PageShell>;
}
