import type { Metadata } from "next";
import { NotFoundState } from "../components/not-found-state";
import { getI18n } from "../i18n/server";

// `absolute` bypasses the root title template; a plain string would be wrapped
// into "404 — Anicast — Anicast".
export const metadata: Metadata = { title: { absolute: "404 — Anicast" } };

export default async function NotFound() {
  const { t } = await getI18n();
  return (
    <NotFoundState
      title={t("notFound.title")}
      text={t("notFound.text")}
      imageAlt={t("notFound.mascotAlt")}
      actions={[
        { href: "/", label: t("account.home"), primary: true },
        { href: "/catalog", label: t("catalog.title") },
        { href: "/characters", label: t("notFound.toCharacters") },
      ]}
    />
  );
}
