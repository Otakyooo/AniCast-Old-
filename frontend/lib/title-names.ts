const JAPANESE_SCRIPT = /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/;

export interface TitleNameRow {
  language: string;
  name: string;
  /** Hidden for "ja" rows written in Latin script: a romaji title is not a
   *  Japanese reading, so a "JA" tag would misrepresent the data. */
  showLanguageTag: boolean;
}

/**
 * Display rows for a title's localized names.
 *
 * Identical names collapse into one row: imported feeds often repeat the
 * romaji in both `en` and `ja`, which used to render two "ONE PIECE" lines.
 * The first row is the primary name regardless of language.
 */
export function titleNameRows(
  localized: Partial<Record<"ru" | "en" | "ja", string>> | null | undefined,
  fallbackName: string,
  originalName?: string | null,
): TitleNameRow[] {
  const source = (Object.entries(localized ?? {}) as Array<[string, string]>)
    .filter(([, name]) => Boolean(name));
  if (source.length === 0) {
    source.push(["ru", fallbackName]);
    if (originalName) source.push(["ja", originalName]);
  }

  const rows: TitleNameRow[] = [];
  const seen = new Set<string>();
  for (const [language, name] of source) {
    if (seen.has(name)) continue;
    seen.add(name);
    rows.push({
      language,
      name,
      showLanguageTag: !(language === "ja" && !JAPANESE_SCRIPT.test(name)),
    });
  }
  return rows;
}
