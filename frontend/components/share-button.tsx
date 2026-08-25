"use client";

import { useState } from "react";
import { useI18n } from "./i18n-provider";

/**
 * Native share sheet when available, clipboard fallback otherwise, with a
 * short "copied" confirmation for the fallback path.
 */
export function ShareButton({ path, title }: { path: string; title: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  async function share() {
    const url = new URL(path, window.location.origin).href;
    try {
      if (typeof navigator.share === "function") {
        await navigator.share({ title, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // User dismissed the share sheet or clipboard is unavailable: stay quiet.
    }
  }

  return (
    <button className="secondary inline-button" type="button" onClick={share}>
      {copied ? t("title.shareCopied") : t("title.share")}
    </button>
  );
}
