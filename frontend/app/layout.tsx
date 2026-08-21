import type { Metadata } from "next";
import { I18nProvider } from "../components/i18n-provider";
import { getI18n } from "../i18n/server";
import "./globals.css";
import "./shell.css";
import "./shell-overrides.css";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getI18n();
  return { title: "AniCast", description: t("meta.description") };
}

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const { locale, dictionary } = await getI18n();
  return <html lang={locale}><body><I18nProvider locale={locale} dictionary={dictionary}>{children}</I18nProvider></body></html>;
}
