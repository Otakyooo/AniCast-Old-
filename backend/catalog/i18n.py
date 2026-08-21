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
    translations = list(instance.translations.all())
    by_language = {translation.language: translation for translation in translations}
    requested = request_language(context)
    requested_translation = by_language.get(requested)
    if requested_translation is not None:
        return getattr(requested_translation, field)
    if requested == "en":
        return getattr(instance, field)
    for language in [DEFAULT_LANGUAGE, "en"]:
        translation = by_language.get(language)
        if translation is not None:
            return getattr(translation, field)
    return getattr(instance, field)
