export const locales = ["ru", "en"] as const;
export type Locale = typeof locales[number];
export const defaultLocale: Locale = "ru";
export const intlLocale: Record<Locale, string> = { ru: "ru-RU", en: "en-US" };
export function isLocale(value: unknown): value is Locale { return typeof value === "string" && locales.includes(value as Locale); }
