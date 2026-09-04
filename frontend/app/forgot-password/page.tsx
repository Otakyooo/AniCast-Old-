import { BrandLockup } from "../../components/brand-lockup";
import { ForgotPasswordForm } from "../../components/forgot-password-form";
import styles from "../auth.module.css";
import { getI18n } from "../../i18n/server";

export default async function ForgotPasswordPage() {
  const { t } = await getI18n();
  return <main className={styles.page}><section className={styles.card}><BrandLockup className={styles.brand} priority /><h1>{t("auth.forgotTitle")}</h1><p className={styles.intro}>{t("auth.forgotText")}</p><ForgotPasswordForm /></section></main>;
}
