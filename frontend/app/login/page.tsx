import { AuthForm } from "../../components/auth-form";
import { TelegramLogin } from "../../components/telegram-login";
import { BrandLockup } from "../../components/brand-lockup";
import styles from "../auth.module.css";
import { getI18n } from "../../i18n/server";

function safeReturnTo(value: string | string[] | undefined) {
  const candidate = Array.isArray(value) ? value[0] : value;
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//")) return "/account";
  let decoded = candidate;
  try {
    decoded = decodeURIComponent(candidate);
  } catch {
    return "/account";
  }
  if (decoded.includes("\\") || decoded.includes("//") || decoded.startsWith("/%")) return "/account";
  if (!/^\/[A-Za-z0-9/_.-]*(\?[A-Za-z0-9/_.\-=&%+;:@$,!*']*)?$/.test(candidate)) return "/account";
  return candidate;
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
  const returnTo = safeReturnTo((await searchParams).next);
  const { t } = await getI18n();
  return <main className={styles.page}><section className={styles.card}><BrandLockup className={styles.brand} priority /><h1>{t("auth.loginTitle")}</h1><p className={styles.intro}>{t("auth.loginText")}</p><AuthForm mode="login" returnTo={returnTo} /><div className={styles.divider}><span>{t("auth.or")}</span></div><TelegramLogin botUsername={botUsername} returnTo={returnTo} /></section></main>;
}
