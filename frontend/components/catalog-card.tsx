import Link from "next/link";
import type { CatalogItem } from "../lib/api";

const statusLabels: Record<string, string> = {
  ongoing: "Выходит",
  finished: "Завершено",
  planned: "Скоро",
};

export function CatalogCard({ item }: { item: CatalogItem }) {
  const status = item.status ? statusLabels[item.status] ?? item.status : "Аниме";

  return (
    <Link className="catalog-card" href={`/titles/${item.slug}`}>
      <div
        className="poster-placeholder"
        style={{ "--poster-accent": "#6d5dfb" } as React.CSSProperties}
        aria-hidden="true"
      >
        <span>{item.name.slice(0, 1).toUpperCase()}</span>
      </div>
      <div className="catalog-card-body">
        <span className="card-kicker">{status}</span>
        <h2>{item.name}</h2>
        <p>{item.year ?? "Год не указан"}{item.title_type ? ` · ${item.title_type}` : ""}</p>
      </div>
    </Link>
  );
}
