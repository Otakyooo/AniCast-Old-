import type { Locale } from "./config";

const ru: Record<string, string> = {
  "meta.homeTitle":"Anicast — аниме-каталог, расписание и сообщество","meta.homeDescription":"Каталог аниме с описаниями, персонажами, расписанием новых серий, оценками и личной библиотекой.","meta.catalogDescription":"Каталог аниме Anicast: поиск по названию, жанрам, формату и статусу выхода.","meta.communityDescription":"Оценки и одобренные рецензии зрителей Anicast без скрытых спойлеров.","meta.mediaDescription":"Трейлеры, промо-материалы и изображения аниме с подтверждённой атрибуцией прав.","meta.franchisesDescription":"Франшизы аниме на Anicast: связанные сезоны, фильмы и спешлы одной вселенной.",
  "meta.description":"Wiki, библиотека и просмотр аниме","common.login":"Войти","common.retry":"Повторить","common.loadFailed":"Не удалось загрузить данные","common.loadFailedText":"Попробуйте ещё раз. Выбранные параметры сохранены.","common.pagination":"Страницы результатов","common.pageMissing":"На этой странице больше нет записей","common.firstPage":"На первую страницу","catalog.randomFailed":"Не удалось выбрать тайтл. Попробуйте ещё раз.","common.loading":"Загрузка...","common.apiUnavailable":"Сайт временно недоступен","common.apiUnavailableText":"Сервис вернётся через несколько минут — мы уже знаем о проблеме.","common.back":"← Назад","common.next":"Вперёд →","common.save":"Сохранить","common.delete":"Удалить","common.cancel":"Отмена","common.search":"Найти","common.error":"Не удалось выполнить запрос.",
  "nav.main":"Основная навигация","nav.home":"Главная","nav.catalog":"Каталог","nav.schedule":"Расписание","nav.franchises":"Франшизы","nav.community":"Сообщество","nav.profile":"Профиль","nav.notifications":"Уведомления","nav.libraryShort":"Библиотека","nav.library":"МОЯ БИБЛИОТЕКА","nav.watching":"Смотрю","nav.planned":"Запланировано","nav.completed":"Просмотрено","nav.favorites":"Избранное","language.label":"Язык интерфейса",
  "home.title":"Продолжи свой путь","home.subtitle":"Изучай миры, сохраняй личный контекст и возвращайся к просмотру.","home.openCatalog":"Открыть каталог","home.catalogCount":"{count} аниме уже в каталоге",
  "catalog.eyebrow":"КОЛЛЕКЦИЯ ANICAST","catalog.title":"Каталог","catalog.searchLabel":"Поиск по каталогу","catalog.searchPlaceholder":"Название тайтла...","catalog.format":"Формат","catalog.allFormats":"Все форматы","catalog.series":"Сериал","catalog.movie":"Фильм","catalog.special":"Спешл","catalog.status":"Статус выпуска","catalog.anyStatus":"Любой статус","catalog.apply":"Применить","catalog.reset":"Сбросить","catalog.notFound":"Ничего не найдено","catalog.empty":"Каталог пока пуст","catalog.changeFilters":"Попробуй изменить параметры или посмотреть всю коллекцию.","catalog.emptyText":"Скоро здесь появятся тайтлы Anicast.","catalog.resetFilters":"Сбросить фильтры","catalog.page":"Страница {current} из {total}","catalog.found":"Найдено: {count}","catalog.sortLabel":"Сортировка","catalog.sortDefault":"Рекомендуемое","catalog.sortPopular":"По популярности","catalog.sortRecent":"Сначала новые","catalog.sortName":"По алфавиту","catalog.genre":"Жанр","catalog.allGenres":"Все жанры","catalog.random":"Случайный тайтл","catalog.seasonsSeparate":"Показывать сезоны отдельно","catalog.seasonsGrouped":"Группировать по франшизам","card.playableOf":"Доступно {available} из {total} серий","card.playableOfOngoing":"Доступно {available} из {total} серий · выходит","card.playableOnly":"Доступно серий: {available}","card.noPlayable":"Нет доступных серий","card.addToLibrary":"+ В планы","card.removeFromLibrary":"Убрать из библиотеки",
  "status.ongoing":"Выходит","status.finished":"Завершено","status.planned":"Скоро","status.unknown":"Статус уточняется","type.anime":"Аниме","type.movie":"Фильм","type.ova":"OVA","type.special":"Спешл","year.unknown":"Год не указан",
  "auth.loginTitle":"С возвращением","auth.loginText":"Войдите, чтобы сохранять личное состояние между устройствами.","auth.registerTitle":"Личное пространство","auth.registerText":"Создайте аккаунт для синхронизации прогресса, истории и списков.","auth.or":"или","auth.displayName":"Как к вам обращаться","auth.password":"Пароль","auth.passwordHint":"Не менее 10 символов. Не используйте распространённый или полностью цифровой пароль.","auth.wait":"Подождите...","auth.create":"Создать аккаунт","auth.haveAccount":"Уже есть аккаунт?","auth.new":"Впервые в Anicast?","auth.telegram":"Войти через Telegram-бота","auth.telegramPending":"Подтвердите вход в боте...","auth.telegramInstruction":"Нажмите Start в @{bot}, затем вернитесь на эту страницу.","auth.openBot":"Открыть бота повторно","auth.telegramUnavailable":"Вход через Telegram пока не настроен.",
  "account.viewer":"Зритель Anicast","account.logout":"Выйти","account.loading":"Загружаем аккаунт...","account.noSession":"Сессия не найдена","account.noSessionText":"Войдите, чтобы синхронизировать списки и прогресс.","account.home":"На главную",
  "notifications.title":"Telegram-уведомления","notifications.connected":"Подключён @{bot}","notifications.description":"Подключите отдельного бота для уведомлений о новых сериях.","notifications.connect":"Подключить бота","notifications.disconnect":"Отключить","notifications.pending":"Подождите...","notifications.subscriptionsTitle":"Мои подписки","notifications.subscriptionsEmpty":"Вы ещё не подписаны на тайтлы — включите уведомления со страницы тайтла.","notifications.unsubscribe":"Отписаться","notifications.notLinkedWarning":"Есть подписки, но Telegram-бот не подключён — уведомления не будут приходить.","notifications.deliveriesTitle":"Последние уведомления","notifications.deliveryEpisode":"Серия {number}","notifications.status.sent":"доставлено","notifications.status.failed":"не доставлено","notifications.status.pending":"ожидает","notifications.subscribe":"Уведомлять о новых сериях","notifications.subscribed":"Уведомления включены","notifications.guest":"Войдите, чтобы подписаться на новые серии.","notifications.digestTitle":"Дайджест расписания","notifications.digestDescription":"Одно сообщение утром с сериями, выходящими сегодня.","notifications.digestOn":"Дайджест включён","notifications.digestOff":"Дайджест выключен",
  "library.eyebrow":"ЛИЧНОЕ ПРОСТРАНСТВО","library.all":"Все","library.onHold":"Отложено","library.dropped":"Брошено","library.empty":"Здесь пока пусто","library.emptyText":"Добавляйте тайтлы из каталога и распределяйте их по статусам.","library.favorite":"В избранное","library.guest":"Войдите, чтобы сохранить тайтл и синхронизировать библиотеку.",
  "history.recent":"Недавно открывали","history.empty":"История пока пуста","history.emptyText":"Откройте страницу серии из карточки тайтла.","history.watched":"Просмотрено","history.guest":"История доступна после входа","history.guestText":"Мы сохраняем только открытые серии и явные отметки.","history.failed":"Историю не удалось загрузить","history.loading":"Загружаем историю...",
  "episode.number":"Серия {number}","episode.untitled":"Без названия","episode.sources":"Источники","episode.special":"Спецвыпуск {number}","title.specials":"Спецвыпуски","title.specialsWithRun":"Вышли вместе с сериалом","title.specialsSeparate":"Отдельные выпуски","title.specialsSeparateHint":"Вышли не с сериалом, поэтому у каждого своя страница.",
  "source.open":"Смотреть","source.gone":"Источник больше недоступен.","source.playerTitle":"{name}: видеоплеер",
  "report.sent":"Жалоба отправлена","report.guest":"Войдите, чтобы сообщить о проблеме.","report.what":"Что случилось","report.unavailable":"Источник не открывается","report.wrong":"Неверная серия или контент","report.geo":"Недоступно в регионе","report.quality":"Проблема качества","report.other":"Другое","report.comment":"Комментарий","report.details":"Дополнительные детали","report.sending":"Отправляем...","report.send":"Отправить",
  "notes.title":"Заметки","notes.subtitle":"Ваш личный контекст к тайтлам.","notes.personal":"Личная заметка","notes.placeholder":"Мысли, детали и контекст для себя","notes.empty":"Заметок пока нет","notes.emptyText":"Добавьте заметку на странице тайтла.","notes.loading":"Загружаем заметки...","notes.guest":"Войдите, чтобы сохранить личную заметку.",
  "schedule.eyebrow":"КАЛЕНДАРЬ РЕЛИЗОВ","schedule.title":"Расписание","schedule.subtitle":"Ближайшие серии с подтверждёнными датами выхода.","schedule.today":"Сегодня",
  "franchise.eyebrow":"СВЯЗАННЫЕ МИРЫ","franchise.title":"Франшизы","franchise.subtitle":"Серии, фильмы и ответвления, объединённые одной историей.","franchise.empty":"Франшизы пока не добавлены","franchise.label":"ФРАНШИЗА","franchise.unlinked":"Тайтлы пока не связаны","franchise.count":"{count} тайтлов",
  "title.cover":"Обложка: {name}","title.yearUnknown":"Год неизвестен","title.yearsOngoing":"{year} – н.в.","title.episodes":"Серии","title.noEpisodes":"Серии пока не добавлены","title.noEpisodesText":"Мы уточняем данные для этого тайтла.","title.notFound":"Тайтл не найден","title.notFoundText":"Похоже, этот тайтл ещё не появился в каталоге или был перемещён.","community.title":"Сообщество","community.subtitle":"Оценки и одобренные рецензии зрителей Anicast.","community.rating":"Ваша оценка","community.average":"Средняя оценка: {value}","community.noRating":"Оценок пока нет","community.review":"Ваша рецензия","community.reviewPlaceholder":"Минимум 20 символов","community.spoiler":"Содержит спойлеры","community.submit":"Отправить на модерацию","community.pending":"На модерации","community.approved":"Одобрена","community.rejected":"Отклонена","community.publicReviews":"Рецензии зрителей","community.noReviews":"Одобренных рецензий пока нет","community.showSpoiler":"Показать спойлер","community.signIn":"Войдите, чтобы поставить оценку и написать рецензию.","character.title":"Персонажи","character.titles":"Связанные тайтлы","character.descriptionMissing":"Описание персонажа пока не добавлено.","role.protagonist":"Главный герой","role.supporting":"Второстепенный","role.antagonist":"Антагонист","role.cameo":"Камео","media.title":"Медиа","media.subtitle":"Опубликованные материалы с подтверждённой атрибуцией прав.","media.all":"Все","media.image":"Изображения","media.trailer":"Трейлеры","media.promo":"Промо","media.empty":"Опубликованных материалов пока нет","media.credit":"Источник: {credit}","recommendations.title":"Рекомендации","recommendations.subtitle":"Тайтлы на основе жанров вашей библиотеки.","recommendations.empty":"Пока нечего рекомендовать","recommendations.reasonGenres":"По вашим жанрам: {genres}","recommendations.reasonFranchise":"Из вашей франшизы","recommendations.dismiss":"Не интересно","recommendations.dismissed":"Скрыто из рекомендаций: {name}","recommendations.undo":"Отменить","recommendations.dismissFailed":"Не удалось скрыть тайтл, попробуйте ещё раз.","recommendations.guest":"Войдите, чтобы получить персональные рекомендации.","recommendations.loadMore":"Показать ещё","similar.title":"Похожие аниме"
};

const en: Record<string, string> = {
  ...ru,
  "meta.homeTitle":"Anicast — anime catalog, schedule and community","meta.homeDescription":"Explore anime descriptions, characters, upcoming episode schedules, viewer ratings and your personal library.","meta.catalogDescription":"Browse the Anicast anime catalog by title, genre, format and release status.","meta.communityDescription":"Ratings and moderated reviews from Anicast viewers, with spoilers kept under your control.","meta.mediaDescription":"Anime trailers, promotional materials and images with verified rights attribution.","meta.franchisesDescription":"Anime franchises on Anicast: related seasons, films and specials from one universe.",
  "meta.description":"Anime wiki, library and viewing","common.login":"Sign in","common.retry":"Try again","common.loadFailed":"Could not load data","common.loadFailedText":"Try again. Your selected filters are preserved.","common.pagination":"Result pages","common.pageMissing":"This page no longer has any entries","common.firstPage":"Go to the first page","catalog.randomFailed":"Could not pick a title. Try again.","common.loading":"Loading...","common.apiUnavailable":"The site is temporarily unavailable","common.apiUnavailableText":"The service will be back in a few minutes — we already know about it.","common.back":"← Back","common.next":"Next →","common.save":"Save","common.delete":"Delete","common.cancel":"Cancel","common.search":"Search","common.error":"Request failed.",
  "nav.main":"Main navigation","nav.home":"Home","nav.catalog":"Catalog","nav.schedule":"Schedule","nav.franchises":"Franchises","nav.community":"Community","nav.profile":"Profile","nav.notifications":"Notifications","nav.libraryShort":"Library","nav.library":"MY LIBRARY","nav.watching":"Watching","nav.planned":"Planned","nav.completed":"Completed","nav.favorites":"Favorites","language.label":"Interface language",
  "home.title":"Continue your journey","home.subtitle":"Explore worlds, keep your personal context and return to watching.","home.openCatalog":"Open catalog","home.catalogCount":"{count} anime already in the catalog",
  "catalog.eyebrow":"ANICAST COLLECTION","catalog.title":"Catalog","catalog.searchLabel":"Search catalog","catalog.searchPlaceholder":"Title name...","catalog.format":"Format","catalog.allFormats":"All formats","catalog.series":"Series","catalog.movie":"Movie","catalog.special":"Special","catalog.status":"Release status","catalog.anyStatus":"Any status","catalog.apply":"Apply","catalog.reset":"Reset","catalog.notFound":"Nothing found","catalog.empty":"Catalog is empty","catalog.changeFilters":"Change the filters or browse the full collection.","catalog.emptyText":"Anicast titles will appear here soon.","catalog.resetFilters":"Reset filters","catalog.page":"Page {current} of {total}","catalog.found":"Found: {count}","catalog.sortLabel":"Sort by","catalog.sortDefault":"Recommended","catalog.sortPopular":"Most popular","catalog.sortRecent":"Newest first","catalog.sortName":"Alphabetical","catalog.genre":"Genre","catalog.allGenres":"All genres","catalog.random":"Random title","catalog.seasonsSeparate":"Show seasons separately","catalog.seasonsGrouped":"Group franchises","card.playableOf":"{available} of {total} episodes playable","card.playableOfOngoing":"{available} of {total} playable · airing","card.playableOnly":"{available} episodes playable","card.noPlayable":"No playable episodes","card.addToLibrary":"+ My list","card.removeFromLibrary":"Remove from library",
  "status.ongoing":"Airing","status.finished":"Completed","status.planned":"Coming soon","status.unknown":"Status unknown","type.anime":"Anime","type.movie":"Movie","type.ova":"OVA","type.special":"Special","year.unknown":"Year not specified",
  "auth.loginTitle":"Welcome back","auth.loginText":"Sign in to keep your personal state across devices.","auth.registerTitle":"Personal space","auth.registerText":"Create an account to sync progress, history and lists.","auth.or":"or","auth.displayName":"Display name","auth.password":"Password","auth.passwordHint":"At least 10 characters. Avoid common or entirely numeric passwords.","auth.wait":"Please wait...","auth.create":"Create account","auth.haveAccount":"Already have an account?","auth.new":"New to Anicast?","auth.telegram":"Sign in with Telegram bot","auth.telegramPending":"Confirm in the bot...","auth.telegramInstruction":"Press Start in @{bot}, then return to this page.","auth.openBot":"Open bot again","auth.telegramUnavailable":"Telegram sign-in is not configured.",
  "account.viewer":"Anicast viewer","account.logout":"Sign out","account.loading":"Loading account...","account.noSession":"Session not found","account.noSessionText":"Sign in to sync lists and progress.","account.home":"Home",
  "notifications.title":"Telegram notifications","notifications.connected":"Connected to @{bot}","notifications.description":"Connect a separate bot for new episode notifications.","notifications.connect":"Connect bot","notifications.disconnect":"Disconnect","notifications.pending":"Please wait...","notifications.subscriptionsTitle":"My subscriptions","notifications.subscriptionsEmpty":"You have no title subscriptions yet — enable them from a title page.","notifications.unsubscribe":"Unsubscribe","notifications.notLinkedWarning":"You have subscriptions but the Telegram bot is not connected — notifications will not arrive.","notifications.deliveriesTitle":"Recent deliveries","notifications.deliveryEpisode":"Episode {number}","notifications.status.sent":"delivered","notifications.status.failed":"not delivered","notifications.status.pending":"pending","notifications.subscribe":"Notify me about new episodes","notifications.subscribed":"Notifications enabled","notifications.guest":"Sign in to subscribe to new episodes.","notifications.digestTitle":"Schedule digest","notifications.digestDescription":"One morning message with the episodes airing today.","notifications.digestOn":"Digest on","notifications.digestOff":"Digest off",
  "library.eyebrow":"PERSONAL SPACE","library.all":"All","library.onHold":"On hold","library.dropped":"Dropped","library.empty":"Nothing here yet","library.emptyText":"Add titles from the catalog and organize them by status.","library.favorite":"Add to favorites","library.guest":"Sign in to save this title and sync your library.",
  "history.recent":"Recently opened","history.empty":"History is empty","history.emptyText":"Open an episode page from a title.","history.watched":"Watched","history.guest":"History is available after sign-in","history.guestText":"We only save opened episodes and explicit marks.","history.failed":"Could not load history","history.loading":"Loading history...",
  "episode.number":"Episode {number}","episode.untitled":"Untitled","episode.sources":"Sources","episode.special":"Special {number}","title.specials":"Specials","title.specialsWithRun":"Aired with the series","title.specialsSeparate":"Released separately","title.specialsSeparateHint":"These did not air with the series, so each has its own page.",
  "source.open":"Watch","source.gone":"Source is no longer available.","source.playerTitle":"{name}: video player",
  "report.sent":"Report sent","report.guest":"Sign in to report a problem.","report.what":"What happened","report.unavailable":"Source does not open","report.wrong":"Wrong episode or content","report.geo":"Unavailable in region","report.quality":"Quality problem","report.other":"Other","report.comment":"Comment","report.details":"Additional details","report.sending":"Sending...","report.send":"Send",
  "notes.title":"Notes","notes.subtitle":"Your personal context for titles.","notes.personal":"Personal note","notes.placeholder":"Thoughts, details and context for yourself","notes.empty":"No notes yet","notes.emptyText":"Add a note on a title page.","notes.loading":"Loading notes...","notes.guest":"Sign in to save a personal note.",
  "schedule.eyebrow":"RELEASE CALENDAR","schedule.title":"Schedule","schedule.subtitle":"Upcoming episodes with confirmed release dates.","schedule.today":"Today",
  "franchise.eyebrow":"CONNECTED WORLDS","franchise.title":"Franchises","franchise.subtitle":"Series, movies and spin-offs connected by one story.","franchise.empty":"No franchises yet","franchise.label":"FRANCHISE","franchise.unlinked":"No titles linked yet","franchise.count":"{count} titles",
  "title.cover":"Cover: {name}","title.yearUnknown":"Year unknown","title.yearsOngoing":"{year} – present","title.episodes":"Episodes","title.noEpisodes":"No episodes added yet","title.noEpisodesText":"We are verifying this title's data.","title.notFound":"Title not found","title.notFoundText":"This title may not be in the catalog yet or may have moved.","community.title":"Community","community.subtitle":"Ratings and approved reviews from Anicast viewers.","community.rating":"Your rating","community.average":"Average rating: {value}","community.noRating":"No ratings yet","community.review":"Your review","community.reviewPlaceholder":"At least 20 characters","community.spoiler":"Contains spoilers","community.submit":"Submit for moderation","community.pending":"Pending moderation","community.approved":"Approved","community.rejected":"Rejected","community.publicReviews":"Viewer reviews","community.noReviews":"No approved reviews yet","community.showSpoiler":"Show spoiler","community.signIn":"Sign in to rate and write a review.","character.title":"Characters","character.titles":"Related titles","character.descriptionMissing":"Character description is not available.","role.protagonist":"Protagonist","role.supporting":"Supporting","role.antagonist":"Antagonist","role.cameo":"Cameo","media.title":"Media","media.subtitle":"Published materials with verified rights attribution.","media.all":"All","media.image":"Images","media.trailer":"Trailers","media.promo":"Promo","media.empty":"No published media yet","media.credit":"Source: {credit}","recommendations.title":"Recommendations","recommendations.subtitle":"Titles based on genres in your library.","recommendations.empty":"Nothing to recommend yet","recommendations.reasonGenres":"Based on your genres: {genres}","recommendations.reasonFranchise":"From your franchise","recommendations.dismiss":"Not interested","recommendations.dismissed":"Hidden from recommendations: {name}","recommendations.undo":"Undo","recommendations.dismissFailed":"Could not hide the title, please try again.","recommendations.guest":"Sign in to get personal recommendations.","recommendations.loadMore":"Show more","similar.title":"Similar anime"
};

Object.assign(ru, {
  "nav.collections":"Коллекции",
  "collections.title":"Мои коллекции","collections.subtitle":"Собирайте тематические подборки, настраивайте порядок и делитесь публичной ссылкой.","collections.manage":"Управление коллекцией","collections.manageText":"Измените описание, доступ и порядок тайтлов.",
  "collections.name":"Название","collections.namePlaceholder":"Например, Аниме для дождливого вечера","collections.slug":"Адрес коллекции","collections.slugPlaceholder":"rainy-evening","collections.slugHint":"Строчные латинские буквы, цифры и дефисы.","collections.description":"Описание","collections.visibility":"Сделать коллекцию публичной","collections.public":"Публичная","collections.private":"Приватная","collections.share":"Ссылка:","collections.create":"Создать коллекцию","collections.creating":"Создаём...","collections.saving":"Сохраняем...",
  "collections.loading":"Загружаем коллекции...","collections.empty":"Коллекций пока нет","collections.emptyText":"Создайте первую подборку и добавляйте тайтлы с их страниц.","collections.noDescription":"Описание пока не добавлено.","collections.itemCount":"Тайтлов: {count}","collections.titles":"Тайтлы","collections.noTitles":"В коллекции пока нет тайтлов","collections.addFromTitle":"Добавьте их на странице нужного тайтла.",
  "collections.guest":"Войдите, чтобы создавать и редактировать свои коллекции.","collections.loadError":"Не удалось загрузить коллекции.","collections.saveError":"Не удалось сохранить коллекцию.","collections.deleteError":"Не удалось удалить коллекцию.","collections.itemError":"Не удалось изменить состав коллекции.","collections.reorderError":"Не удалось изменить порядок тайтлов.","collections.deleteConfirm":"Удалить эту коллекцию? Это действие нельзя отменить.",
  "collections.moveUp":"Переместить выше","collections.moveDown":"Переместить ниже","collections.remove":"Убрать","collections.addTitle":"Добавить в коллекцию","collections.added":"Добавлено","collections.createFirst":"Создать первую коллекцию","collections.publicLabel":"ПУБЛИЧНАЯ КОЛЛЕКЦИЯ","collections.by":"Автор: {name}","collections.owner":"пользователь Anicast",
  "notFound.title":"Страница потерялась","notFound.text":"Похоже, такой страницы нет или она была перемещена.","notFound.mascotAlt":"Растерянная аниме-девочка с котёнком держит записку «Страница потерялась»","notFound.toCharacters":"Персонажи","character.notFound":"Персонаж не найден","character.notFoundText":"Такого персонажа нет в каталоге — возможно, ссылка устарела.",
});

Object.assign(ru, {
  // Расписание: дни недели, статусы выхода и время в часовом поясе зрителя.
  "schedule.weekdays":"Дни недели","schedule.today":"Сегодня","schedule.tomorrow":"Завтра","schedule.yesterday":"Вчера",
  "schedule.released":"Уже вышла","schedule.airingNow":"Сейчас","schedule.inMinutes":"Через {count} мин","schedule.inHours":"Через {count} ч","schedule.inHoursMinutes":"Через {hours} ч {minutes} мин","schedule.laterToday":"Сегодня позже","schedule.upcoming":"Ожидается","schedule.timeUnknown":"Время не подтверждено",
  "schedule.episodesCount":"Серий: {count}","schedule.noEpisodes":"В этот день релизов нет","schedule.noEpisodesText":"Выберите другой день недели или откройте каталог.","schedule.timezoneNote":"Время показано в вашем часовом поясе.",
  "schedule.prevWeek":"← Предыдущая неделя","schedule.nextWeek":"Следующая неделя →","schedule.thisWeek":"Текущая неделя","schedule.weekRange":"{from} — {to}",
  // Header и меню пользователя.
  "nav.openMenu":"Открыть меню пользователя","nav.closeMenu":"Закрыть меню","nav.register":"Регистрация","nav.myAccount":"Мой аккаунт","nav.logout":"Выйти","nav.openSearch":"Открыть поиск","nav.closeSearch":"Закрыть поиск",
  // Глобальный поиск.
  "search.title":"Поиск","search.placeholder":"Аниме, персонажи, франшизы...","search.hint":"Введите не менее {count} символов","search.loading":"Ищем...","search.empty":"Ничего не найдено","search.emptyText":"Проверьте написание или откройте каталог целиком.","search.error":"Поиск временно недоступен","search.errorText":"Повторите запрос через несколько секунд.","search.titles":"Аниме","search.characters":"Персонажи","search.franchises":"Франшизы","search.allResults":"Показать все результаты",
  // Страница тайтла: действия и вкладки.
  "title.continueEpisode":"Продолжить: серия {number}","watch.title":"Смотреть","watch.prev":"Предыдущая серия","watch.next":"Следующая серия","title.favorite":"Избранное","title.favoriteActive":"В избранном","title.actionsGuest":"Войдите, чтобы сохранять прогресс.","title.addToWatching":"Начать смотреть",
  "title.tabOverview":"Обзор","title.tabEpisodes":"Серии","title.tabCharacters":"Персонажи и авторы","title.tabCommunity":"Сообщество","title.tabNotes":"Заметки","title.description":"Описание","title.franchiseLabel":"Франшиза","title.noCast":"Персонажи пока не добавлены","title.charactersMain":"Главные персонажи","title.authorsMain":"Главные авторы","title.characters":"Персонажи","title.authors":"Авторы","title.noAuthors":"Сведения об авторах уточняются","similar.moreInGenre":"Ещё в жанре «{genre}» →",
  // Главная страница.
  "home.continueWatching":"Продолжить просмотр","home.airingNow":"Сейчас выходит","home.airingNowText":"Тайтлы с подтверждёнными датами новых серий.","home.popular":"Чаще добавляют","home.popularText":"Тайтлы, которые чаще всего добавляют в библиотеку.","home.newest":"Новинки","home.newestText":"Самые свежие годы выпуска в каталоге.","home.showAll":"Смотреть все →","home.sectionEmpty":"Пока нет данных для этого блока","rail.scrollBack":"Листать полку назад","rail.scrollForward":"Листать полку вперёд","franchise.titlesCount":"Тайтлов: {count}"
});

Object.assign(ru, {
  
});

Object.assign(ru, {
  // Главная: hero-прогресс и элементы полки.
  "home.removeHistory":"Убрать из истории","home.removeHistoryFailed":"Не удалось убрать тайтл из истории.",
  "home.shelfMeta.episode":"{count} серия","home.shelfMeta.few":"{count} серии","home.shelfMeta.many":"{count} серий",
  "footer.about":"О проекте Anicast","footer.aboutText":"Anicast — независимый каталог аниме: расписания, оценки и личная библиотека.","footer.support":"Поддержка",
});

Object.assign(en, {
  "schedule.weekdays":"Weekdays","schedule.today":"Today","schedule.tomorrow":"Tomorrow","schedule.yesterday":"Yesterday",
  "schedule.released":"Released","schedule.airingNow":"Now","schedule.inMinutes":"In {count} min","schedule.inHours":"In {count} h","schedule.inHoursMinutes":"In {hours} h {minutes} min","schedule.laterToday":"Later today","schedule.upcoming":"Upcoming","schedule.timeUnknown":"Time not confirmed",
  "schedule.episodesCount":"Episodes: {count}","schedule.noEpisodes":"No releases on this day","schedule.noEpisodesText":"Pick another weekday or open the catalog.","schedule.timezoneNote":"Times are shown in your timezone.",
  "schedule.prevWeek":"← Previous week","schedule.nextWeek":"Next week →","schedule.thisWeek":"Current week","schedule.weekRange":"{from} — {to}",
  "nav.openMenu":"Open user menu","nav.closeMenu":"Close menu","nav.register":"Sign up","nav.myAccount":"My account","nav.logout":"Sign out","nav.openSearch":"Open search","nav.closeSearch":"Close search",
  "search.title":"Search","search.placeholder":"Anime, characters, franchises...","search.hint":"Type at least {count} characters","search.loading":"Searching...","search.empty":"Nothing found","search.emptyText":"Check the spelling or browse the full catalog.","search.error":"Search is temporarily unavailable","search.errorText":"Please retry in a few seconds.","search.titles":"Anime","search.characters":"Characters","search.franchises":"Franchises","search.allResults":"Show all results",
  "title.continueEpisode":"Continue: episode {number}","watch.title":"Watch","watch.prev":"Previous episode","watch.next":"Next episode","title.favorite":"Favorite","title.favoriteActive":"In favorites","title.actionsGuest":"Sign in to keep your progress.","title.addToWatching":"Start watching",
  "title.tabOverview":"Overview","title.tabEpisodes":"Episodes","title.tabCharacters":"Characters & creators","title.tabCommunity":"Community","title.tabNotes":"Notes","title.description":"Description","title.franchiseLabel":"Franchise","title.noCast":"No characters added yet","title.charactersMain":"Main characters","title.authorsMain":"Main creators","title.characters":"Characters","title.authors":"Creators","title.noAuthors":"Creator details are being verified","similar.moreInGenre":"More in {genre} →",
  "home.continueWatching":"Continue watching","home.airingNow":"Airing now","home.airingNowText":"Titles with confirmed upcoming episode dates.","home.popular":"Most added","home.popularText":"Titles most often added to libraries.","home.newest":"Newest","home.newestText":"The freshest release years in the catalog.","home.showAll":"See all →","home.sectionEmpty":"No data for this block yet","rail.scrollBack":"Scroll the shelf back","rail.scrollForward":"Scroll the shelf forward","franchise.titlesCount":"Titles: {count}"
});

Object.assign(en, {
  
});

Object.assign(en, {
  "home.removeHistory":"Remove from history","home.removeHistoryFailed":"Could not remove the title from history.",
  "home.shelfMeta.episode":"{count} episode","home.shelfMeta.few":"{count} episodes","home.shelfMeta.many":"{count} episodes",
  "footer.about":"About Anicast","footer.aboutText":"Anicast is an independent anime catalog: schedules, ratings and a personal library.","footer.support":"Support",
});

Object.assign(ru, {
  "watch.sourceFailed":"Эта озвучка сейчас не открывается. Повторите или выберите другую.",
  "creator.eyebrow":"АВТОР","creator.works":"Работы","creator.worksCount":"Работ в каталоге: {count}",
  "creator.metaDescription":"{name} в каталоге Anicast: работ в каталоге — {count}."
});

Object.assign(en, {
  "watch.sourceFailed":"This voice track is unavailable right now. Retry or choose another one.",
  "creator.eyebrow":"CREATOR","creator.works":"Works","creator.worksCount":"Works in catalog: {count}",
  "creator.metaDescription":"{name} on Anicast: {count} works in the catalog."
});

Object.assign(en, {
  "nav.collections":"Collections",
  "collections.title":"My collections","collections.subtitle":"Build themed lists, arrange titles and share a public link.","collections.manage":"Manage collection","collections.manageText":"Edit its description, visibility and title order.",
  "collections.name":"Name","collections.namePlaceholder":"For example, Anime for a rainy evening","collections.slug":"Collection URL","collections.slugPlaceholder":"rainy-evening","collections.slugHint":"Lowercase Latin letters, numbers and hyphens.","collections.description":"Description","collections.visibility":"Make this collection public","collections.public":"Public","collections.private":"Private","collections.share":"Share link:","collections.create":"Create collection","collections.creating":"Creating...","collections.saving":"Saving...",
  "collections.loading":"Loading collections...","collections.empty":"No collections yet","collections.emptyText":"Create your first list and add titles from their pages.","collections.noDescription":"No description yet.","collections.itemCount":"Titles: {count}","collections.titles":"Titles","collections.noTitles":"This collection has no titles yet","collections.addFromTitle":"Add them from a title page.",
  "collections.guest":"Sign in to create and manage your collections.","collections.loadError":"Could not load collections.","collections.saveError":"Could not save the collection.","collections.deleteError":"Could not delete the collection.","collections.itemError":"Could not update the collection titles.","collections.reorderError":"Could not reorder the titles.","collections.deleteConfirm":"Delete this collection? This action cannot be undone.",
  "collections.moveUp":"Move up","collections.moveDown":"Move down","collections.remove":"Remove","collections.addTitle":"Add to collection","collections.added":"Added","collections.createFirst":"Create your first collection","collections.publicLabel":"PUBLIC COLLECTION","collections.by":"By {name}","collections.owner":"Anicast user",
  "notFound.title":"Page got lost","notFound.text":"This page does not exist or may have moved.","notFound.mascotAlt":"A puzzled anime girl with a kitten holding a 'Page got lost' note","notFound.toCharacters":"Characters","character.notFound":"Character not found","character.notFoundText":"This character is not in the catalog — the link may be outdated.",
});

Object.assign(ru, {
  // Личный кабинет: сводка, разделы и подсказки.
  "account.title":"Личный кабинет","account.noEmail":"Email не указан",
  "account.statsLabel":"Статистика библиотеки","account.sections":"Личные разделы",
  "account.sectionLibraryHint":"{count} в списке",
  "account.recentNotes":"Последние заметки","account.collectionsHeading":"Мои коллекции","account.recommendedHeading":"Вам может понравиться",
  "account.watchingHeading":"Смотрю","account.plannedHeading":"В планах","account.newEpisodesHeading":"Новые серии",
  "home.heroEyebrow":"Продолжить просмотр","home.continueEpisode":"Продолжить серию {number}",
  "profile.tabOverview":"Обзор","profile.tabLibrary":"Библиотека","profile.tabHistory":"История",
  "profile.statsHours":"Часы","profile.statsAvgRating":"Средняя оценка","profile.genreToCatalog":"Открыть в каталоге",
  "profile.favoriteGenres":"Любимые жанры",
  "profile.activityTitle":"Активность просмотров","profile.activitySubtitle":"Отмеченные серии за последние 12 месяцев","profile.activityLabel":"График активности просмотров по месяцам","profile.activityCount":"Серий: {count}",
  "profile.guest":"Гость",
  // Настройки: отдельный приватный маршрут (design freeze §17).
  "settings.title":"Настройки","settings.subtitle":"Публичный профиль, уведомления и язык интерфейса.",
  // Представления внутри вкладки «Библиотека».
  "library.viewSwitch":"Представление библиотеки","library.filters":"Фильтры библиотеки","library.viewTitles":"Тайтлы","library.viewCollections":"Коллекции",
  "notes.saving":"Сохраняем...","notes.deleting":"Удаляем...","notes.saved":"Заметка сохранена","notes.deleted":"Заметка удалена",
  // Единый сценарий просмотра: озвучка, доступные серии и плеер.
  "watch.navigation":"Выбор озвучки и серии","watch.voice":"Озвучка или субтитры","watch.noVoice":"Доступных озвучек пока нет",
  "watch.voiceCoverage":"Доступно: {coverage}",
  "watch.coverageUnknown":"покрытие уточняется","watch.coverageEmpty":"нет серий","watch.coverageSingle":"серия {number}","watch.coverageRanges":"серии {ranges}",
  "watch.coverageExcept":"серии {first}–{last}, кроме {missing}","watch.coverageWithGaps":"{count} эп. · {first}–{last}, с пропусками",
  
  "watch.voiceUnavailable":"Серии {number} нет в варианте «{name}». Выберите доступную серию.",
  "watch.playEpisode":"Смотреть серию {number}","watch.noPlayer":"Для этой серии нет доступного плеера",
  "watch.chooseAvailableEpisode":"Выберите серию из списка или другую озвучку.",
  "watch.noPlayableTitle":"Просмотр пока недоступен","watch.noPlayableText":"Для этого тайтла пока нет доступного плеера.",
  "watch.noEpisodesTitle":"Просмотр пока недоступен","watch.noEpisodesPlanned":"Серии появятся здесь после выхода.","watch.noEpisodesText":"Данные о сериях и просмотре уточняются.",
  "watch.loadFailed":"Не удалось загрузить плеер","watch.loadFailedText":"Информация о тайтле доступна. Попробуйте загрузить просмотр ещё раз.",
  "watch.navigationUnavailable":"Список серий временно неполный. Плеер можно использовать, а навигацию — обновить.",
  "watch.episodeRequestCorrected":"Указанная серия не найдена. Открыта доступная серия {number}.","watch.voiceRequestCorrected":"Указанная озвучка недоступна. Выбран доступный вариант.",
  "watch.episodeRange":"Диапазон серий","watch.episodeRangeOption":"Серии {first}–{last}","watch.episodeActions":"Действия с серией","watch.titleActions":"Действия с просмотром",
  "watch.progressAutomatic":"Прогресс сохраняется автоматически","watch.progressLoading":"Загружаем прогресс...","watch.progressSaving":"Сохраняем прогресс...","watch.progressCompleted":"Серия просмотрена","watch.progressError":"Не удалось сохранить прогресс","watch.progressGuest":"Войдите, чтобы сохранять прогресс",
  
  "watch.currentEpisode":"Сейчас","watch.availableEpisodeCount":"Доступно серий: {count}",
  "watch.episodeSearch":"Поиск серии","watch.episodeSearchPlaceholder":"Номер серии","watch.episodeSearchEmpty":"Серии с таким номером здесь нет.","watch.sectionTitle":"Просмотр","watch.watchedMark":"Просмотрено",
  "watch.episodeDialogTitle":"Выбор серии","watch.closeChooser":"Закрыть выбор",
  "watch.voiceOptionsTitle":"Озвучка и субтитры",
  "watch.voiceGroup.dub":"Озвучка","watch.voiceGroup.sub":"Субтитры","watch.voiceGroup.raw":"Оригинал",
});

Object.assign(en, {
  "account.title":"Account","account.noEmail":"No email provided",
  "account.statsLabel":"Library statistics","account.sections":"Personal sections",
  "account.sectionLibraryHint":"{count} in list",
  "account.recentNotes":"Recent notes","account.collectionsHeading":"My collections","account.recommendedHeading":"You may also like",
  "account.watchingHeading":"Watching","account.plannedHeading":"Planned","account.newEpisodesHeading":"New episodes",
  "home.heroEyebrow":"Continue watching","home.continueEpisode":"Continue episode {number}",
  "profile.tabOverview":"Overview","profile.tabLibrary":"Library","profile.tabHistory":"History",
  "profile.statsHours":"Hours","profile.statsAvgRating":"Average rating","profile.genreToCatalog":"Show in catalog",
  "profile.favoriteGenres":"Favorite genres",
  "profile.activityTitle":"Viewing activity","profile.activitySubtitle":"Episodes marked during the last 12 months","profile.activityLabel":"Monthly viewing activity chart","profile.activityCount":"Episodes: {count}",
  "profile.guest":"Guest",
  "settings.title":"Settings","settings.subtitle":"Public profile, notifications and interface language.",
  "library.viewSwitch":"Library view","library.filters":"Library filters","library.viewTitles":"Titles","library.viewCollections":"Collections",
  "notes.saving":"Saving...","notes.deleting":"Deleting...","notes.saved":"Note saved","notes.deleted":"Note deleted",
  "watch.navigation":"Voice-over and episode navigation","watch.voice":"Voice-over or subtitles","watch.noVoice":"No playable voice-overs yet",
  "watch.voiceCoverage":"Available: {coverage}",
  "watch.coverageUnknown":"coverage pending","watch.coverageEmpty":"no episodes","watch.coverageSingle":"episode {number}","watch.coverageRanges":"episodes {ranges}",
  "watch.coverageExcept":"episodes {first}–{last}, except {missing}","watch.coverageWithGaps":"{count} eps · {first}–{last}, with gaps",
  
  "watch.voiceUnavailable":"Episode {number} is not available in “{name}”. Choose an available episode.",
  "watch.playEpisode":"Watch episode {number}","watch.noPlayer":"No playable source for this episode",
  "watch.chooseAvailableEpisode":"Choose an episode from the list or another voice-over.",
  "watch.noPlayableTitle":"Playback is not available yet","watch.noPlayableText":"There is no playable source for this title yet.",
  "watch.noEpisodesTitle":"Playback is not available yet","watch.noEpisodesPlanned":"Episodes will appear here after release.","watch.noEpisodesText":"Episode and playback details are being verified.",
  "watch.loadFailed":"Could not load the player","watch.loadFailedText":"Title information is still available. Try loading playback again.",
  "watch.navigationUnavailable":"The episode list is temporarily incomplete. You can use the player or refresh navigation.",
  "watch.episodeRequestCorrected":"That episode was not found. Available episode {number} is open.","watch.voiceRequestCorrected":"That voice-over is unavailable. An available option was selected.",
  "watch.episodeRange":"Episode range","watch.episodeRangeOption":"Episodes {first}–{last}","watch.episodeActions":"Episode actions","watch.titleActions":"Viewing actions",
  "watch.progressAutomatic":"Progress is saved automatically","watch.progressLoading":"Loading progress...","watch.progressSaving":"Saving progress...","watch.progressCompleted":"Episode watched","watch.progressError":"Could not save progress","watch.progressGuest":"Sign in to save your progress",
  
  "watch.currentEpisode":"Now","watch.availableEpisodeCount":"Episodes available: {count}",
  "watch.episodeSearch":"Search episodes","watch.episodeSearchPlaceholder":"Episode number","watch.episodeSearchEmpty":"There is no episode with that number here.","watch.sectionTitle":"Playback","watch.watchedMark":"Watched",
  "watch.episodeDialogTitle":"Choose an episode","watch.closeChooser":"Close chooser",
  "watch.voiceOptionsTitle":"Voice-over and subtitles",
  "watch.voiceGroup.dub":"Voice-over","watch.voiceGroup.sub":"Subtitles","watch.voiceGroup.raw":"Original",
});

Object.assign(ru, {
  
  "footer.navigation":"Навигация в подвале сайта",
  "social.eyebrow":"СООБЩЕСТВО ANICAST",
  "social.settingsTitle":"Публичный профиль",
  "social.settingsDescription":"Настройте имя и краткое описание. Профиль появится в сообществе только после вашего явного согласия.",
  "social.displayName":"Имя в сообществе",
  "social.bio":"О себе",
  "social.bioPlaceholder":"Например: любимые жанры, студии и истории, которые хочется обсуждать.",
  "social.publicProfile":"Показывать публичный профиль",
  "social.publicProfileHint":"Будут видны только имя, описание, одобренные рецензии и коллекции, которые вы сами сделали публичными.",
  "social.profileSaved":"Профиль сохранён",
  "social.openProfile":"Открыть профиль",
  "social.publicBadge":"ПУБЛИЧНЫЙ ПРОФИЛЬ",
  "social.collections":"Коллекции",
  "social.reviews":"Рецензии",
  "social.publicCollections":"Публичные коллекции",
  "social.publishedReviews":"Опубликованные рецензии",
  "social.noPublicCollections":"Публичных коллекций пока нет.",
  "social.noPublishedReviews":"Опубликованных рецензий пока нет.",
  "social.profileDescription":"Профиль {name} в сообществе Anicast: публичные коллекции и рецензии.",
  "social.follow":"Подписаться",
  "social.unfollow":"Отписаться",
  "social.followError":"Не удалось изменить подписку. Попробуйте ещё раз.",
  "social.signInToFollow":"Войти, чтобы подписаться",
  "social.editOwnProfile":"Настроить профиль",
  "social.followers":"Подписчики",
  "social.followersCount":"Подписчиков: {count}",
  "social.feedTabs":"Разделы ленты сообщества",
  "social.feedAll":"Все рецензии",
  "social.feedFollowing":"Мои подписки",
  "social.feedEmpty":"В ленте подписок пока пусто",
  "social.feedEmptyHint":"Подпишитесь на интересные публичные профили — их новые рецензии и обновления коллекций появятся здесь.",
  "social.collectionUpdated":"Коллекция обновлена",
  "social.reviewPublished":"Рецензия опубликована",
});

Object.assign(en, {
  
  "footer.navigation":"Footer navigation",
  "social.eyebrow":"ANICAST COMMUNITY",
  "social.settingsTitle":"Public profile",
  "social.settingsDescription":"Choose your community name and short bio. Your profile appears only after you explicitly make it public.",
  "social.displayName":"Community name",
  "social.bio":"About you",
  "social.bioPlaceholder":"For example: favorite genres, studios and stories you enjoy discussing.",
  "social.publicProfile":"Show my public profile",
  "social.publicProfileHint":"Only your name, bio, approved reviews and collections you explicitly made public will be visible.",
  "social.profileSaved":"Profile saved",
  "social.openProfile":"Open profile",
  "social.publicBadge":"PUBLIC PROFILE",
  "social.collections":"Collections",
  "social.reviews":"Reviews",
  "social.publicCollections":"Public collections",
  "social.publishedReviews":"Published reviews",
  "social.noPublicCollections":"No public collections yet.",
  "social.noPublishedReviews":"No published reviews yet.",
  "social.profileDescription":"{name}'s Anicast community profile, public collections and reviews.",
  "social.follow":"Follow",
  "social.unfollow":"Unfollow",
  "social.followError":"Could not update the follow. Please try again.",
  "social.signInToFollow":"Sign in to follow",
  "social.editOwnProfile":"Edit profile",
  "social.followers":"Followers",
  "social.followersCount":"Followers: {count}",
  "social.feedTabs":"Community feed sections",
  "social.feedAll":"All reviews",
  "social.feedFollowing":"Following",
  "social.feedEmpty":"Your following feed is empty",
  "social.feedEmptyHint":"Follow public profiles you enjoy. Their new reviews and collection updates will appear here.",
  "social.collectionUpdated":"Collection updated",
  "social.reviewPublished":"Review published",
});

Object.assign(ru, {
  // Восстановление доступа: сброс пароля, подтверждение адреса, сессии.
  "auth.forgot":"Забыли пароль?",
  "auth.forgotTitle":"Восстановление доступа",
  "auth.forgotText":"Укажите адрес, на который зарегистрирован аккаунт. Мы отправим ссылку для смены пароля.",
  "auth.forgotSubmit":"Отправить ссылку",
  // Формулировка намеренно не раскрывает, есть ли такой аккаунт.
  "auth.forgotSent":"Если аккаунт с таким адресом существует, письмо со ссылкой уже отправлено.",
  "auth.forgotSentHint":"Ссылка действует сутки и работает один раз. Проверьте папку «Спам», если письма нет через несколько минут.",
  "auth.backToLogin":"Вернуться к входу",
  "auth.resetTitle":"Новый пароль",
  "auth.resetText":"Придумайте пароль, которого ещё не было в других сервисах.",
  "auth.resetSubmit":"Сохранить пароль",
  "auth.resetNoToken":"Ссылка неполная. Откройте её из письма целиком или запросите новую.",
  "auth.resetDone":"Пароль изменён, вы вошли в аккаунт. Остальные сессии завершены.",
  "auth.resetRequestNew":"Запросить новую ссылку",
  "auth.newPassword":"Новый пароль",
  "auth.repeatPassword":"Повторите пароль",
  "auth.passwordMismatch":"Пароли не совпадают.",
  "auth.verifyTitle":"Подтверждение адреса",
  "auth.verifyPending":"Проверяем ссылку...",
  "auth.verifyDone":"Адрес подтверждён. Теперь по нему можно восстановить пароль.",
  "auth.verifyFailed":"Ссылка недействительна или устарела.",
  "auth.toAccount":"В личный кабинет",
  // Настройки безопасности.
  "security.title":"Пароль и безопасность",
  "security.description":"Смена пароля завершает сессии на других устройствах. Текущее устройство останется в аккаунте.",
  "security.currentPassword":"Текущий пароль",
  "security.setPasswordTitle":"Пароль для входа",
  "security.setPasswordDescription":"Аккаунт создан через Telegram. Задайте пароль, чтобы входить и по email.",
  "security.setPassword":"Задать пароль",
  "security.changePassword":"Сменить пароль",
  "security.passwordChanged":"Пароль изменён",
  "security.passwordChangedSessions":"Пароль изменён. Завершено сессий: {count}",
  "security.emailUnverified":"Адрес не подтверждён",
  "security.emailUnverifiedHint":"Пока адрес не подтверждён, восстановить пароль по нему нельзя.",
  "security.sendVerification":"Отправить письмо",
  "security.verificationSent":"Письмо отправлено. Откройте ссылку из него.",
  "security.emailVerified":"Адрес подтверждён",
  "security.noEmail":"К аккаунту не привязан email — вход только через Telegram.",
  "security.sessionsTitle":"Активные сессии",
  "security.sessionsDescription":"Сессия живёт 30 дней и продлевается при использовании. Если вы входили с чужого устройства, завершите остальные сессии.",
  "security.revokeSessions":"Завершить другие сессии",
  "security.sessionsRevoked":"Завершено сессий: {count}",
  "security.sessionsNone":"Других активных сессий не найдено",
  "security.mailUnavailable":"Отправка писем пока не настроена — обратитесь в поддержку.",
});

Object.assign(en, {
  "auth.forgot":"Forgot your password?",
  "auth.forgotTitle":"Account recovery",
  "auth.forgotText":"Enter the address your account uses. We will send a link to set a new password.",
  "auth.forgotSubmit":"Send the link",
  "auth.forgotSent":"If an account with that address exists, a message with the link is already on its way.",
  "auth.forgotSentHint":"The link is valid for one day and works once. Check your spam folder if nothing arrives within a few minutes.",
  "auth.backToLogin":"Back to sign-in",
  "auth.resetTitle":"New password",
  "auth.resetText":"Pick a password you have not used on other services.",
  "auth.resetSubmit":"Save the password",
  "auth.resetNoToken":"The link is incomplete. Open it from the email in full or request a new one.",
  "auth.resetDone":"Password changed and you are signed in. All other sessions were ended.",
  "auth.resetRequestNew":"Request a new link",
  "auth.newPassword":"New password",
  "auth.repeatPassword":"Repeat the password",
  "auth.passwordMismatch":"The passwords do not match.",
  "auth.verifyTitle":"Address confirmation",
  "auth.verifyPending":"Checking the link...",
  "auth.verifyDone":"Address confirmed. Password recovery to it is now possible.",
  "auth.verifyFailed":"This link is invalid or has expired.",
  "auth.toAccount":"Go to account",
  "security.title":"Password and security",
  "security.description":"Changing the password ends sessions on other devices. This device stays signed in.",
  "security.currentPassword":"Current password",
  "security.setPasswordTitle":"Sign-in password",
  "security.setPasswordDescription":"This account was created through Telegram. Set a password to sign in with email as well.",
  "security.setPassword":"Set a password",
  "security.changePassword":"Change password",
  "security.passwordChanged":"Password changed",
  "security.passwordChangedSessions":"Password changed. Sessions ended: {count}",
  "security.emailUnverified":"Address not confirmed",
  "security.emailUnverifiedHint":"Until the address is confirmed, it cannot be used to recover the password.",
  "security.sendVerification":"Send the email",
  "security.verificationSent":"Email sent. Open the link inside it.",
  "security.emailVerified":"Address confirmed",
  "security.noEmail":"This account has no email — sign-in works through Telegram only.",
  "security.sessionsTitle":"Active sessions",
  "security.sessionsDescription":"A session lasts 30 days and renews while in use. If you signed in on someone else's device, end the other sessions.",
  "security.revokeSessions":"End other sessions",
  "security.sessionsRevoked":"Sessions ended: {count}",
  "security.sessionsNone":"No other active sessions were found",
  "security.mailUnavailable":"Email delivery is not configured yet — please contact support.",
});

Object.assign(ru, {
  "watch.reloadPlayer": "Перезапустить плеер",
  "watch.loadingSlow": "Плеер загружается дольше обычного. Можно подождать, повторить загрузку или выбрать другую озвучку.",
});
Object.assign(en, {
  "watch.reloadPlayer": "Reload player",
  "watch.loadingSlow": "The player is taking longer than usual. Wait, retry loading or choose another voice-over.",
});

Object.assign(ru, {
  // Главная: честное имя полки популярности и релизные полки.
  "home.popular":"Чаще добавляют","home.popularText":"Тайтлы, которые чаще всего добавляют в библиотеку.",
  "home.recentEpisodes":"Новые серии","home.recentEpisodesText":"Серии, вышедшие за последнюю неделю.","home.today":"Сегодня","home.moreEpisodes":"ещё {count}",
  "home.nextEpisodeAt":"Следующая: {date}",
  // Страница тайтла: один синопсис, одна строка метаданных, одна система списков.
  "title.otherNames":"Другие названия","title.ratingCountOne":"{count} оценка","title.ratingCountFew":"{count} оценки","title.ratingCountMany":"{count} оценок",
  "title.synopsisMore":"Подробнее",
  "title.notInList":"Не в списке","title.listLabel":"Статус просмотра","title.minutesValue":"{minutes} мин",
  "title.watchOrder":"Порядок просмотра","title.watchOrderHint":"Хронология франшизы: смотрите слева направо.",
  "title.allCharacters":"Все персонажи",
  "report.videoProblem":"Проблема с видео",
  // Плеер: автопереход и подписанные селекторы озвучки.
  "watch.autoplayNext":"Следующая серия через {seconds}…","watch.autoplayCancel":"Отмена",
  "watch.voiceNone":"Нет",
  // Профиль: компактная статистика и подписи графика.
  "profile.activityTotal":"{count} серий за 12 месяцев",
});
Object.assign(en, {
  "home.popular":"Most added","home.popularText":"Titles most often added to libraries.",
  "home.recentEpisodes":"New episodes","home.recentEpisodesText":"Episodes aired in the last week.","home.today":"Today","home.moreEpisodes":"{count} more",
  "home.nextEpisodeAt":"Next: {date}",
  "title.otherNames":"Other names","title.ratingCountOne":"{count} rating","title.ratingCountFew":"{count} ratings","title.ratingCountMany":"{count} ratings",
  "title.synopsisMore":"Read more",
  "title.notInList":"Not in list","title.listLabel":"Watch status","title.minutesValue":"{minutes} min",
  "title.watchOrder":"Watch order","title.watchOrderHint":"Franchise chronology: watch left to right.",
  "title.allCharacters":"All characters",
  "report.videoProblem":"Problem with video",
  "watch.autoplayNext":"Next episode in {seconds}…","watch.autoplayCancel":"Cancel",
  "watch.voiceNone":"None",
  "profile.activityTotal":"{count} episodes in 12 months",
});

Object.assign(ru, {
  // Полка релизов сообщает фактическое окно, если за неделю серий почти нет.
  
  // Статус списка — один контрол: «Статус: Не в списке».
  "title.listLabel":"Статус:",
  // Серии в каталоге и серии в выбранной озвучке — разные числа, и это сказано прямо.
  "watch.episodeCoverageLine":"{total} всего · {available} доступны в выбранной озвучке",
  "watch.episodeCoverageLineOne":"{total} всего · {available} доступна в выбранной озвучке",
  "watch.availableOfTotal":"Доступно {available} из {total}",
});
Object.assign(en, {
  
  "title.listLabel":"Status:",
  "watch.episodeCoverageLine":"{total} total · {available} available in the selected voice-over",
  "watch.episodeCoverageLineOne":"{total} total · {available} available in the selected voice-over",
  "watch.availableOfTotal":"{available} of {total} available",
});

Object.assign(ru, {
  // Меню пользователя и навигация: предпочтения, «Ещё», библиотека в шапке.
  "nav.preferences":"Предпочтения","nav.openPrefs":"Открыть предпочтения","theme.label":"Тема",
  // Продолжение просмотра: единый формат строк и меню карточки.
  "home.continueWatchingText":"Серия, точка остановки и выбранная озвучка.",
  "home.allStarted":"Все начатые","home.startEp":"Смотреть {number} серию",
  "home.startEpisode":"Смотреть серию {number}",
  "home.episodeProgressLine":"Серия {number} · {time}",
  "home.episodesWatched":"просмотрено {count} из {total}",
  "home.removeFromContinue":"Убрать из продолжения","home.continueRemoved":"Убрано из продолжения",
  "home.continueMenu":"Действия с продолжением","home.undo":"Отменить",
  // Полка «Следующая часть»: контекст франшизы, а не новая рекомендация.
  "home.nextPartTitle":"Следующая часть истории",
  "home.nextPartText":"Вы досмотрели часть — дальше по порядку просмотра франшизы.",
  "home.nextPartAfter":"После «{name}»","home.nextPartWatching":" · вы на {time}",
});
Object.assign(en, {
  "nav.preferences":"Preferences","nav.openPrefs":"Open preferences","theme.label":"Theme",
  "home.continueWatchingText":"Episode, resume point and chosen voice track.",
  "home.allStarted":"All started","home.startEp":"Watch episode {number}",
  "home.startEpisode":"Watch episode {number}",
  "home.episodeProgressLine":"Episode {number} · {time}",
  "home.episodesWatched":"watched {count} of {total}",
  "home.removeFromContinue":"Remove from continue watching","home.continueRemoved":"Removed from continue watching",
  "home.continueMenu":"Continue watching actions","home.undo":"Undo",
  "home.nextPartTitle":"Next part of your story",
  "home.nextPartText":"You finished a part — continue in franchise watch order.",
  "home.nextPartAfter":"After “{name}”","home.nextPartWatching":" · you are at {time}",
});

export const dictionaries: Record<Locale, Record<string, string>> = { ru, en };
