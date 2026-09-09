"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import styles from "../app/language.module.css";
import { useI18n } from "./i18n-provider";
import { setLanguageCookie, setPreferredLanguage } from "../lib/auth";

export function LanguageSwitcher() {
  const { locale } = useI18n();
  return <LanguageSelection key={locale} />;
}

function LanguageSelection() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const [language, setLanguage] = useState(locale);
  function select(value: "ru" | "en") {
    setLanguageCookie(value);
    setLanguage(value);
    setPreferredLanguage(value).catch(() => undefined);
    router.refresh();
  }
  return <div className={`language-switcher ${styles.switcher}`} role="group" aria-label={t("language.label")}><button className={language === "ru" ? styles.active : undefined} type="button" aria-pressed={language === "ru"} onClick={() => select("ru")}>RU</button><button className={language === "en" ? styles.active : undefined} type="button" aria-pressed={language === "en"} onClick={() => select("en")}>EN</button></div>;
}
