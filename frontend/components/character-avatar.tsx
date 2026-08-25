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
  return <Image className={className} src={characterImage(imageUrl)} alt={alt} fill sizes={sizes} referrerPolicy="no-referrer" />;
}
