import { AccountLink } from "../../components/account-link";
import { CollectionsList } from "../../components/collections-list";
import { Sidebar } from "../../components/sidebar";
import { getI18n } from "../../i18n/server";

export default async function CollectionsPage() { const { t } = await getI18n(); return <main className="shell"><Sidebar active="collections" /><section className="content"><header className="topbar"><span className="eyebrow">{t("collections.eyebrow")}</span><AccountLink /></header><div className="page-heading"><h1>{t("collections.title")}</h1><p className="muted">{t("collections.subtitle")}</p></div><CollectionsList /></section></main>; }
