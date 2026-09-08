import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import { I18nProvider } from "../components/i18n-provider";
import { SITE_URL } from "../lib/site";
import { getI18n } from "../i18n/server";
import "@fontsource-variable/manrope";
import "./theme.css";
import "./globals.css";
import { THEME_SCRIPT } from "../lib/theme";

export const viewport: Viewport = {
  colorScheme: "dark light",
  themeColor: "#171311",
};

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getI18n();
  return {
    // Anchors relative canonical/OG URLs to the public origin.
    metadataBase: new URL(SITE_URL),
    applicationName: "Anicast",
    title: {
      default: t("meta.homeTitle"),
      template: "%s — Anicast",
    },
    description: t("meta.homeDescription"),
    creator: "Anicast",
    openGraph: {
      type: "website",
      siteName: "Anicast",
      url: SITE_URL,
      images: [{ url: "/og-v02.png", width: 1200, height: 630, alt: "Anicast" }],
    },
    twitter: { card: "summary_large_image" },
  };
}

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const { locale, dictionary } = await getI18n();
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return <html lang={locale} suppressHydrationWarning><head><script nonce={nonce} dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} /></head><body><I18nProvider locale={locale} dictionary={dictionary}>{children}</I18nProvider></body></html>;
}
