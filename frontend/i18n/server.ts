import { cookies } from "next/headers";
import { defaultLocale, isLocale } from "./config";
import { dictionaries } from "./dictionaries";
import { createTranslator } from "./translate";

export async function getI18n() {
  const value = (await cookies()).get("anicast_lang")?.value;
  const locale = isLocale(value) ? value : defaultLocale;
  const dictionary = dictionaries[locale];
  return { locale, dictionary, t: createTranslator(dictionary) };
}
