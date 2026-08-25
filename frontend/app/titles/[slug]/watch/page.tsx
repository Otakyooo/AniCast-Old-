import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { WatchSpace } from "../../../../components/watch-space";
import { ApiUnavailableState } from "../../../../components/api-unavailable";
import { PageShell } from "../../../../components/page-shell";
import { apiErrorStatus, getCatalogItem, getEpisode, getFirstEpisodeNumber } from "../../../../lib/api";

export const dynamic = "force-dynamic";

// Episode views duplicate the title page content: they canonicalize to the
// title and stay out of the index.
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  return {
    title: "AniCast",
    alternates: { canonical: `/titles/${slug}` },
    robots: { index: false, follow: true },
  };
}

export default async function WatchPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ episode?: string }>;
}) {
  const { slug } = await params;
  const { episode: rawEpisodeParam } = await searchParams;
  let item;
  try {
    item = await getCatalogItem(slug);
  } catch (error) {
    if (apiErrorStatus(error) === 404) notFound();
    return <ApiUnavailableState />;
  }
  const episodesCount = item.episodes_count ?? 0;
  if (!episodesCount) notFound();

  // Without an explicit ?episode= the watch space resumes from the first
  // episode; numbers are sequential in this catalog, so clamping to the count
  // keeps stale deep links inside the real range.
  const rawRequested = Number(rawEpisodeParam);
  const fallbackNumber = Number((await getFirstEpisodeNumber(slug).catch(() => null)) ?? 1);
  let number = Number.isInteger(rawRequested) && rawRequested >= 1 ? rawRequested : fallbackNumber || 1;
  number = Math.min(number, episodesCount);

  let episode;
  try {
    episode = await getEpisode(slug, number);
  } catch (error) {
    if (apiErrorStatus(error) !== 404) return <ApiUnavailableState />;
    try {
      episode = await getEpisode(slug, 1);
      number = 1;
    } catch (retryError) {
      if (apiErrorStatus(retryError) === 404) notFound();
      return <ApiUnavailableState />;
    }
  }

  return (
    <PageShell active="catalog" back={{ href: `/titles/${slug}`, label: item.name }}>
      <WatchSpace
        slug={slug}
        titleName={item.name}
        episodesCount={episodesCount}
        currentNumber={number}
        episode={{
          number: episode.number,
          name: episode.name,
          synopsis: episode.synopsis,
          air_date: episode.air_date,
          sources: episode.sources ?? [],
        }}
      />
    </PageShell>
  );
}
