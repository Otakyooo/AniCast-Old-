import { getCsrfToken } from "./auth";
import { clientMessage } from "../i18n/client";

export interface NotificationChannelStatus {
  connected: boolean;
  channel: { username: string; is_active: boolean; linked_at: string; disabled_at: string | null; last_error: string } | null;
}

async function csrfRequest(path: string, method: string, body?: object) {
  const csrf = await getCsrfToken();
  return fetch(`/api/v1/notifications/${path}`, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function getNotificationChannel() {
  const response = await fetch("/api/v1/notifications/telegram/channel/", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error(clientMessage("Не удалось проверить канал уведомлений.", "Could not check notification channel."));
  return response.json() as Promise<NotificationChannelStatus>;
}

export async function createNotificationChallenge() {
  const response = await csrfRequest("telegram/challenge/", "POST");
  if (!response.ok) throw new Error(clientMessage("Не удалось подключить Telegram-бота.", "Could not connect Telegram bot."));
  return response.json() as Promise<{ bot_url: string; expires_in: number }>;
}

export async function disconnectNotificationChannel() {
  const response = await csrfRequest("telegram/channel/", "DELETE");
  if (!response.ok) throw new Error(clientMessage("Не удалось отключить уведомления.", "Could not disable notifications."));
}

export async function getTitleSubscription(slug: string) {
  const response = await fetch(`/api/v1/notifications/subscriptions/${encodeURIComponent(slug)}/`, { credentials: "same-origin", cache: "no-store" });
  if (response.status === 404) return false;
  if (!response.ok) throw new Error(clientMessage("Не удалось проверить подписку.", "Could not check subscription."));
  return true;
}

export async function subscribeToTitle(slug: string) {
  const response = await csrfRequest(`subscriptions/${encodeURIComponent(slug)}/`, "PUT");
  if (!response.ok) throw new Error(clientMessage("Не удалось включить уведомления.", "Could not enable notifications."));
}

export async function unsubscribeFromTitle(slug: string) {
  const response = await csrfRequest(`subscriptions/${encodeURIComponent(slug)}/`, "DELETE");
  if (!response.ok) throw new Error(clientMessage("Не удалось отключить уведомления.", "Could not disable notifications."));
}


export interface SubscriptionTitle { name: string; slug: string; poster_url?: string | null; title_type: string; status: string }
export interface SubscriptionItem { title: SubscriptionTitle; is_active: boolean; created_at: string }
export interface Paginated<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface DeliveryItem { title: SubscriptionTitle; episode_number: number; status: string; sent_at: string | null; created_at: string }

export async function getSubscriptions() {
  const response = await fetch("/api/v1/notifications/subscriptions/", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error(clientMessage("Не удалось загрузить подписки.", "Could not load subscriptions."));
  return response.json() as Promise<Paginated<SubscriptionItem>>;
}

export async function getDeliveries() {
  const response = await fetch("/api/v1/notifications/deliveries/", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error(clientMessage("Не удалось загрузить уведомления.", "Could not load deliveries."));
  return response.json() as Promise<Paginated<DeliveryItem>>;
}
