import { AccountLink } from "../../components/account-link";
import { NotesView } from "../../components/notes-view";
import { Sidebar } from "../../components/sidebar";
import { getI18n } from "../../i18n/server";

export default async function NotesPage() {
  const { t } = await getI18n();
  return <main className="shell"><Sidebar active="library" /><section className="content"><header className="topbar"><span className="eyebrow">{t("library.eyebrow")}</span><AccountLink /></header><div className="page-heading"><h1>{t("notes.title")}</h1><p className="muted">{t("notes.subtitle")}</p></div><NotesView /></section></main>;
}
