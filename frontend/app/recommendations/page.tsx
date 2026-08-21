import { AccountLink } from "../../components/account-link";
import { RecommendationsView } from "../../components/recommendations-view";
import { Sidebar } from "../../components/sidebar";
import { getI18n } from "../../i18n/server";

export default async function RecommendationsPage() {
  const { t } = await getI18n();
  return <main className="shell"><Sidebar active="library" /><section className="content"><header className="topbar"><span className="eyebrow">{t("nav.library")}</span><AccountLink /></header><div className="page-heading"><h1>{t("recommendations.title")}</h1><p className="muted">{t("recommendations.subtitle")}</p></div><RecommendationsView /></section></main>;
}
