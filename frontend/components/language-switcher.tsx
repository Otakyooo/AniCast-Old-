"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import styles from "../app/language.module.css";
import { useI18n } from "./i18n-provider";
import { setLanguageCookie, setPreferredLanguage } from "../lib/auth";

export function LanguageSwitcher() {
  const router = useRouter();
  const { t } = useI18n();
  const [language, setLanguage] = useState("ru");
  useEffect(() => {
    setLanguage(document.cookie.match(/(?:^|; )anicast_lang=([^;]+)/)?.[1] ?? "ru");
  }, []);
  function select(value: "ru" | "en") {
    setLanguageCookie(value);
    setLanguage(value);
    setPreferredLanguage(value).catch(() => undefined);
    router.refresh();
  }
  return <div className={`language-switcher ${styles.switcher}`} aria-label={t("language.label")}><button className={language === "ru" ? styles.active : undefined} type="button" onClick={() => select("ru")}>RU</button><button className={language === "en" ? styles.active : undefined} type="button" onClick={() => select("en")}>EN</button></div>;
}
