import { getI18n } from "../i18n/server";

// Rendered instead of a 500 when the API is briefly unreachable: the
// incident itself is caught by the external site-availability probe, so
// these pages do not need to scream.
export async function ApiUnavailableState() {
  const { t } = await getI18n();
  return (
    <main className="shell"><section className="content"><div className="state-panel" role="status"><h1>{t("common.apiUnavailable")}</h1><p className="muted">{t("common.apiUnavailableText")}</p></div></section></main>
  );
}
