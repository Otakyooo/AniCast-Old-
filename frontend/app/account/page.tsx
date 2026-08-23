import { AccountPanel } from "../../components/account-panel";
import { PageShell } from "../../components/page-shell";

export default async function AccountPage() {
  return <PageShell active="library">
    <div className="profile-shell">
      <AccountPanel notificationBotUsername={process.env.NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME} />
    </div>
  </PageShell>;
}
