import { BrandLockup } from "../../components/brand-lockup";
import { VerifyEmailPanel } from "../../components/verify-email-panel";
import styles from "../auth.module.css";
import { getI18n } from "../../i18n/server";

function tokenFrom(value: string | string[] | undefined) {
  return (Array.isArray(value) ? value[0] : value) ?? "";
}

export default async function VerifyEmailPage({ searchParams }: { searchParams: Promise<{ token?: string | string[] }> }) {
  const { t } = await getI18n();
  const token = tokenFrom((await searchParams).token);
  return <main className={styles.page}><section className={styles.card}><BrandLockup className={styles.brand} priority /><h1>{t("auth.verifyTitle")}</h1><VerifyEmailPanel token={token} /></section></main>;
}
