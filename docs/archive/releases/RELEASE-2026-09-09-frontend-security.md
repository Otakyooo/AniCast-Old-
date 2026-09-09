# Frontend security patch — 09.09.2026

Исходники: `13286f92f056bdfcc085cf9d1f23430b16e6bfe8`.
[CI и публикация](https://github.com/Otakyooo/AniCast/actions/runs/34334672751)
прошли полностью. Production frontend:

```text
ghcr.io/otakyooo/anicast-frontend@sha256:282e496e6ab3f42e2b588fd170189c1f5c19168ec0cee3a27082872b886ea519
```

## Изменения

- Next 15.5.23 → 15.5.25; eslint-config-next 15.4.6 → 15.5.25.
- sharp override 0.35.0 → 0.35.4; js-yaml 4.3.1 → 4.3.2 (dev dependency).
- `npm run audit` сканирует production/dev dependencies и блокирует high/critical.
- CI проверяет настоящий native sharp в собранном Alpine image: PNG → resize →
  WebP → проверка размеров, без сети и с лимитом памяти 128 MiB.

Исходный audit отметил три затронутых пакета, включая critical Next. Это не
доказательство эксплуатации сайта. Часть advisories зависит от ОС/библиотек:
[Windows](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36),
[AVIF optimizer](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4),
[sharp](https://github.com/lovell/sharp/security/advisories/GHSA-rgj7-g3m4-5g8c).
Эксплуатация прежнего musl runtime не проверялась.

## Проверки

- npm audit: **0 уязвимостей** текущего lockfile на дату проверки.
- CI: frontend lint/typecheck, 73 unit tests, build; backend и infrastructure gates;
  обе публикации и release manifests — success. Workflow проверен actionlint.
- В production подтверждены Next 15.5.25, sharp 0.35.4, libvips 8.18.6.
- Frontend/Caddy healthy после deploy; публичные главная/API — 200,
  `/internal/metrics` — 404.
- Браузер: главная и каталог, смена светлой/тёмной темы; исходная тёмная тема
  восстановлена. Нет ошибок console, битых загруженных изображений или
  горизонтального переполнения в проверенном desktop viewport.
  Это ограниченный smoke, не полный mobile/accessibility/E2E набор.

Реальный постер 6 200 879 bytes преобразован в WebP 46 520 bytes. Первый публичный
холодный запрос занял 20 735 ms. При диагностике скачивание исходника отдельно
заняло 9 158 ms, прямое преобразование sharp — 1 733 ms; другой холодный запрос
через loopback optimizer — 3 876 ms (MISS), повторный — 19 ms (HIT).
Запросы выполнялись отдельно: времена нельзя складывать как трассу первого запроса.
Долгая первая задержка не повторилась; стабильная нагрузочная ёмкость этим не доказана.

На VPS после проверки доступно около 332 MiB RAM, swap около 77 MiB; лимиты
и CPU не повышались. Увеличение RAM MainServer до 4 ГБ остаётся планом владельца.

## Выкладка и восстановление

Образ получен из успешного CI artifact, сборка на VPS не выполнялась.
Текущий manifest: `/var/lib/anicast/releases/vps/current.env`; immutable env:
`/root/anicast-security-13286f9/runtime.env`. Прежние env/Compose/Caddy и image
сохранены для аварийного отката. Старый frontend содержит прежние advisories;
возврат допустим только как краткий аварийный шаг с последующим исправлением.
Backend image, БД и MainServer workers этим релизом не менялись.

Оба recovery kits обновлены: `20260909T094102Z`. На рабочей станции расшифрованы
в памяти и проверены SHA-256 всех 21/11 файлов. Оба архива независимо скачаны
из Google Drive и побайтно сверены по SHA-256; VPS kit содержит текущий release
SHA/digest. Временный plaintext rclone config удалён. Реальные уведомления не отправлялись.

Следующие отдельные задачи: переход с Next 15 до конца поддержки, воспроизводимый
браузерный E2E и нагрузочные измерения. Этот patch не создаёт HA и не убирает
зависимость API от домашнего MainServer.
