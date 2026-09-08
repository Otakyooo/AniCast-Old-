"use client";

import { useEffect, useState } from "react";
import { useI18n } from "./i18n-provider";
import type { ThemePreference } from "../lib/theme";
import styles from "./theme-switcher.module.css";

export function ThemeSwitcher() {
  const { locale } = useI18n();
  const [preference, setPreference] = useState<ThemePreference>("system");
  useEffect(() => {
    const sync = () => setPreference((document.documentElement.dataset.themePreference ?? "system") as ThemePreference);
    sync();
    window.addEventListener("anicast-theme-applied", sync);
    return () => window.removeEventListener("anicast-theme-applied", sync);
  }, []);
  const ru = locale === "ru";
  return <label className={styles.control}>
    <span className={styles.label}>{ru ? "Тема" : "Theme"}</span>
    <select aria-label={ru ? "Тема оформления" : "Color theme"} value={preference}
      onChange={event => window.dispatchEvent(new CustomEvent("anicast-theme-change", { detail: event.target.value }))}>
      <option value="system">{ru ? "Системная" : "System"}</option>
      <option value="light">{ru ? "Светлая" : "Light"}</option>
      <option value="dark">{ru ? "Тёмная" : "Dark"}</option>
    </select>
  </label>;
}
