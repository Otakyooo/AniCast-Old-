import { BrandLockup } from "../../components/brand-lockup";
import { ResetPasswordForm } from "../../components/reset-password-form";
import styles from "../auth.module.css";
import { getI18n } from "../../i18n/server";

function tokenFrom(value: string | string[] | undefined) {
  return (Array.isArray(value) ? value[0] : value) ?? "";
}

export default async function ResetPasswordPage({ searchParams }: { searchParams: Promise<{ token?: string | string[] }> }) {
  const { t } = await getI18n();
  const token = tokenFrom((await searchParams).token);
  return <main className={styles.page}><section className={styles.card}><BrandLockup className={styles.brand} priority /><h1>{t("auth.resetTitle")}</h1><p className={styles.intro}>{t("auth.resetText")}</p><ResetPasswordForm token={token} /></section></main>;
}
