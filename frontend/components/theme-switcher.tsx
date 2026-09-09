"use client";

import { useSyncExternalStore } from "react";
import { useI18n } from "./i18n-provider";
import type { ThemePreference } from "../lib/theme";
import styles from "./theme-switcher.module.css";

function subscribe(sync: () => void) {
  window.addEventListener("anicast-theme-applied", sync);
  return () => window.removeEventListener("anicast-theme-applied", sync);
}
const snapshot = (): ThemePreference => document.documentElement.dataset.themePreference === "light" ? "light" : "dark";
const serverSnapshot = (): ThemePreference => "dark";

export function ThemeSwitcher() {
  const { locale } = useI18n();
  const preference = useSyncExternalStore(subscribe, snapshot, serverSnapshot);
  const ru = locale === "ru";
  return <label className={styles.control}>
    <span className={styles.label}>{ru ? "Тема" : "Theme"}</span>
    <select aria-label={ru ? "Тема оформления" : "Color theme"} value={preference}
      onChange={event => window.dispatchEvent(new CustomEvent("anicast-theme-change", { detail: event.target.value }))}>
      <option value="light">{ru ? "Светлая" : "Light"}</option>
      <option value="dark">{ru ? "Тёмная" : "Dark"}</option>
    </select>
  </label>;
}
