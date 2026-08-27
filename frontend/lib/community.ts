import { getCsrfToken } from "./auth";

export interface Review { id:number; title:{name:string;slug:string}; author_name:string; author_public_id:string|null; body:string; contains_spoilers:boolean; published_at:string|null; updated_at:string; status?:string; moderation_note?:string }
export interface CommunitySummary { average_rating:number|null; rating_count:number; reviews:Review[]; my_rating:{value:number}|null; my_review:Review|null }

export async function getCommunitySummary(slug:string) {
  const response = await fetch(`/api/v1/titles/${encodeURIComponent(slug)}/community/`, { credentials:"same-origin", cache:"no-store" });
  if (!response.ok) throw new Error("Community request failed");
  return response.json() as Promise<CommunitySummary>;
}
async function mutate(path:string, method:string, body?:object) {
  const csrf=await getCsrfToken();
  return fetch(`/api/v1/community/${path}`, { method, credentials:"same-origin", headers:{"Content-Type":"application/json","X-CSRFToken":csrf}, body:body?JSON.stringify(body):undefined });
}
export async function setRating(slug:string,value:number){const r=await mutate(`ratings/${encodeURIComponent(slug)}/`,"PUT",{value});if(!r.ok)throw new Error("Rating failed");}
export async function saveReview(slug:string,body:string,contains_spoilers:boolean){const r=await mutate(`reviews/${encodeURIComponent(slug)}/`,"PUT",{body,contains_spoilers});if(!r.ok)throw new Error("Review failed");}
export async function deleteReview(slug:string){const r=await mutate(`reviews/${encodeURIComponent(slug)}/`,"DELETE");if(!r.ok)throw new Error("Delete failed");}
export async function getPublicReviews(signal?:AbortSignal){const r=await fetch("/api/v1/community/reviews/",{cache:"no-store",signal});if(!r.ok)throw new Error("Reviews failed");return r.json() as Promise<{count:number;results:Review[]}>;}
