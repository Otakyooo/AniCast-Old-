import Image from "next/image";
import Link from "next/link";

export function BrandLockup({ className = "", priority = false }: { className?: string; priority?: boolean }) {
  return (
    <Link className={`brand-lockup ${className}`.trim()} href="/" aria-label="AniCast">
      <Image
        className="brand-logo"
        src="/brand-mark.png"
        alt=""
        width={36}
        height={36}
        priority={priority}
      />
      <span className="brand-wordmark"><span>Ani</span><strong>Cast</strong></span>
    </Link>
  );
}
