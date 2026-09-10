SUPPORTED_LANGUAGES = {"ru", "en", "uk", "be", "kk", "de", "fr", "es", "it", "ja", "ko", "zh"}
DEFAULT_LANGUAGE = "ru"


def request_language(context) -> str:
    request = context.get("request") if context else None
    if request is None:
        return DEFAULT_LANGUAGE
    candidate = request.query_params.get("lang") or request.COOKIES.get("anicast_lang")
    if not candidate:
        candidate = request.headers.get("Accept-Language", "").split(",", 1)[0].split(";", 1)[0]
    candidate = (candidate or DEFAULT_LANGUAGE).strip().lower().split("-", 1)[0]
    return candidate if candidate in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def translated_value(instance, field: str, context) -> str:
    return translated_value_for_language(instance, field, request_language(context))


def translated_value_for_language(instance, field: str, requested: str) -> str:
    """Localized field value with a non-empty fallback chain.

    A translation row is not a promise that every field of it is filled: the
    imports create rows to carry the localized *name*, which left titles with
    a Russian row whose ``synopsis`` is empty. Returning that empty string hid
    the imported description from every Russian reader, so an empty localized
    value now falls through to the remaining languages and finally to the base
    instance field. The English request keeps its shortcut to the base fields:
    they hold the original English spelling, not a Russian fallback.
    """
    by_language = {translation.language: translation for translation in instance.translations.all()}

    def localized(language: str) -> str:
        translation = by_language.get(language)
        return getattr(translation, field) if translation is not None else ""

    candidates = [localized(requested)]
    if requested == "en":
        candidates.append(getattr(instance, field))
    candidates += [localized(DEFAULT_LANGUAGE), localized("en")]
    for value in candidates:
        if value:
            return value
    return getattr(instance, field)
