import Image from "next/image";
import Link from "next/link";

export function BrandLockup({ className = "", priority = false }: { className?: string; priority?: boolean }) {
  return (
    <Link className={`brand-lockup ${className}`.trim()} href="/" aria-label="Anicast">
      <Image
        className="brand-logo"
        src="/brand-mark-v01.png"
        alt=""
        width={40}
        height={40}
        priority={priority}
      />
      <span className="brand-wordmark"><span>Ani</span><strong>cast</strong></span>
    </Link>
  );
}
