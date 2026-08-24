import { AccountPanel } from "../../components/account-panel";
import { PageShell } from "../../components/page-shell";
import { getI18n } from "../../i18n/server";

export default async function AccountPage() {
  const { t } = await getI18n();
  return <PageShell
    active="library"
    heading={{ eyebrow: t("account.eyebrow"), title: t("account.title"), subtitle: t("account.subtitle") }}
  >
    <div className="profile-shell">
      <AccountPanel notificationBotUsername={process.env.NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME} />
    </div>
  </PageShell>;
}
