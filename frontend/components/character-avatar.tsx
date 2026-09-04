import Image from "next/image";
import { characterImage } from "../lib/character-image";

export function CharacterAvatar({
  imageUrl,
  alt = "",
  className,
  sizes,
}: {
  imageUrl: string;
  alt?: string;
  className?: string;
  sizes: string;
}) {
  return <Image
    className={className}
    src={characterImage(imageUrl)}
    alt={alt}
    fill
    sizes={sizes}
    quality={92}
    referrerPolicy="no-referrer"
    // Square crops of 2:3 character portraits read best slightly below the
    // top edge: that is where faces sit in both bust and full-body art.
    style={{ objectFit: "cover", objectPosition: "50% 22%" }}
  />;
}
