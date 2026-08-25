export const CHARACTER_FALLBACK_IMAGE = "/not-found-mascot.webp";

const MISSING_ART_MARK = "missing_original";

export function characterImage(imageUrl: string | null | undefined): string {
  return imageUrl && !imageUrl.includes(MISSING_ART_MARK) ? imageUrl : CHARACTER_FALLBACK_IMAGE;
}

export function hasCharacterArt(imageUrl: string | null | undefined): boolean {
  return Boolean(imageUrl) && !imageUrl!.includes(MISSING_ART_MARK);
}
