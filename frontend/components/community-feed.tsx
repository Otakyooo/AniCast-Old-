"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getPublicReviews, type Review } from "../lib/community";
import { useI18n } from "./i18n-provider";
import styles from "../app/community/community.module.css";

export function CommunityFeed(){const{t}=useI18n();const[reviews,setReviews]=useState<Review[]>();useEffect(()=>{const c=new AbortController();getPublicReviews(c.signal).then(r=>setReviews(r.results)).catch(()=>setReviews([]));return()=>c.abort();},[]);if(!reviews)return <div className="empty-state">{t("common.loading")}</div>;if(!reviews.length)return <div className="empty-state"><strong>{t("community.noReviews")}</strong></div>;return <div>{reviews.map(review=><article className={styles.review} key={review.id}><Link href={`/titles/${review.title.slug}`}><strong>{review.title.name}</strong></Link><span> · {review.author_name}</span>{review.contains_spoilers?<details><summary>{t("community.showSpoiler")}</summary><p>{review.body}</p></details>:<p>{review.body}</p>}</article>)}</div>}
