import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { WatchSpace } from "../../../../components/watch-space";
import { ApiUnavailableState } from "../../../../components/api-unavailable";
import { PageShell } from "../../../../components/page-shell";
import {
  apiErrorStatus,
  getCatalogItemEpisodes,
  getEpisode,
  getWatchNavigation,
  type WatchNavigation,
} from "../../../../lib/api";
import { NO_INDEX_ROBOTS } from "../../../../lib/seo";
import { getI18n } from "../../../../i18n/server";

export const dynamic = "force-dynamic";

/** Playback is an application state, not a second indexable title page. */
export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getI18n();
  return {
    title: t("watch.title"),
    robots: NO_INDEX_ROBOTS,
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
  const { episode: rawEpisode, voice: requestedSourceKey } = await searchParams;
  const navigationRequest = getWatchNavigation(slug).catch(() => null);

  let item;
  try {
    // The player needs title metadata and the real first episode only; avoid
    // loading a long title's full nested source list.
    item = await getCatalogItemEpisodes(slug, 1, 1);
  } catch (error) {
    if (apiErrorStatus(error) === 404) notFound();
    return <ApiUnavailableState />;
  }

  const episodesCount = item.episodes_count ?? 0;
  if (!episodesCount) notFound();

  const loadedNavigation = await navigationRequest;
  const navigation: WatchNavigation = loadedNavigation ?? {
    episode_numbers: Array.from({ length: episodesCount }, (_, index) => index + 1),
    source_groups: [],
  };
  const episodeNumbers = navigation.episode_numbers.length
    ? navigation.episode_numbers
    : Array.from({ length: episodesCount }, (_, index) => index + 1);
  const fallbackNumber = Number(episodeNumbers[0] ?? item.episodes?.[0]?.number ?? 1);
  const requestedNumber = Number(rawEpisode);
  let number = Number.isInteger(requestedNumber) && episodeNumbers.includes(requestedNumber)
    ? requestedNumber
    : fallbackNumber;

  let episode;
  try {
    episode = await getEpisode(slug, number);
  } catch (error) {
    if (apiErrorStatus(error) !== 404) return <ApiUnavailableState />;
    number = fallbackNumber;
    try {
      episode = await getEpisode(slug, fallbackNumber);
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
        trackProgress
      />
    </PageShell>
  );
}
