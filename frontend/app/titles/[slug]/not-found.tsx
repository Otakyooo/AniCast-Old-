import type { Metadata } from "next";
import { NotFoundState } from "../../../components/not-found-state";
import { getI18n } from "../../../i18n/server";

// `absolute` bypasses the root title template; a plain string would be wrapped
// into "404 — AniCast — AniCast".
export const metadata: Metadata = { title: { absolute: "404 — AniCast" } };

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
