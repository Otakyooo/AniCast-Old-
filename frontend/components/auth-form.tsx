"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { register, signIn } from "../lib/auth";
import styles from "../app/auth.module.css";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const isRegister = mode === "register";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const payload = {
        email: String(data.get("email") ?? ""),
        password: String(data.get("password") ?? ""),
        ...(isRegister ? { display_name: String(data.get("display_name") ?? "") } : {}),
      };
      await (isRegister ? register(payload) : signIn(payload));
      router.push("/account");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось выполнить запрос.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      {isRegister && <label><span>Как к вам обращаться</span><input name="display_name" autoComplete="name" maxLength={80} /></label>}
      <label><span>Email</span><input name="email" type="email" autoComplete="email" required /></label>
      <label><span>Пароль</span><input name="password" type="password" autoComplete={isRegister ? "new-password" : "current-password"} minLength={10} required /></label>
      {isRegister && <p className={styles.hint}>Не менее 10 символов. Не используйте распространённый или полностью цифровой пароль.</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      <button className={styles.submit} type="submit" disabled={pending}>{pending ? "Подождите..." : isRegister ? "Создать аккаунт" : "Войти"}</button>
      <p className={styles.switch}>{isRegister ? "Уже есть аккаунт?" : "Впервые в AniCast?"} <Link href={isRegister ? "/login" : "/register"}>{isRegister ? "Войти" : "Создать аккаунт"}</Link></p>
    </form>
  );
}
