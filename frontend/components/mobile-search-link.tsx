"use client";

import Link from "next/link";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { useI18n } from "./i18n-provider";

/** Custom event the header search listens for to expand its sheet. */
export const OPEN_SEARCH_EVENT = "anicast:open-search";

/**
 * Mobile bottom-nav search action (design spec §10.1: Главная, Каталог,
 * Расписание, Поиск, Профиль). Without JavaScript it falls back to the
 * catalog page, which owns a full search field.
 */
export function MobileSearchLink() {
  const { t } = useI18n();
  return (
    <Link
      href="/catalog"
      onClick={(event) => {
        event.preventDefault();
        window.dispatchEvent(new Event(OPEN_SEARCH_EVENT));
      }}
    >
      <MagnifyingGlass aria-hidden="true" size={20} />{t("search.title")}
    </Link>
  );
}
