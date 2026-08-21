"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSessionUser } from "../lib/auth";
import { LanguageSwitcher } from "./language-switcher";
import styles from "../app/language.module.css";

export function AccountLink() {
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    getSessionUser().then((user) => setAuthenticated(Boolean(user))).catch(() => undefined);
  }, []);

  return <div className={styles.actions}><LanguageSwitcher /><Link className="profile" href={authenticated ? "/account" : "/login"}>{authenticated ? "Мой аккаунт" : "Войти"}</Link></div>;
}
