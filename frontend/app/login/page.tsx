import Link from "next/link";
import { AuthForm } from "../../components/auth-form";
import { TelegramLogin } from "../../components/telegram-login";
import styles from "../auth.module.css";
import { getI18n } from "../../i18n/server";

function safeReturnTo(value: string | string[] | undefined) {
  const candidate = Array.isArray(value) ? value[0] : value;
  return candidate?.startsWith("/") && !candidate.startsWith("//") ? candidate : "/account";
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
  const returnTo = safeReturnTo((await searchParams).next);
  const { t } = await getI18n();
  return <main className={styles.page}><section className={styles.card}><Link className={styles.brand} href="/">Ani<span>Cast</span></Link><h1>{t("auth.loginTitle")}</h1><p className={styles.intro}>{t("auth.loginText")}</p><AuthForm mode="login" returnTo={returnTo} /><div className={styles.divider}><span>{t("auth.or")}</span></div><TelegramLogin botUsername={botUsername} returnTo={returnTo} /></section></main>;
}
