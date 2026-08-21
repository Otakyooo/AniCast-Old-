export interface SessionUser {
  id: number;
  email: string | null;
  display_name: string;
}

type AuthPayload = {
  email: string;
  password: string;
  display_name?: string;
};

export async function getCsrfToken() {
  const response = await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" });
  if (!response.ok) throw new Error("Не удалось подготовить защищённый запрос.");
  const body = await response.json() as { csrfToken: string };
  return body.csrfToken;
}

async function parseError(response: Response) {
  const body = await response.json().catch(() => null) as Record<string, string | string[]> | null;
  if (!body) return "Не удалось выполнить запрос. Попробуйте ещё раз.";
  const message = Object.values(body).flat().find(Boolean);
  return message ?? "Не удалось выполнить запрос. Попробуйте ещё раз.";
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
  return response.status === 204 ? null : response.json() as Promise<SessionUser>;
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

export async function getSessionUser(): Promise<SessionUser | null> {
  const response = await fetch("/api/v1/auth/me/", { credentials: "same-origin", cache: "no-store" });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new Error("Не удалось загрузить данные аккаунта.");
  return response.json() as Promise<SessionUser>;
}

export async function signInWithTelegram(payload: object) {
  const csrf = await getCsrfToken();
  const response = await fetch("/api/v1/auth/telegram/login/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json() as Promise<SessionUser>;
}
