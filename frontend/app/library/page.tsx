import { Suspense } from "react";
import { AccountLink } from "../../components/account-link";
import { LibraryView } from "../../components/library-view";
import { Sidebar } from "../../components/sidebar";
import { getI18n } from "../../i18n/server";

export default async function LibraryPage() {
  const { t } = await getI18n();
  return <main className="shell"><Sidebar active="library" /><section className="content"><header className="topbar"><div><span className="eyebrow">{t("library.eyebrow")}</span></div><AccountLink /></header><div className="page-heading"><h1>{t("library.title")}</h1><p className="muted">{t("library.subtitle")}</p></div><Suspense fallback={<div className="empty-state">{t("common.loading")}</div>}><LibraryView /></Suspense></section></main>;
}
