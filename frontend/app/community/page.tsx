import { AccountLink } from "../../components/account-link";
import { Sidebar } from "../../components/sidebar";
import { CommunityFeed } from "../../components/community-feed";
import { getI18n } from "../../i18n/server";

export default async function CommunityPage(){const{t}=await getI18n();return <main className="shell"><Sidebar active="community"/><section className="content"><header className="topbar"><span className="eyebrow">{t("nav.community")}</span><AccountLink/></header><div className="page-heading"><h1>{t("community.title")}</h1><p className="muted">{t("community.subtitle")}</p></div><CommunityFeed/></section></main>}
