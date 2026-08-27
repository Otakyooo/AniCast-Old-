"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSessionUser } from "../lib/auth";
import { followProfile, getFollowState, unfollowProfile, type FollowState } from "../lib/community";
import { useI18n } from "./i18n-provider";
import styles from "../app/users/[publicId]/profile.module.css";

export function FollowButton({ publicId, initialFollowers }: { publicId:string; initialFollowers:number }) {
  const { t } = useI18n();
  const [state, setState] = useState<FollowState | null>();
  const [followers, setFollowers] = useState(initialFollowers);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getSessionUser()
      .then((user) => user ? getFollowState(publicId, controller.signal) : null)
      .then((value) => {
        setState(value);
        if (value) setFollowers(value.followers);
      })
      .catch(() => setState(null));
    return () => controller.abort();
  }, [publicId]);

  async function toggle() {
    if (!state || state.is_self) return;
    setPending(true);
    try {
      if (state.is_following) {
        await unfollowProfile(publicId);
        setState({ ...state, is_following:false, followers:Math.max(0, followers - 1) });
        setFollowers((value) => Math.max(0, value - 1));
      } else {
        const next = await followProfile(publicId);
        setState(next);
        setFollowers(next.followers);
      }
    } finally {
      setPending(false);
    }
  }

  return <div className={styles.followControl}>
    {state === undefined ? <span className={styles.followPlaceholder} aria-hidden="true" /> : state === null ? (
      <Link className={styles.followSecondary} href="/login">{t("social.signInToFollow")}</Link>
    ) : state.is_self ? (
      <Link className={styles.followSecondary} href="/settings">{t("social.editOwnProfile")}</Link>
    ) : (
      <button className={state.is_following ? styles.followSecondary : styles.followPrimary} type="button" onClick={toggle} disabled={pending}>
        {pending ? t("auth.wait") : state.is_following ? t("social.unfollow") : t("social.follow")}
      </button>
    )}
    <span>{t("social.followersCount", { count:followers })}</span>
  </div>;
}
