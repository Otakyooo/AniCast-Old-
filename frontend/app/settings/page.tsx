import { NotificationPanel } from "../../components/notification-panel";
import { PageShell } from "../../components/page-shell";
import { ProfileSettingsPanel } from "../../components/profile-settings-panel";
import { getI18n } from "../../i18n/server";

export default async function SettingsPage() {
  const { t } = await getI18n();
  return <PageShell
    active="profile"
    back={{ href: "/account", label: t("nav.myAccount") }}
    heading={{ title: t("settings.title"), subtitle: t("settings.subtitle") }}
  >
    <ProfileSettingsPanel />
    <NotificationPanel botUsername={process.env.NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME} />
  </PageShell>;
}
