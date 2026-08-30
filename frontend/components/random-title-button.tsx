"use client";

import { useRouter } from "next/navigation";
import { DiceFive } from "@phosphor-icons/react";
import type { MouseEvent } from "react";
import { useI18n } from "./i18n-provider";
import styles from "../app/catalog/catalog.module.css";

/**
 * "Random title" dice: jumps to a random page of the catalog grid. The server
 * already knows the total count, so no extra request is needed — the page the
 * dice lands on does the actual picking.
 */
export function RandomTitleButton({ count }: { count: number }) {
  const { t } = useI18n();
  const router = useRouter();

  const roll = (event: MouseEvent<HTMLButtonElement>) => {
    const pages = Math.max(1, Math.ceil(count / 20));
    const page = 1 + Math.floor(Math.random() * pages);
    event.currentTarget.blur();
    router.push(page > 1 ? `/catalog?page=${page}` : "/catalog");
  };

  return (
    <button
      className={styles.randomButton}
      type="button"
      onClick={roll}
      disabled={count < 1}
      title={t("catalog.random")}
    >
      <DiceFive aria-hidden="true" size={20} weight="bold" />
      <span>{t("catalog.random")}</span>
    </button>
  );
}
