import type { Metadata, Viewport } from "next";
import { I18nProvider } from "../components/i18n-provider";
import { SITE_URL } from "../lib/site";
import { getI18n } from "../i18n/server";
import "@fontsource-variable/noto-sans-jp";
import "./globals.css";

export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#0B131C",
};

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getI18n();
  return {
    // Anchors relative canonical/OG URLs to the public origin.
    metadataBase: new URL(SITE_URL),
    applicationName: "AniCast",
    title: {
      default: t("meta.homeTitle"),
      template: "%s — AniCast",
    },
    description: t("meta.homeDescription"),
    creator: "AniCast",
    openGraph: {
      type: "website",
      siteName: "AniCast",
      url: SITE_URL,
      images: [{ url: "/og.png", width: 1200, height: 630, alt: "AniCast" }],
    },
    twitter: { card: "summary_large_image" },
  };
}

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const { locale, dictionary } = await getI18n();
  return <html lang={locale}><body><I18nProvider locale={locale} dictionary={dictionary}>{children}</I18nProvider></body></html>;
}
