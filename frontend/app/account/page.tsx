import { AccountPanel } from "../../components/account-panel";
import { Sidebar } from "../../components/sidebar";

export default function AccountPage() {
  return <main className="shell"><Sidebar active="library" /><section className="content"><div className="profile-shell"><AccountPanel notificationBotUsername={process.env.NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME} /></div></section></main>;
}
