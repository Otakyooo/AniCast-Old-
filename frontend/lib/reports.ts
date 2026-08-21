import { getCsrfToken } from "./auth";

export type SourceReportReason = "unavailable" | "wrong_content" | "geo_blocked" | "quality" | "other";

export class SourceReportApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function createSourceReport(payload: { source: number; reason: SourceReportReason; message: string }) {
  const csrf = await getCsrfToken();
  const response = await fetch("/api/v1/source-reports/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as Record<string, string | string[]> | null;
    const message = body ? Object.values(body).flat().find(Boolean) : null;
    throw new SourceReportApiError(response.status, message ?? "Не удалось отправить жалобу.");
  }
  return response.json();
}
