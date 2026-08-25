import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { WatchSpace } from "../../../../components/watch-space";
import { ApiUnavailableState } from "../../../../components/api-unavailable";
import { PageShell } from "../../../../components/page-shell";
import {
  apiErrorStatus,
  getCatalogItem,
  getEpisode,
  getFirstEpisodeNumber,
  getWatchNavigation,
  type WatchNavigation,
} from "../../../../lib/api";

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
  searchParams: Promise<{ episode?: string; voice?: string }>;
}) {
  const { slug } = await params;
  const { episode: rawEpisodeParam, voice: requestedSourceKey } = await searchParams;
  let item;
  try {
    item = await getCatalogItem(slug);
  } catch (error) {
    if (apiErrorStatus(error) === 404) notFound();
    return <ApiUnavailableState />;
  }
  const episodesCount = item.episodes_count ?? 0;
  if (!episodesCount) notFound();

  let navigation: WatchNavigation;
  try {
    navigation = await getWatchNavigation(slug);
  } catch {
    // Keep the watch route usable during a rolling backend/frontend deploy.
    navigation = {
      episode_numbers: Array.from({ length: episodesCount }, (_, index) => index + 1),
      source_groups: [],
    };
  }
  const episodeNumbers = navigation.episode_numbers.length
    ? navigation.episode_numbers
    : Array.from({ length: episodesCount }, (_, index) => index + 1);

  // Navigation uses actual episode numbers rather than assuming every title is
  // sequential, so stale links cannot silently land on another episode.
  const rawRequested = Number(rawEpisodeParam);
  const fallbackNumber = Number(episodeNumbers[0] ?? (await getFirstEpisodeNumber(slug).catch(() => null)) ?? 1);
  let number = Number.isInteger(rawRequested) && episodeNumbers.includes(rawRequested)
    ? rawRequested
    : fallbackNumber || 1;

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
        episodeNumbers={episodeNumbers}
        sourceGroups={navigation.source_groups}
        requestedSourceKey={requestedSourceKey}
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
