import "server-only";

import { cache } from "react";
import { cookies } from "next/headers";
import { SITE_URL } from "./site";
import type { PublicProfileData } from "./public-profile";

export class PublicProfileError extends Error {
  constructor(public status: number) {
    super(`Public profile request failed with status ${status}`);
  }
}

export const getPublicProfileServer = cache(async (publicId: string) => {
  const internalBase = process.env.INTERNAL_API_BASE_URL?.replace(/\/+$/, "");
  const base = internalBase || `${SITE_URL}/api/v1`;
  const locale = (await cookies()).get("anicast_lang")?.value ?? "ru";
  const response = await fetch(`${base}/public/users/${encodeURIComponent(publicId)}/?lang=${encodeURIComponent(locale)}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Accept-Language": locale,
      ...(internalBase ? { "X-Forwarded-Proto": "https" } : {}),
    },
  });
  if (!response.ok) throw new PublicProfileError(response.status);
  return response.json() as Promise<PublicProfileData>;
});
