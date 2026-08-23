import { CollectionsList } from "../../components/collections-list";
import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";

export default async function CollectionsPage() {
  const { t } = await getI18n();
  return <PageShell active="collections" heading={{ eyebrow: t("collections.eyebrow"), title: t("collections.title"), subtitle: t("collections.subtitle") }}>
    <CollectionsList />
  </PageShell>;
}
