from pathlib import Path

DEFAULT_LOCALE = "ru"
FALLBACK_LOCALE = "en"
SUPPORTED_LOCALES = frozenset({"ru", "en"})
CYRILLIC_TG_LANGUAGE_PREFIXES = ("ru", "be", "uk", "kk")
LOCALES_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "locales"


def resolve_initial_locale(raw_locale: str | None) -> str:
    """
    Maps Telegram language hints to the bot locale for newly created users.

    Cyrillic-first locales are routed to `ru`, the rest fall back to `en`.
    """
    normalized = (raw_locale or "").strip().lower()
    if normalized.startswith(CYRILLIC_TG_LANGUAGE_PREFIXES):
        return DEFAULT_LOCALE
    return FALLBACK_LOCALE


def normalize_locale_code(locale: str | None) -> str:
    """
    Sanitizes a persisted locale to a supported 2-letter code.
    """
    normalized = (locale or "").strip().lower()
    for separator in ("-", "_"):
        if separator in normalized:
            normalized = normalized.split(separator, 1)[0]
            break
    if normalized in SUPPORTED_LOCALES:
        return normalized
    return DEFAULT_LOCALE
