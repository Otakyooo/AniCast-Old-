import { clientMessage } from "../i18n/client";
import type { CatalogItem } from "./api";
import { getCsrfToken } from "./auth";

export interface CollectionOwner {
  public_id: string;
  display_name: string;
  profile_is_public: boolean;
}

export interface CollectionItem {
  title: CatalogItem;
  position: number;
  created_at?: string;
}

/**
 * Poster-only row returned by the list endpoint.
 *
 * Cards draw a name and a poster, so the list response carries just that. The
 * full `CollectionItem` with its nested title stays on the detail endpoints,
 * where a collection is capped at 200 items and every one is rendered.
 */
export interface CollectionPreviewItem {
  position: number;
  slug: string;
  name: string;
  poster_url: string | null;
}

/** Collection card: a count, a bounded preview and optional membership. */
export interface CollectionSummary {
  slug: string;
  name: string;
  description: string;
  is_public: boolean;
  item_count: number;
  preview_items: CollectionPreviewItem[];
  /** Present only when the request passed a title slug; null otherwise. */
  contains_title: boolean | null;
  owner?: CollectionOwner;
  created_at?: string;
  updated_at?: string;
}

export interface CollectionDetail {
  slug: string;
  name: string;
  description: string;
  is_public: boolean;
  items: CollectionItem[];
  owner?: CollectionOwner;
  owner_public_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface CollectionInput {
  name: string;
  slug: string;
  description: string;
  is_public: boolean;
}

export class CollectionsApiError extends Error {
  constructor(public status: number, message = clientMessage("Не удалось выполнить запрос к коллекциям.", "Collection request failed.")) {
    super(message);
    this.name = "CollectionsApiError";
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) throw new CollectionsApiError(response.status);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function mutation<T>(path: string, method: "POST" | "PATCH" | "DELETE", body?: object, signal?: AbortSignal) {
  const csrf = await getCsrfToken();
  return parse<T>(await fetch(path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    signal,
    headers: { "X-CSRFToken": csrf, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  }));
}

function collectionResults(payload: CollectionSummary[] | { results: CollectionSummary[] }) {
  return Array.isArray(payload) ? payload : payload.results ?? [];
}

/**
 * Collection cards for the owner.
 *
 * `titleSlug` asks the server which collections already contain that title, so
 * membership no longer requires the full nested item list of every collection.
 */
export async function getCollections(signal?: AbortSignal, titleSlug?: string) {
  const query = titleSlug ? `?title=${encodeURIComponent(titleSlug)}` : "";
  const response = await fetch(`/api/v1/collections/${query}`, { credentials: "same-origin", cache: "no-store", signal });
  return collectionResults(await parse<CollectionSummary[] | { results: CollectionSummary[] }>(response));
}

export function createCollection(payload: CollectionInput, signal?: AbortSignal) {
  return mutation<CollectionDetail>("/api/v1/collections/", "POST", payload, signal);
}

export async function getCollection(slug: string, signal?: AbortSignal) {
  return parse<CollectionDetail>(await fetch(`/api/v1/collections/${encodeURIComponent(slug)}/`, { credentials: "same-origin", cache: "no-store", signal }));
}

export function updateCollection(slug: string, payload: Partial<Omit<CollectionInput, "slug">>, signal?: AbortSignal) {
  return mutation<CollectionDetail>(`/api/v1/collections/${encodeURIComponent(slug)}/`, "PATCH", payload, signal);
}

export function deleteCollection(slug: string, signal?: AbortSignal) {
  return mutation<void>(`/api/v1/collections/${encodeURIComponent(slug)}/`, "DELETE", undefined, signal);
}

export function addCollectionItem(slug: string, titleSlug: string, signal?: AbortSignal) {
  return mutation<CollectionItem>(`/api/v1/collections/${encodeURIComponent(slug)}/items/`, "POST", { title_slug: titleSlug }, signal);
}

export function updateCollectionItem(slug: string, titleSlug: string, position: number, signal?: AbortSignal) {
  return mutation<CollectionItem>(`/api/v1/collections/${encodeURIComponent(slug)}/items/${encodeURIComponent(titleSlug)}/`, "PATCH", { position }, signal);
}

export function deleteCollectionItem(slug: string, titleSlug: string, signal?: AbortSignal) {
  return mutation<void>(`/api/v1/collections/${encodeURIComponent(slug)}/items/${encodeURIComponent(titleSlug)}/`, "DELETE", undefined, signal);
}
