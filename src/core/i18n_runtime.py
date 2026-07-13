from aiogram_i18n.cores.fluent_runtime_core import FluentRuntimeCore
from fluent.runtime import FluentLocalization, FluentResourceLoader

from src.core.localization import DEFAULT_LOCALE, LOCALES_DIR, SUPPORTED_LOCALES, normalize_locale_code


def build_app_i18n_core() -> FluentRuntimeCore:
    return FluentRuntimeCore(
        path=LOCALES_DIR,
        default_locale=DEFAULT_LOCALE,
        raise_key_error=True,
    )


class BackgroundI18n:
    def __init__(self) -> None:
        loader = FluentResourceLoader(f"{LOCALES_DIR}/{{locale}}")
        self._localizations = {
            locale: FluentLocalization([locale], ["messages.ftl"], loader)
            for locale in SUPPORTED_LOCALES
        }

    def get(self, key: str, *, locale: str | None = None, **kwargs: object) -> str:
        normalized_locale = normalize_locale_code(locale)
        localization = self._localizations[normalized_locale]
        args = kwargs or None
        return str(localization.format_value(key, args))


app_i18n_core = build_app_i18n_core()
background_i18n = BackgroundI18n()
