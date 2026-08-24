import { CollectionEditor } from "../../../../components/collection-editor";
import { PageShell } from "../../../../components/page-shell";
import { ProfileShell } from "../../../../components/profile-shell";
import { getI18n } from "../../../../i18n/server";

export default async function ManageCollectionPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { t } = await getI18n();
  return <PageShell active="profile">
    <ProfileShell tab="library">
      <div className="page-back">
        <a className="back-link" href="/library?view=collections">← {t("collections.title")}</a>
      </div>
      <div className="page-heading">
        <h1>{t("collections.manage")}</h1>
        <p className="muted">{t("collections.manageText")}</p>
      </div>
      <CollectionEditor slug={slug} />
    </ProfileShell>
  </PageShell>;
}
