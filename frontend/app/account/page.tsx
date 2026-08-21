import Link from "next/link";
import { AccountPanel } from "../../components/account-panel";
import styles from "../auth.module.css";

export default function AccountPage() {
  return <main className={styles.page}><section className={styles.card}><Link className={styles.brand} href="/">Ani<span>Cast</span></Link><AccountPanel notificationBotUsername={process.env.NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME} /></section></main>;
}
