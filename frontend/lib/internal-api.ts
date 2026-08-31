/** Headers accepted only on the private Next.js -> Django hop. */
export function internalApiHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "X-Forwarded-Proto": "https" };
  const token = process.env.INTERNAL_API_TOKEN ?? "";
  if (token.length >= 32) headers["X-AniCast-Internal-Token"] = token;
  return headers;
}
