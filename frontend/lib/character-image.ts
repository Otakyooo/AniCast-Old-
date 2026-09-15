export const CHARACTER_FALLBACK_IMAGE = "/brand-mark-v01.png";

const LOCAL_MEDIA_PATH = "/api/v1/media/";

function isAniCastMedia(imageUrl: string): boolean {
  if (imageUrl.startsWith(LOCAL_MEDIA_PATH)) return true;
  try {
    const parsed = new URL(imageUrl);
    // No host comparison. The API is the only producer of this path, and the
    // public origin is configuration (POSTERS_PUBLIC_BASE). Pinning the host
    // here meant a domain change silently swapped every portrait for the
    // brand mark while the backend had already moved, and it needed a second
    // setting to be kept in step by hand.
    return parsed.protocol === "https:" && parsed.pathname.startsWith(LOCAL_MEDIA_PATH);
  } catch {
    return false;
  }
}

export function characterImage(imageUrl: string | null | undefined): string {
  return imageUrl && isAniCastMedia(imageUrl) ? imageUrl : CHARACTER_FALLBACK_IMAGE;
}

export function hasCharacterArt(imageUrl: string | null | undefined): boolean {
  return Boolean(imageUrl) && isAniCastMedia(imageUrl!);
}
