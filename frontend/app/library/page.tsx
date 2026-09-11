import { Suspense } from "react";
import { LibraryView } from "../../components/library-view";
import { PageShell } from "../../components/page-shell";
import { ProfileShell } from "../../components/profile-shell";
import { getI18n } from "../../i18n/server";

export default async function LibraryPage() {
  const { t } = await getI18n();
  return <PageShell active="library">
    <ProfileShell tab="library">
      <Suspense fallback={<div className="empty-state">{t("common.loading")}</div>}>
        <LibraryView />
      </Suspense>
    </ProfileShell>
  </PageShell>;
}
