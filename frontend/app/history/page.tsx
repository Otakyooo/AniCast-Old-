import { AccountLink } from "../../components/account-link";
import { HistoryView } from "../../components/history-view";
import { Sidebar } from "../../components/sidebar";
import { getI18n } from "../../i18n/server";

export default async function HistoryPage() {
  const { t } = await getI18n();
  return <main className="shell"><Sidebar active="library" /><section className="content"><header className="topbar"><span className="eyebrow">{t("library.eyebrow")}</span><AccountLink /></header><div className="page-heading"><h1>{t("history.title")}</h1><p className="muted">{t("history.subtitle")}</p></div><HistoryView /></section></main>;
}
