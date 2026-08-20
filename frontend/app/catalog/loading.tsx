export default function CatalogLoading() {
  return <main className="shell"><section className="content"><div className="page-heading"><p className="eyebrow">КОЛЛЕКЦИЯ ANICAST</p><h1>Каталог</h1></div><div className="catalog-grid" aria-label="Загрузка каталога" aria-busy="true">{[1, 2, 3, 4].map(item => <div className="catalog-card skeleton-card" key={item}><div className="poster-placeholder" /><div className="catalog-card-body"><span className="skeleton-line short" /><span className="skeleton-line" /><span className="skeleton-line small" /></div></div>)}</div></section></main>;
}
