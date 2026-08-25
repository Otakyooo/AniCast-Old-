import type { Locale } from "../i18n/config";
import { clientLanguage, clientMessage } from "../i18n/client";

export interface SessionUser {
  id: number;
  email: string | null;
  display_name: string;
  preferred_language: Locale;
  date_joined: string;
  avatar_url: string;
}

export function setLanguageCookie(language: Locale) {
  const secure = typeof window !== "undefined" && window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `anicast_lang=${language}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}

export async function setPreferredLanguage(language: Locale) {
  const csrf = await getCsrfToken();
  const response = await fetch("/api/v1/auth/preferences/", {
    method: "PUT", credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: JSON.stringify({ preferred_language: language }),
  });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new Error("Could not save language preference.");
  return response.json() as Promise<SessionUser>;
}

type AuthPayload = {
  email: string;
  password: string;
  display_name?: string;
};

export async function getCsrfToken() {
  const response = await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" });
  if (!response.ok) throw new Error(clientMessage("Не удалось подготовить защищённый запрос.", "Could not prepare a secure request."));
  const body = await response.json() as { csrfToken: string };
  return body.csrfToken;
}

async function parseError(response: Response) {
  if (clientLanguage() === "en") return "Request failed. Check the entered data and try again.";
  const body = await response.json().catch(() => null) as Record<string, string | string[]> | null;
  if (!body) return clientMessage("Не удалось выполнить запрос. Попробуйте ещё раз.", "Request failed. Please try again.");
  const message = Object.values(body).flat().find(Boolean);
  return message ?? clientMessage("Не удалось выполнить запрос. Попробуйте ещё раз.", "Request failed. Please try again.");
}

async function mutateSession(path: string, payload?: AuthPayload): Promise<SessionUser | null> {
  const csrf = await getCsrfToken();
  const response = await fetch(`/api/v1/auth/${path}/`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) throw new Error(await parseError(response));
  const user = response.status === 204 ? null : ((await response.json()) as SessionUser);
  writeCachedSession(user);
  return user;
}

export function register(payload: AuthPayload) {
  return mutateSession("register", payload);
}

export function signIn(payload: AuthPayload) {
  return mutateSession("login", payload);
}

export function signOut() {
  return mutateSession("logout");
}

const SESSION_CACHE_KEY = "anicast.session";

/** Last validated session from sessionStorage: user, null (guest) or undefined (no cache). */
export function cachedSessionUser(): SessionUser | null | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const raw = window.sessionStorage.getItem(SESSION_CACHE_KEY);
    return raw === null ? undefined : (JSON.parse(raw) as SessionUser | null);
  } catch {
    return undefined;
  }
}

function writeCachedSession(user: SessionUser | null) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(SESSION_CACHE_KEY, JSON.stringify(user));
  } catch {
    // Storage may be unavailable (private mode); the cache is optional.
  }
}

export async function getSessionUser(): Promise<SessionUser | null> {
  const response = await fetch("/api/v1/auth/me/", { credentials: "same-origin", cache: "no-store" });
  if (response.status === 401 || response.status === 403) {
    writeCachedSession(null);
    return null;
  }
  if (!response.ok) throw new Error(clientMessage("Не удалось загрузить данные аккаунта.", "Could not load account data."));
  const user = (await response.json()) as SessionUser;
  writeCachedSession(user);
  return user;
}

export interface GenreShare {
  slug: string;
  name: string;
  count: number;
  share: number;
}

export interface AccountSummary {
  library: { planned: number; watching: number; completed: number; on_hold: number; dropped: number };
  favorites: number;
  watched_episodes: number;
  watched_hours: number;
  average_rating: number | null;
  top_genres: GenreShare[];
  notes: number;
  collections: number;
  ratings: number;
  reviews: number;
  activity: Array<{ month: string; episodes: number }>;
}

export async function fetchAccountSummary(): Promise<AccountSummary> {
  const response = await fetch("/api/v1/account/summary/", { credentials: "same-origin", cache: "no-store" });
  if (response.status === 401 || response.status === 403) throw new Error("unauthorized");
  if (!response.ok) throw new Error(clientMessage("Не удалось загрузить статистику.", "Could not load statistics."));
  return response.json() as Promise<AccountSummary>;
}

export interface TelegramChallenge {
  token: string;
  bot_url: string;
  expires_in: number;
  csrf: string;
}

export async function createTelegramChallenge(): Promise<TelegramChallenge> {
  const csrf = await getCsrfToken();
  const response = await fetch("/api/v1/auth/telegram/challenge/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
  });
  if (!response.ok) throw new Error(await parseError(response));
  const challenge = await response.json() as Omit<TelegramChallenge, "csrf">;
  return { ...challenge, csrf };
}

export async function completeTelegramChallenge(challenge: TelegramChallenge) {
  const response = await fetch("/api/v1/auth/telegram/challenge/complete/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": challenge.csrf },
    body: JSON.stringify({ token: challenge.token }),
  });
  if (response.status === 202) return null;
  if (!response.ok) throw new Error(await parseError(response));
  return response.json() as Promise<SessionUser>;
}
