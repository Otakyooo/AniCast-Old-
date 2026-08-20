import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "AniCast", description: "Wiki, библиотека и просмотр аниме" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ru"><body>{children}</body></html>;
}
