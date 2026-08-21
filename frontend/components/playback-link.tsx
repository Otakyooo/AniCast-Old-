"use client";

import { useState } from "react";
import { useI18n } from "./i18n-provider";

export function PlaybackLink({ sourceId }: { sourceId: number }) {
  const { t } = useI18n();
  const [error, setError] = useState("");
  async function open() {
    const popup = window.open("about:blank", "_blank");
    if (popup) popup.opener = null;
    setError("");
    const response = await fetch(`/api/v1/sources/${sourceId}/playback/`, { cache: "no-store" });
    if (!response.ok) { popup?.close(); setError(t("source.gone")); return; }
    const payload = await response.json() as { url: string };
    if (popup) popup.location.href = payload.url;
  }
  return <><button className="primary inline-button" type="button" onClick={open}>{t("source.open")}</button>{error && <small>{error}</small>}</>;
}
