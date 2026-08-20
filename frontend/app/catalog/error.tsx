"use client";

export default function CatalogError({ reset }: { reset: () => void }) {
  return <main className="shell"><section className="content"><div className="state-panel" role="alert"><p className="eyebrow">ОШИБКА СОЕДИНЕНИЯ</p><h1>Каталог не загрузился</h1><p className="muted">Не удалось получить данные. Проверь соединение и попробуй ещё раз.</p><button className="primary" onClick={reset}>Повторить</button></div></section></main>;
}
