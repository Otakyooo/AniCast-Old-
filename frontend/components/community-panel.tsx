"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { deleteReview, getCommunitySummary, saveReview, setRating, type CommunitySummary } from "../lib/community";
import { useI18n } from "./i18n-provider";
import styles from "../app/community/community.module.css";

export function CommunityPanel({slug}:{slug:string}){
  const {t}=useI18n(); const [data,setData]=useState<CommunitySummary>(); const [error,setError]=useState("");
  const load=()=>getCommunitySummary(slug).then(setData).catch(()=>setError(t("common.error")));
  useEffect(()=>{getCommunitySummary(slug).then(setData).catch(()=>setError(t("common.error")));},[slug,t]);
  async function rate(value:number){try{await setRating(slug,value);await load();}catch{setError(t("community.signIn"));}}
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const f=new FormData(e.currentTarget);try{await saveReview(slug,String(f.get("body")??""),f.get("spoiler")==="on");await load();}catch{setError(t("community.signIn"));}}
  if(!data)return <section className={styles.panel}>{error||t("common.loading")}</section>;
  return <section className={styles.panel}><div className={styles.summary}><h2>{t("community.title")}</h2><strong>{data.average_rating!==null?t("community.average",{value:data.average_rating}):t("community.noRating")}</strong><span>({data.rating_count})</span></div><div className={styles.rating}><span>{t("community.rating")}</span>{[1,2,3,4,5,6,7,8,9,10].map(value=><button className={data.my_rating?.value===value?styles.active:undefined} onClick={()=>rate(value)} type="button" key={value}>{value}</button>)}</div><form className={styles.form} onSubmit={submit}><label>{t("community.review")}<textarea name="body" minLength={20} maxLength={5000} defaultValue={data.my_review?.body??""} placeholder={t("community.reviewPlaceholder")} required /></label><label className={styles.spoiler}><input type="checkbox" name="spoiler" defaultChecked={data.my_review?.contains_spoilers}/>{t("community.spoiler")}</label><button type="submit">{t("community.submit")}</button>{data.my_review&&<button type="button" onClick={async()=>{await deleteReview(slug);await load();}}>{t("common.delete")}</button>}{data.my_review?.status&&<small>{t(`community.${data.my_review.status}`)}</small>}</form>{error&&<p>{error} <Link href="/login">{t("common.login")}</Link></p>}<div><h3>{t("community.publicReviews")}</h3>{data.reviews.length?data.reviews.map(review=><article className={styles.review} key={review.id}><strong>{review.author_name}</strong>{review.contains_spoilers?<details><summary>{t("community.showSpoiler")}</summary><p>{review.body}</p></details>:<p>{review.body}</p>}</article>):<p>{t("community.noReviews")}</p>}</div></section>;
}
