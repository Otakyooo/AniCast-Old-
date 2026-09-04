"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  createNotificationChallenge,
  disconnectNotificationChannel,
  getDeliveries,
  getNotificationChannel,
  getSubscriptions,
  setScheduleDigest,
  unsubscribeFromTitle,
  type DeliveryItem,
  type SubscriptionItem,
} from "../lib/notifications";
import { titleWatchHref } from "../lib/seo";
import styles from "../app/notifications.module.css";
import { useI18n } from "./i18n-provider";

function formatDay(value: string | null) {
  if (!value) return "";
  const day = new Date(value);
  return Number.isNaN(day.getTime()) ? "" : day.toLocaleDateString();
}

export function NotificationPanel({ botUsername }: { botUsername?: string }) {
  const { t } = useI18n();
  const [connected, setConnected] = useState<boolean>();
  const [digestEnabled, setDigestEnabled] = useState<boolean>(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>();
  const [deliveries, setDeliveries] = useState<DeliveryItem[]>();
  useEffect(() => {
    getNotificationChannel().then(value => {
      setConnected(value.connected);
      if (value.channel) setDigestEnabled(value.channel.schedule_digest_enabled);
    }).catch(() => setConnected(false));
    getSubscriptions().then(value => setSubscriptions(value.results)).catch(() => setSubscriptions([]));
    getDeliveries().then(value => setDeliveries(value.results)).catch(() => setDeliveries([]));
  }, []);
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
  async function unsubscribe(slug: string) {
    setPending(true); setError("");
    try {
      await unsubscribeFromTitle(slug);
      setSubscriptions(current => (current ?? []).filter(item => item.title.slug !== slug));
    } catch (reason) { setError(reason instanceof Error ? reason.message : t("common.error")); } finally { setPending(false); }
  }
  async function toggleDigest() {
    const next = !digestEnabled;
    setPending(true); setError("");
    try {
      await setScheduleDigest(next);
      setDigestEnabled(next);
    } catch (reason) { setError(reason instanceof Error ? reason.message : t("common.error")); } finally { setPending(false); }
  }
  if (!botUsername) return null;
  return (
    <section id="notifications" className={styles.panel}>
      <h3>{t("notifications.title")}</h3>
      <p>{connected ? t("notifications.connected", { bot: botUsername }) : t("notifications.description")}</p>
      <button type="button" disabled={pending || connected === undefined} onClick={connected ? disconnect : connect}>{pending ? t("notifications.pending") : connected ? t("notifications.disconnect") : t("notifications.connect")}</button>
      {error && <span role="alert">{error}</span>}
      {connected && (
        <div className={styles.section}>
          <h4>{t("notifications.digestTitle")}</h4>
          <p className="muted">{t("notifications.digestDescription")}</p>
          <button type="button" disabled={pending} onClick={toggleDigest}>{digestEnabled ? t("notifications.digestOn") : t("notifications.digestOff")}</button>
        </div>
      )}
      {subscriptions !== undefined && subscriptions.length > 0 && !connected && (
        <p className={styles.warning}>{t("notifications.notLinkedWarning")}</p>
      )}
      {subscriptions !== undefined && subscriptions.length > 0 && (
        <div className={styles.section}>
          <h4>{t("notifications.subscriptionsTitle")}</h4>
          <ul className={styles.list}>
            {subscriptions.map(item => (
              <li key={item.title.slug} className={styles.listItem}>
                <Link href={`/titles/${item.title.slug}/`}>{item.title.name}</Link>
                <button type="button" disabled={pending} onClick={() => unsubscribe(item.title.slug)}>{t("notifications.unsubscribe")}</button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {subscriptions !== undefined && subscriptions.length === 0 && (
        <p>{t("notifications.subscriptionsEmpty")}</p>
      )}
      {deliveries !== undefined && deliveries.length > 0 && (
        <div className={styles.section}>
          <h4>{t("notifications.deliveriesTitle")}</h4>
          <ul className={styles.list}>
            {deliveries.map(item => (
              <li key={`${item.title.slug}-${item.episode_number}`} className={styles.listItem}>
                <Link href={titleWatchHref(item.title.slug, item.episode_number)}>{item.title.name}</Link>
                <span>
                  {t("notifications.deliveryEpisode", { number: item.episode_number })} · {t(`notifications.status.${item.status}`)} · {formatDay(item.sent_at ?? item.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
