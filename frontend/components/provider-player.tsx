"use client";

import { useState } from "react";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

export function ProviderPlayer({ src, title, onClose }: { src: string; title: string; onClose: () => void }) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(true);

  return (
    <section className={styles.playerShell} aria-busy={loading}>
      <div className={styles.playerBar}>
        <strong>{title}</strong>
        <button className="secondary inline-button" type="button" onClick={onClose}>{t("source.closePlayer")}</button>
      </div>
      <div className={styles.playerFrameWrap}>
        {loading && <span className={styles.playerLoading}>{t("common.loading")}</span>}
        <iframe
          className={styles.playerFrame}
          src={src}
          title={t("source.playerTitle", { name: title })}
          allow="autoplay *; fullscreen *"
          allowFullScreen
          loading="lazy"
          referrerPolicy="no-referrer"
          sandbox="allow-forms allow-presentation allow-same-origin allow-scripts"
          onLoad={() => setLoading(false)}
        />
      </div>
    </section>
  );
}
