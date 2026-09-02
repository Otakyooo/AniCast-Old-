import type { Metadata } from "next";
import { NotFoundState } from "../../../components/not-found-state";
import { getI18n } from "../../../i18n/server";

// `absolute` bypasses the root title template; a plain string would be wrapped
// into "404 — AniCast — AniCast".
export const metadata: Metadata = { title: { absolute: "404 — AniCast" } };

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
