"use client";

import Link from "next/link";
import { useI18n } from "../components/i18n-provider";

export default function GlobalError({ reset }: { reset: () => void }) {
  const { t } = useI18n();
  return (
    <main className="shell">
      <section className="content">
        <div className="state-panel" role="alert">
          <h1>{t("common.error")}</h1>
          <p className="muted">{t("common.apiUnavailableText")}</p>
          <button className="primary inline-button" type="button" onClick={reset}>{t("common.retry")}</button>
          <Link className="secondary" href="/">{t("account.home")}</Link>
        </div>
      </section>
    </main>
  );
}
