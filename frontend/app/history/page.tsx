import { HistoryView } from "../../components/history-view";
import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";

export default async function HistoryPage() {
  const { t } = await getI18n();
  return <PageShell active="library" heading={{ eyebrow: t("library.eyebrow"), title: t("history.title"), subtitle: t("history.subtitle") }}>
    <HistoryView />
  </PageShell>;
}
