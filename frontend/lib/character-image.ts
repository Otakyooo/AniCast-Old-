export const CHARACTER_FALLBACK_IMAGE = "/brand-mark.png";

const LOCAL_MEDIA_PATH = "/api/v1/media/";

function isAniCastMedia(imageUrl: string): boolean {
  if (imageUrl.startsWith(LOCAL_MEDIA_PATH)) return true;
  try {
    const parsed = new URL(imageUrl);
    return parsed.protocol === "https:"
      && parsed.hostname === "anicast.online"
      && parsed.pathname.startsWith(LOCAL_MEDIA_PATH);
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
