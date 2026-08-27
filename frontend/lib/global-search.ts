export interface SearchOption {
  id: string;
  href: string;
}

export interface SearchOptionModel {
  options: SearchOption[];
  starts: {
    titles: number;
    characters: number;
    franchises: number;
  };
}

interface SearchOptionGroups {
  titles: Array<{ slug: string }>;
  characters: Array<{ slug: string }>;
  franchises: Array<{ slug: string }>;
}

/**
 * Flattens grouped search results into the exact order exposed by the listbox.
 * Group start indexes keep pointer and keyboard selection on the same option.
 */
export function buildSearchOptionModel(
  data: SearchOptionGroups,
  panelId: string,
  query: string,
): SearchOptionModel {
  const starts = {
    titles: 0,
    characters: data.titles.length,
    franchises: data.titles.length + data.characters.length,
  };

  return {
    starts,
    options: [
      ...data.titles.map((item) => ({
        id: `${panelId}-title-${item.slug}`,
        href: `/titles/${item.slug}`,
      })),
      ...data.characters.map((item) => ({
        id: `${panelId}-character-${item.slug}`,
        href: `/characters/${item.slug}`,
      })),
      ...data.franchises.map((item) => ({
        id: `${panelId}-franchise-${item.slug}`,
        href: `/franchises/${item.slug}`,
      })),
      {
        id: `${panelId}-all`,
        href: `/catalog?q=${encodeURIComponent(query)}`,
      },
    ],
  };
}
