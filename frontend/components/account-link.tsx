"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSessionUser } from "../lib/auth";
import { LanguageSwitcher } from "./language-switcher";
import styles from "../app/language.module.css";
import { useI18n } from "./i18n-provider";

export function AccountLink() {
  const [authenticated, setAuthenticated] = useState(false);
  const { t } = useI18n();

  useEffect(() => {
    getSessionUser().then((user) => setAuthenticated(Boolean(user))).catch(() => undefined);
  }, []);

  return <div className={`account-actions ${styles.actions}`}><LanguageSwitcher /><Link className="profile" href={authenticated ? "/account" : "/login"}>{authenticated ? t("common.account") : t("common.login")}</Link></div>;
}
