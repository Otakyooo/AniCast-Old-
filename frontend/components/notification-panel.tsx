"use client";

import { useEffect, useState } from "react";
import { createNotificationChallenge, disconnectNotificationChannel, getNotificationChannel } from "../lib/notifications";
import styles from "../app/notifications.module.css";
import { useI18n } from "./i18n-provider";

export function NotificationPanel({ botUsername }: { botUsername?: string }) {
  const { t } = useI18n();
  const [connected, setConnected] = useState<boolean>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { getNotificationChannel().then(value => setConnected(value.connected)).catch(() => setConnected(false)); }, []);
  async function connect() {
    const popup = window.open("about:blank", "anicast-push-bot", "popup,width=520,height=720");
    if (popup) popup.opener = null;
    setPending(true); setError("");
    try {
      const challenge = await createNotificationChallenge();
      if (popup) popup.location.href = challenge.bot_url;
      const deadline = Date.now() + challenge.expires_in * 1000;
      while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        if ((await getNotificationChannel()).connected) { setConnected(true); setPending(false); return; }
      }
      throw new Error(t("common.error"));
    } catch (reason) { popup?.close(); setError(reason instanceof Error ? reason.message : t("common.error")); setPending(false); }
  }
  async function disconnect() { setPending(true); try { await disconnectNotificationChannel(); setConnected(false); } catch (reason) { setError(reason instanceof Error ? reason.message : t("common.error")); } finally { setPending(false); } }
  if (!botUsername) return null;
  return <section className={styles.panel}><h3>{t("notifications.title")}</h3><p>{connected ? t("notifications.connected", { bot: botUsername }) : t("notifications.description")}</p><button type="button" disabled={pending || connected === undefined} onClick={connected ? disconnect : connect}>{pending ? t("notifications.pending") : connected ? t("notifications.disconnect") : t("notifications.connect")}</button>{error && <span>{error}</span>}</section>;
}
