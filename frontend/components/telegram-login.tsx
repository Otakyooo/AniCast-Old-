"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { signInWithTelegram } from "../lib/auth";
import styles from "../app/auth.module.css";

type TelegramPayload = {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
};

declare global {
  interface Window { onTelegramAuth?: (user: TelegramPayload) => void }
}

export function TelegramLogin({ botUsername }: { botUsername?: string }) {
  const router = useRouter();
  const container = useRef<HTMLDivElement>(null);
  const pendingRef = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!botUsername || !container.current || !/^[A-Za-z0-9_]{5,32}$/.test(botUsername)) return;
    const target = container.current;
    window.onTelegramAuth = async (payload) => {
      if (pendingRef.current) return;
      pendingRef.current = true;
      setPending(true);
      setError("");
      try {
        await signInWithTelegram(payload);
        router.replace("/account");
        router.refresh();
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Не удалось войти через Telegram.");
      } finally {
        pendingRef.current = false;
        setPending(false);
      }
    };
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.dataset.telegramLogin = botUsername;
    script.dataset.size = "large";
    script.dataset.userpic = "false";
    script.dataset.radius = "8";
    script.dataset.onauth = "onTelegramAuth(user)";
    target.appendChild(script);
    return () => {
      delete window.onTelegramAuth;
      target.replaceChildren();
    };
  }, [botUsername, router]);

  if (!botUsername) return <p className={styles.telegramUnavailable}>Вход через Telegram появится после подключения бота.</p>;
  return <div className={styles.telegramBlock}><div ref={container} aria-busy={pending} />{pending && <span>Проверяем Telegram...</span>}{error && <p className={styles.error} role="alert">{error}</p>}</div>;
}
