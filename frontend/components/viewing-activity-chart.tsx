"use client";

import type { AccountSummary } from "../lib/auth";
import { intlLocale } from "../i18n/config";
import { useI18n } from "./i18n-provider";
import styles from "../app/profile.module.css";

export function ViewingActivityChart({ activity }: { activity: AccountSummary["activity"] }) {
  const { t, locale } = useI18n();
  const max = Math.max(1, ...activity.map((item) => item.episodes));
  const formatter = new Intl.DateTimeFormat(intlLocale[locale], { month: "short", timeZone: "UTC" });

  return (
    <section className={styles.activityCard} aria-labelledby="viewing-activity-title">
      <div className={styles.sectionHeading}>
        <div>
          <h2 id="viewing-activity-title">{t("profile.activityTitle")}</h2>
          <p>{t("profile.activitySubtitle")}</p>
        </div>
        <strong>{activity.reduce((sum, item) => sum + item.episodes, 0)}</strong>
      </div>
      <div className={styles.activityChart} role="img" aria-label={t("profile.activityLabel")}>
        {activity.map((item) => (
          <div className={styles.activityColumn} key={item.month} title={t("profile.activityCount", { count: item.episodes })}>
            <span className={styles.activityValue}>{item.episodes || ""}</span>
            <span className={styles.activityTrack}>
              <span className={styles.activityBar} style={{ height: `${Math.max(item.episodes ? 8 : 2, item.episodes / max * 100)}%` }} />
            </span>
            <span className={styles.activityMonth}>{formatter.format(new Date(`${item.month}-01T12:00:00Z`))}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
