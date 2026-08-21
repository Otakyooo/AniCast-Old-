import Link from "next/link";
import { AuthForm } from "../../components/auth-form";
import { TelegramLogin } from "../../components/telegram-login";
import styles from "../auth.module.css";

function safeReturnTo(value: string | string[] | undefined) {
  const candidate = Array.isArray(value) ? value[0] : value;
  return candidate?.startsWith("/") && !candidate.startsWith("//") ? candidate : "/account";
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
  const returnTo = safeReturnTo((await searchParams).next);
  return <main className={styles.page}><section className={styles.card}><Link className={styles.brand} href="/">Ani<span>Cast</span></Link><h1>С возвращением</h1><p className={styles.intro}>Войдите, чтобы сохранять личное состояние между устройствами.</p><AuthForm mode="login" returnTo={returnTo} /><div className={styles.divider}><span>или</span></div><TelegramLogin botUsername={botUsername} returnTo={returnTo} /></section></main>;
}
