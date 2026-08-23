import { CollectionEditor } from "../../../../components/collection-editor";
import { PageShell } from "../../../../components/page-shell";
import { getI18n } from "../../../../i18n/server";

export default async function ManageCollectionPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { t } = await getI18n();
  return <PageShell
    active="collections"
    back={{ href: "/collections", label: t("collections.title") }}
    heading={{ title: t("collections.manage"), subtitle: t("collections.manageText") }}
  >
    <CollectionEditor slug={slug} />
  </PageShell>;
}
