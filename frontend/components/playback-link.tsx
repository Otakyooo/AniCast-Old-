"use client";

import { useState } from "react";
import { getPlayback } from "../lib/api";
import { useI18n } from "./i18n-provider";

export function PlaybackLink({ sourceId }: { sourceId: number }) {
  const { t } = useI18n();
  const [error, setError] = useState("");
  async function open() {
    const popup = window.open("about:blank", "_blank");
    if (popup) popup.opener = null;
    setError("");
    try {
      const payload = await getPlayback(sourceId);
      const target = new URL(payload.url, window.location.origin);
      if (payload.mode !== "external_link" || target.origin !== window.location.origin) throw new Error("Unsafe playback response");
      if (popup) popup.location.href = target.href;
    } catch {
      popup?.close();
      setError(t("source.gone"));
    }
  }
  return <><button className="primary inline-button" type="button" onClick={open}>{t("source.open")}</button>{error && <small>{error}</small>}</>;
}
