import Link from "next/link";
import { getCatalogItem } from "../../../lib/api";

export const dynamic = "force-dynamic";

export default async function CatalogDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let item;
  try {
    item = await getCatalogItem(slug);
  } catch (error) {
    if (error instanceof Error && Object.hasOwn(error, "status") && (error as Error & { status?: number }).status === 404) return <NotFoundState />;
    throw error;
  }

  return <main className="shell"><aside className="sidebar"><Link className="brand" href="/">Ani<span>Cast</span></Link><nav aria-label="Основная навигация"><Link href="/">Главная</Link><Link className="active" href="/catalog">Каталог</Link><Link href="#">Расписание</Link><Link href="#">Франшизы</Link><Link href="#">Персонажи</Link><Link href="#">Медиа</Link></nav></aside><section className="content"><header className="topbar"><Link className="back-link" href="/catalog">← Каталог</Link><button className="profile">Войти</button></header><article className="detail"><div className="detail-poster poster-placeholder" style={{ "--poster-accent": item.accent ?? "#6d5dfb" } as React.CSSProperties} aria-label={`Обложка: ${item.title}`}><span>{item.title.slice(0, 1).toUpperCase()}</span></div><div className="detail-copy"><p className="eyebrow">{item.type ?? "АНИМЕ"}</p><h1>{item.title}</h1>{item.original_title && <p className="original-title">{item.original_title}</p>}<p className="muted">{item.description || "Описание для этого тайтла пока не добавлено."}</p><div className="detail-meta"><span>{item.year ?? "Год неизвестен"}</span><span>{item.episodes ? `${item.episodes} эп.` : "Эпизоды уточняются"}</span><span>{item.status ?? "Статус уточняется"}</span></div>{item.genres?.length ? <div className="tag-list">{item.genres.map(genre => <span key={genre}>{genre}</span>)}</div> : null}<button className="primary">Добавить в библиотеку</button></div></article></section></main>;
}

function NotFoundState() {
  return <main className="shell"><section className="content"><div className="state-panel" role="status"><p className="eyebrow">404</p><h1>Тайтл не найден</h1><p className="muted">Похоже, этот тайтл ещё не появился в каталоге или был перемещён.</p><Link className="primary inline-button" href="/catalog">Вернуться в каталог</Link></div></section></main>;
}
