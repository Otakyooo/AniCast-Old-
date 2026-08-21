"use client";

import { createContext, useContext } from "react";
import type { Locale } from "../i18n/config";
import { createTranslator } from "../i18n/translate";

type I18nValue = { locale: Locale; t: ReturnType<typeof createTranslator> };
const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ locale, dictionary, children }: { locale: Locale; dictionary: Record<string, string>; children: React.ReactNode }) {
  return <I18nContext.Provider value={{ locale, t: createTranslator(dictionary) }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const value = useContext(I18nContext);
  if (!value) throw new Error("I18nProvider is missing");
  return value;
}
