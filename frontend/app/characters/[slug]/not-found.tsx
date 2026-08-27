import type { Metadata } from "next";
import { NotFoundState } from "../../../components/not-found-state";
import { getI18n } from "../../../i18n/server";

export const metadata: Metadata = { title: "404 — AniCast" };

export default async function CharacterNotFound() {
  const { t } = await getI18n();
  return (
    <NotFoundState
      title={t("character.notFound")}
      text={t("character.notFoundText")}
      imageAlt={t("notFound.mascotAlt")}
      actions={[
        { href: "/characters", label: t("notFound.toCharacters"), primary: true },
        { href: "/catalog", label: t("catalog.title") },
      ]}
    />
  );
}
