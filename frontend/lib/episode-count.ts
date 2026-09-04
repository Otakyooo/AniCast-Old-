import type { Locale } from "../i18n/config";

const RULES: Record<Locale, Intl.PluralRules> = {
  ru: new Intl.PluralRules("ru"),
  en: new Intl.PluralRules("en"),
};

/**
 * "N episodes" label for shelf cards. English has one plural form; Russian
 * needs the three forms the home dictionaries already ship
 * (`home.shelfMeta.*`), selected by the standard Intl plural category.
 */
export function episodeCountLabel(
  t: (key: string, values?: Record<string, string | number>) => string,
  locale: Locale,
  count: number,
): string {
  const category = RULES[locale].select(count);
  const key = category === "one" ? "home.shelfMeta.episode" : category === "few" ? "home.shelfMeta.few" : "home.shelfMeta.many";
  return t(key, { count });
}
