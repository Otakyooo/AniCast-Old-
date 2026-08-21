import { AccountLink } from "../../components/account-link";
import { HistoryView } from "../../components/history-view";
import { Sidebar } from "../../components/sidebar";

export default function HistoryPage() {
  return <main className="shell"><Sidebar active="library" /><section className="content"><header className="topbar"><span className="eyebrow">ЛИЧНОЕ ПРОСТРАНСТВО</span><AccountLink /></header><div className="page-heading"><h1>История</h1><p className="muted">Только действительно открытые эпизоды и ваши явные отметки.</p></div><HistoryView /></section></main>;
}
