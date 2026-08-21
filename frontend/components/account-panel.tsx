"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getSessionUser, signOut, type SessionUser } from "../lib/auth";
import styles from "../app/auth.module.css";

export function AccountPanel() {
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null | undefined>();
  const [error, setError] = useState("");

  useEffect(() => {
    getSessionUser().then(setUser).catch((reason) => setError(reason instanceof Error ? reason.message : "Не удалось загрузить аккаунт."));
  }, []);

  async function logout() {
    setError("");
    try {
      await signOut();
      router.push("/");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось выйти из аккаунта.");
    }
  }

  if (error) return <div className={styles.accountState} role="alert"><p>{error}</p><Link href="/">На главную</Link></div>;
  if (user === undefined) return <div className={styles.accountState} role="status">Загружаем аккаунт...</div>;
  if (user === null) return <div className={styles.accountState}><h2>Сессия не найдена</h2><p>Войдите, чтобы синхронизировать будущие списки и прогресс.</p><Link className={styles.submit} href="/login">Войти</Link></div>;

  return <div className={styles.accountState}><p className="eyebrow">ВАШ АККАУНТ</p><h2>{user.display_name || "Зритель AniCast"}</h2>{user.email && <p className="muted">{user.email}</p>}<p>Сессия активна. Личная библиотека синхронизируется между устройствами.</p><Link className={styles.submit} href="/library">Открыть библиотеку</Link><button className={styles.secondary} type="button" onClick={logout}>Выйти</button></div>;
}
