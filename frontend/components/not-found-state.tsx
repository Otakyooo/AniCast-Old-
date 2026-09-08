import Image from "next/image";
import Link from "next/link";
import styles from "../app/not-found.module.css";

interface NotFoundAction {
  href: string;
  label: string;
  primary?: boolean;
}

export function NotFoundState({
  title,
  text,
  imageAlt,
  actions,
}: {
  title: string;
  text: string;
  imageAlt: string;
  actions: NotFoundAction[];
}) {
  return (
    <main className={`shell ${styles.notFoundPage}`}>
      <div className={styles.panel} role="status">
        <Image
          className={styles.illustration}
          src="/not-found-brand-v01.webp"
          alt={imageAlt}
          width={1254}
          height={1254}
          priority
          sizes="(max-width: 760px) 86vw, 420px"
        />
        <div className={styles.copy}>
          <p className="eyebrow">404</p>
          <h1>{title}</h1>
          <p className="muted">{text}</p>
          <div className={styles.actions}>
            {actions.map((action) => (
              <Link
                className={action.primary ? "primary inline-button" : "secondary"}
                href={action.href}
                key={action.href}
              >
                {action.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
