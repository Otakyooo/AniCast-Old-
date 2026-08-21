import { Suspense } from "react";
import { AccountLink } from "../../components/account-link";
import { LibraryView } from "../../components/library-view";
import { Sidebar } from "../../components/sidebar";

export default function LibraryPage() {
  return <main className="shell"><Sidebar active="library" /><section className="content"><header className="topbar"><div><span className="eyebrow">ЛИЧНОЕ ПРОСТРАНСТВО</span></div><AccountLink /></header><div className="page-heading"><h1>Моя библиотека</h1><p className="muted">Собирайте тайтлы, отмечайте статус и сохраняйте любимое.</p></div><Suspense fallback={<div className="empty-state">Загружаем библиотеку...</div>}><LibraryView /></Suspense></section></main>;
}
