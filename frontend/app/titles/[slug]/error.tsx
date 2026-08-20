"use client";

import Link from "next/link";

export default function CatalogDetailError({ reset }: { reset: () => void }) {
  return <main className="shell"><section className="content"><div className="state-panel" role="alert"><p className="eyebrow">ОШИБКА СОЕДИНЕНИЯ</p><h1>Не удалось открыть тайтл</h1><p className="muted">Данные временно недоступны. Попробуй ещё раз или вернись в каталог.</p><button className="primary" onClick={reset}>Повторить</button><Link className="secondary" href="/catalog">В каталог</Link></div></section></main>;
}
