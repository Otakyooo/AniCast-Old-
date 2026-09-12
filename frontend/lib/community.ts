import { getCsrfToken } from "./auth";

export interface Review { id:number; title:{name:string;slug:string}; author_name:string; author_public_id:string|null; body:string; contains_spoilers:boolean; published_at:string|null; updated_at:string; status?:string; moderation_note?:string }
export interface CommunitySummary { average_rating:number|null; rating_count:number; reviews:Review[]; my_rating:{value:number}|null; my_review:Review|null }
export interface FollowState { is_self:boolean; is_following:boolean; followers:number }
export type FollowingFeedItem =
  | { kind:"review"; occurred_at:string; author:{public_id:string;display_name:string}; review:Review }
  | { kind:"collection"; occurred_at:string; author:{public_id:string;display_name:string}; collection:{name:string;slug:string;description:string;item_count:number} };

/** Fetch failures keep their HTTP status so the UI can tell "sign in"
 * apart from "the request failed": a network error must not send a signed-in
 * viewer to the login page. Guests and aborted requests carry no status. */
export class CommunityApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "CommunityApiError";
    this.status = status;
  }
}

export function isAuthError(error: unknown): boolean {
  return error instanceof CommunityApiError && (error.status === 401 || error.status === 403);
}

export async function getCommunitySummary(slug:string) {
  const response = await fetch(`/api/v1/titles/${encodeURIComponent(slug)}/community/`, { credentials:"same-origin", cache:"no-store" });
  if (!response.ok) throw new CommunityApiError("Community request failed", response.status);
  return response.json() as Promise<CommunitySummary>;
}
async function mutate(path:string, method:string, body?:object) {
  const csrf=await getCsrfToken();
  return fetch(`/api/v1/community/${path}`, { method, credentials:"same-origin", headers:{"Content-Type":"application/json","X-CSRFToken":csrf}, body:body?JSON.stringify(body):undefined });
}
function throwForStatus(response:Response, message:string): void {
  if (!response.ok) throw new CommunityApiError(message, response.status);
}
export async function setRating(slug:string,value:number){const r=await mutate(`ratings/${encodeURIComponent(slug)}/`,"PUT",{value});throwForStatus(r,"Rating failed");}
export async function saveReview(slug:string,body:string,contains_spoilers:boolean){const r=await mutate(`reviews/${encodeURIComponent(slug)}/`,"PUT",{body,contains_spoilers});throwForStatus(r,"Review failed");}
export async function deleteReview(slug:string){const r=await mutate(`reviews/${encodeURIComponent(slug)}/`,"DELETE");throwForStatus(r,"Delete failed");}

export async function getFollowState(publicId:string, signal?:AbortSignal) {
  const response = await fetch(`/api/v1/community/follows/${encodeURIComponent(publicId)}/`, { credentials:"same-origin", cache:"no-store", signal });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new CommunityApiError("Follow state failed", response.status);
  return response.json() as Promise<FollowState>;
}

export async function followProfile(publicId:string) {
  const csrf = await getCsrfToken();
  const response = await fetch(`/api/v1/community/follows/${encodeURIComponent(publicId)}/`, {
    method:"PUT", credentials:"same-origin", cache:"no-store", headers:{"X-CSRFToken":csrf},
  });
  if (!response.ok) throw new CommunityApiError("Follow failed", response.status);
  return response.json() as Promise<FollowState>;
}

export async function unfollowProfile(publicId:string) {
  const csrf = await getCsrfToken();
  const response = await fetch(`/api/v1/community/follows/${encodeURIComponent(publicId)}/`, {
    method:"DELETE", credentials:"same-origin", cache:"no-store", headers:{"X-CSRFToken":csrf},
  });
  if (!response.ok) throw new CommunityApiError("Unfollow failed", response.status);
}

export async function getFollowingFeed(signal?:AbortSignal) {
  const response = await fetch("/api/v1/community/feed/", { credentials:"same-origin", cache:"no-store", signal });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new CommunityApiError("Following feed failed", response.status);
  return response.json() as Promise<{count:number;results:FollowingFeedItem[]}>;
}
