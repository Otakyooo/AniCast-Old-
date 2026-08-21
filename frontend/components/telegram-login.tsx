"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { completeTelegramChallenge, createTelegramChallenge, type TelegramChallenge } from "../lib/auth";
import styles from "../app/auth.module.css";

export function TelegramLogin({ botUsername, returnTo = "/account" }: { botUsername?: string; returnTo?: string }) {
  const router = useRouter();
  const [challenge, setChallenge] = useState<TelegramChallenge>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!challenge) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const user = await completeTelegramChallenge(challenge);
        if (!active) return;
        if (user) {
          router.replace(returnTo);
          router.refresh();
          return;
        }
        timer = setTimeout(poll, 2000);
      } catch (reason) {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "Не удалось подтвердить вход через Telegram.");
        setChallenge(undefined);
        setPending(false);
      }
    };
    timer = setTimeout(poll, 1200);
    return () => { active = false; clearTimeout(timer); };
  }, [challenge, returnTo, router]);

  async function start() {
    const popup = window.open("about:blank", "anicast-telegram-login", "popup,width=520,height=720");
    if (popup) popup.opener = null;
    setPending(true);
    setError("");
    try {
      const created = await createTelegramChallenge();
      setChallenge(created);
      if (popup) popup.location.href = created.bot_url;
    } catch (reason) {
      popup?.close();
      setError(reason instanceof Error ? reason.message : "Не удалось начать вход через Telegram.");
      setPending(false);
    }
  }

  if (!botUsername) return <p className={styles.telegramUnavailable}>Вход через Telegram пока не настроен.</p>;
  return <div className={styles.telegramBlock}>
    <button className={styles.submit} type="button" disabled={pending} onClick={start}>{pending ? "Подтвердите вход в боте..." : "Войти через Telegram-бота"}</button>
    {pending && <><span>Нажмите Start в @{botUsername}, затем вернитесь на эту страницу.</span>{challenge && <a href={challenge.bot_url} target="_blank" rel="noreferrer">Открыть бота повторно</a>}</>}
    {error && <p className={styles.error} role="alert">{error}</p>}
  </div>;
}
