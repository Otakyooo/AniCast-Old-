"use client";

import { useState } from "react";

export function PlaybackLink({ sourceId }: { sourceId: number }) {
  const [error, setError] = useState("");
  async function open() {
    const popup = window.open("about:blank", "_blank");
    if (popup) popup.opener = null;
    setError("");
    const response = await fetch(`/api/v1/sources/${sourceId}/playback/`, { cache: "no-store" });
    if (!response.ok) { popup?.close(); setError("Источник больше недоступен."); return; }
    const payload = await response.json() as { url: string };
    if (popup) popup.location.href = payload.url;
  }
  return <><button className="primary inline-button" type="button" onClick={open}>Открыть у провайдера</button>{error && <small>{error}</small>}</>;
}
