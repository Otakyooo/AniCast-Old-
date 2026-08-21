import { AccountLink } from "../../components/account-link";
import { NotesView } from "../../components/notes-view";
import { Sidebar } from "../../components/sidebar";

export default function NotesPage() {
  return <main className="shell"><Sidebar active="library" /><section className="content"><header className="topbar"><span className="eyebrow">ЛИЧНОЕ ПРОСТРАНСТВО</span><AccountLink /></header><div className="page-heading"><h1>Заметки</h1><p className="muted">Ваш личный контекст к тайтлам.</p></div><NotesView /></section></main>;
}
