import { redirect } from "next/navigation";

/** Preserve old bookmarks while keeping playback on the canonical title page. */
export default async function LegacyWatchRedirect({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ episode?: string; voice?: string }>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  const target = new URLSearchParams({ episode: query.episode || "1" });
  if (query.voice) target.set("voice", query.voice);
  redirect(`/titles/${slug}?${target}`);
}
