"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CaretDown } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "./i18n-provider";
import styles from "./nav-more-menu.module.css";

/**
 * «Ещё» in primary nav — secondary links (Франшизы / Коллекции / Сообщество)
 * live behind one menu so watching routes stay first-class.
 * A native <details> element keeps keyboard and screen-reader support free.
 */
export function NavMoreMenu() {
  const { t } = useI18n();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [prevPathname, setPrevPathname] = useState(pathname);
  const ref = useRef<HTMLDetailsElement>(null);

  if (prevPathname !== pathname) {
    setPrevPathname(pathname);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  const links = [
    { href: "/franchises", label: t("nav.franchises") },
    { href: "/collections", label: t("nav.collections") },
    { href: "/community", label: t("nav.community") },
  ];

  return (
    <details
      ref={ref}
      className={styles.more}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className={styles.moreTrigger}>
        {t("nav.more")}
        <CaretDown aria-hidden="true" size={13} weight="bold" />
      </summary>
      <div className={styles.moreMenu} role="menu" aria-label={t("nav.more")}>
        {links.map((link) => (
          <Link className={styles.moreItem} href={link.href} key={link.href} role="menuitem">
            {link.label}
          </Link>
        ))}
      </div>
    </details>
  );
}
