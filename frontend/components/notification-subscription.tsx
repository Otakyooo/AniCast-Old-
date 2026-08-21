"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getTitleSubscription, subscribeToTitle, unsubscribeFromTitle } from "../lib/notifications";
import styles from "../app/notifications.module.css";

export function NotificationSubscription({ slug }: { slug: string }) {
  const [subscribed, setSubscribed] = useState<boolean>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { getTitleSubscription(slug).then(setSubscribed).catch(() => setGuest(true)); }, [slug]);
  async function toggle() { setPending(true); setError(""); try { if (subscribed) await unsubscribeFromTitle(slug); else await subscribeToTitle(slug); setSubscribed(!subscribed); } catch { setError("Не удалось изменить подписку."); } finally { setPending(false); } }
  if (guest) return <div className={styles.subscription}><Link href="/login">Войдите</Link>, чтобы подписаться на новые эпизоды.</div>;
  return <div className={styles.subscription}><button type="button" disabled={pending || subscribed === undefined} onClick={toggle}>{subscribed ? "Уведомления включены" : "Уведомлять о новых эпизодах"}</button>{error && <span>{error}</span>}</div>;
}
