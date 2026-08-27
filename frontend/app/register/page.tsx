import { AuthForm } from "../../components/auth-form";
import { BrandLockup } from "../../components/brand-lockup";
import styles from "../auth.module.css";
import { getI18n } from "../../i18n/server";

export default async function RegisterPage() {
  const { t } = await getI18n();
  return <main className={styles.page}><section className={styles.card}><BrandLockup className={styles.brand} priority /><h1>{t("auth.registerTitle")}</h1><p className={styles.intro}>{t("auth.registerText")}</p><AuthForm mode="register" /></section></main>;
}
