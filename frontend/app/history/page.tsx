import { HistoryView } from "../../components/history-view";
import { PageShell } from "../../components/page-shell";
import { ProfileShell } from "../../components/profile-shell";

export default async function HistoryPage() {
  return <PageShell active="profile">
    <ProfileShell tab="history">
      <HistoryView />
    </ProfileShell>
  </PageShell>;
}
