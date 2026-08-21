"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { register, setLanguageCookie, signIn } from "../lib/auth";
import styles from "../app/auth.module.css";
import { useI18n } from "./i18n-provider";

export function AuthForm({ mode, returnTo = "/account" }: { mode: "login" | "register"; returnTo?: string }) {
  const router = useRouter();
  const { t } = useI18n();
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
      const user = await (isRegister ? register(payload) : signIn(payload));
      if (user) setLanguageCookie(user.preferred_language);
      router.replace(returnTo);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("common.error"));
    } finally {
      setPending(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      {isRegister && <label><span>{t("auth.displayName")}</span><input name="display_name" autoComplete="name" maxLength={80} /></label>}
      <label><span>Email</span><input name="email" type="email" autoComplete="email" required /></label>
      <label><span>{t("auth.password")}</span><input name="password" type="password" autoComplete={isRegister ? "new-password" : "current-password"} minLength={10} required /></label>
      {isRegister && <p className={styles.hint}>{t("auth.passwordHint")}</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      <button className={styles.submit} type="submit" disabled={pending}>{pending ? t("auth.wait") : isRegister ? t("auth.create") : t("common.login")}</button>
      <p className={styles.switch}>{isRegister ? t("auth.haveAccount") : t("auth.new")} <Link href={isRegister ? "/login" : "/register"}>{isRegister ? t("common.login") : t("auth.create")}</Link></p>
    </form>
  );
}
