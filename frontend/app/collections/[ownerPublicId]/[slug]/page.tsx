import Link from "next/link";
import { AccountLink } from "../../../../components/account-link";
import { PublicCollection } from "../../../../components/public-collection";
import { Sidebar } from "../../../../components/sidebar";
import { getI18n } from "../../../../i18n/server";

export default async function PublicCollectionPage({ params }: { params: Promise<{ ownerPublicId: string; slug: string }> }) { const { ownerPublicId, slug } = await params; const { t } = await getI18n(); return <main className="shell"><Sidebar active="collections" /><section className="content"><header className="topbar"><Link className="back-link" href="/collections">← {t("collections.title")}</Link><AccountLink /></header><PublicCollection ownerPublicId={ownerPublicId} slug={slug} /></section></main>; }
