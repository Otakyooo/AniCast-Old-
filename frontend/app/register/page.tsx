import Link from "next/link";
import { AuthForm } from "../../components/auth-form";
import styles from "../auth.module.css";

export default function RegisterPage() {
  return <main className={styles.page}><section className={styles.card}><Link className={styles.brand} href="/">Ani<span>Cast</span></Link><h1>Личное пространство</h1><p className={styles.intro}>Создайте аккаунт для будущей синхронизации прогресса, истории и списков.</p><AuthForm mode="register" /></section></main>;
}
