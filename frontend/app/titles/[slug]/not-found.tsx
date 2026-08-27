import type { Metadata } from "next";
import { NotFoundState } from "../../../components/not-found-state";
import { getI18n } from "../../../i18n/server";

export const metadata: Metadata = { title: "404 — AniCast" };

export default async function TitleNotFound() {
  const { t } = await getI18n();
  return (
    <NotFoundState
      title={t("title.notFound")}
      text={t("title.notFoundText")}
      imageAlt={t("notFound.mascotAlt")}
      actions={[
        { href: "/catalog", label: t("catalog.title"), primary: true },
        { href: "/", label: t("account.home") },
      ]}
    />
  );
}
