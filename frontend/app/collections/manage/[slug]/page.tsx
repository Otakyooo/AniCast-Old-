import Link from "next/link";
import { AccountLink } from "../../../../components/account-link";
import { CollectionEditor } from "../../../../components/collection-editor";
import { Sidebar } from "../../../../components/sidebar";
import { getI18n } from "../../../../i18n/server";

export default async function ManageCollectionPage({ params }: { params: Promise<{ slug: string }> }) { const { slug } = await params; const { t } = await getI18n(); return <main className="shell"><Sidebar active="collections" /><section className="content"><header className="topbar"><Link className="back-link" href="/collections">← {t("collections.title")}</Link><AccountLink /></header><div className="page-heading"><h1>{t("collections.manage")}</h1><p className="muted">{t("collections.manageText")}</p></div><CollectionEditor slug={slug} /></section></main>; }
