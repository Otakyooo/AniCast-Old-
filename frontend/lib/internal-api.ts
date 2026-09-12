/** Headers accepted only on the private Next.js -> Django hop. */
export function internalApiHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "X-Forwarded-Proto": "https" };
  const token = process.env.INTERNAL_API_TOKEN ?? "";
  if (token.length >= 32) {
    headers["X-AniCast-Internal-Token"] = token;
  } else if (process.env.NODE_ENV === "production") {
    // Fail-closed without leaking the value: SSR continues anonymously and the
    // misconfiguration surfaces in logs rather than as a silent data downgrade.
    console.error("INTERNAL_API_TOKEN is missing or shorter than 32 chars; SSR continues without it");
  }
  return headers;
}
