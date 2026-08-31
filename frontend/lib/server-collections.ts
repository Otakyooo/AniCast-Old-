import "server-only";

import { cache } from "react";
import { cookies } from "next/headers";
import type { CollectionDetail } from "./collections";
import { SITE_URL } from "./site";
import { internalApiHeaders } from "./internal-api";

export class PublicCollectionError extends Error {
  constructor(public status: number) {
    super(`Public collection request failed with status ${status}`);
  }
}

export const getPublicCollectionServer = cache(async (ownerPublicId: string, slug: string) => {
  const internalBase = process.env.INTERNAL_API_BASE_URL?.replace(/\/+$/, "");
  const base = internalBase || `${SITE_URL}/api/v1`;
  const locale = (await cookies()).get("anicast_lang")?.value ?? "ru";
  const url = `${base}/public/collections/${encodeURIComponent(ownerPublicId)}/${encodeURIComponent(slug)}/?lang=${encodeURIComponent(locale)}`;
  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Accept-Language": locale,
      ...(internalBase ? internalApiHeaders() : {}),
    },
  });
  if (!response.ok) throw new PublicCollectionError(response.status);
  return response.json() as Promise<CollectionDetail>;
});
