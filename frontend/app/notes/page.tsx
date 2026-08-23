import { NotesView } from "../../components/notes-view";
import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";

export default async function NotesPage() {
  const { t } = await getI18n();
  return <PageShell active="library" heading={{ eyebrow: t("library.eyebrow"), title: t("notes.title"), subtitle: t("notes.subtitle") }}>
    <NotesView />
  </PageShell>;
}
