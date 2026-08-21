"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getTitleSubscription, subscribeToTitle, unsubscribeFromTitle } from "../lib/notifications";
import styles from "../app/notifications.module.css";
import { useI18n } from "./i18n-provider";

export function NotificationSubscription({ slug }: { slug: string }) {
  const { t } = useI18n();
  const [subscribed, setSubscribed] = useState<boolean>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { getTitleSubscription(slug).then(setSubscribed).catch(() => setGuest(true)); }, [slug]);
  async function toggle() { setPending(true); setError(""); try { if (subscribed) await unsubscribeFromTitle(slug); else await subscribeToTitle(slug); setSubscribed(!subscribed); } catch { setError(t("common.error")); } finally { setPending(false); } }
  if (guest) return <div className={styles.subscription}><Link href="/login">{t("common.login")}</Link>: {t("notifications.guest")}</div>;
  return <div className={styles.subscription}><button type="button" disabled={pending || subscribed === undefined} onClick={toggle}>{subscribed ? t("notifications.subscribed") : t("notifications.subscribe")}</button>{error && <span>{error}</span>}</div>;
}
