"use client";

import Link from "next/link";
import { useI18n } from "../../../components/i18n-provider";

export default function CatalogDetailError({ reset }: { reset: () => void }) {
  const { t } = useI18n();
  return <main className="shell"><section className="content"><div className="state-panel" role="alert"><h1>{t("common.error")}</h1><button className="primary" onClick={reset}>{t("common.retry")}</button><Link className="secondary" href="/catalog">{t("catalog.title")}</Link></div></section></main>;
}
