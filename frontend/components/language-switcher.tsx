"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import styles from "../app/language.module.css";

export function LanguageSwitcher() {
  const router = useRouter();
  const [language, setLanguage] = useState("ru");
  useEffect(() => {
    setLanguage(document.cookie.match(/(?:^|; )anicast_lang=([^;]+)/)?.[1] ?? "ru");
  }, []);
  function select(value: "ru" | "en") {
    document.cookie = `anicast_lang=${value}; Path=/; Max-Age=31536000; SameSite=Lax; Secure`;
    setLanguage(value);
    router.refresh();
  }
  return <div className={styles.switcher} aria-label="Язык контента"><button className={language === "ru" ? styles.active : undefined} type="button" onClick={() => select("ru")}>RU</button><button className={language === "en" ? styles.active : undefined} type="button" onClick={() => select("en")}>EN</button></div>;
}
