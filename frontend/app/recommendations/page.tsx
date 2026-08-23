import { PageShell } from "../../components/page-shell";
import { RecommendationsView } from "../../components/recommendations-view";
import { getI18n } from "../../i18n/server";

export default async function RecommendationsPage() {
  const { t } = await getI18n();
  return <PageShell active="library" heading={{ eyebrow: t("nav.library"), title: t("recommendations.title"), subtitle: t("recommendations.subtitle") }}>
    <RecommendationsView />
  </PageShell>;
}
