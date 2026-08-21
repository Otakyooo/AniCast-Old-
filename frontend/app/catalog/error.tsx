"use client";
import { useI18n } from "../../components/i18n-provider";

export default function CatalogError({ reset }: { reset: () => void }) {
  const { t } = useI18n();
  return <main className="shell"><section className="content"><div className="state-panel" role="alert"><h1>{t("common.error")}</h1><button className="primary" onClick={reset}>{t("common.retry")}</button></div></section></main>;
}
