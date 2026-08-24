import { AccountPanel } from "../../components/account-panel";
import { PageShell } from "../../components/page-shell";
import { ProfileShell } from "../../components/profile-shell";

export default async function AccountPage() {
  return <PageShell active="profile">
    <ProfileShell tab="overview">
      <AccountPanel />
    </ProfileShell>
  </PageShell>;
}
