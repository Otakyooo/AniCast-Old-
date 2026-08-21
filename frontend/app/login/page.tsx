import Link from "next/link";
import { AuthForm } from "../../components/auth-form";
import { TelegramLogin } from "../../components/telegram-login";
import styles from "../auth.module.css";

export default function LoginPage() {
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
  return <main className={styles.page}><section className={styles.card}><Link className={styles.brand} href="/">Ani<span>Cast</span></Link><h1>С возвращением</h1><p className={styles.intro}>Войдите, чтобы сохранять личное состояние между устройствами.</p><AuthForm mode="login" /><div className={styles.divider}><span>или</span></div><TelegramLogin botUsername={botUsername} /></section></main>;
}
