from pathlib import Path

from aiogram_i18n.cores.fluent_runtime_core import FluentRuntimeCore
from fluent.runtime import (
    FluentBundle,
    FluentLocalization,
    FluentResource,
    FluentResourceLoader,
)

from src.core.localization import DEFAULT_LOCALE, LOCALES_DIR, SUPPORTED_LOCALES, normalize_locale_code


def _get_locale_resource_paths(locale: str) -> list[Path]:
    locale_dir = LOCALES_DIR / locale
    resource_paths = sorted(
        (
            path
            for path in locale_dir.rglob("*.ftl")
            if path.is_file()
        ),
        key=lambda path: path.relative_to(locale_dir).as_posix(),
    )
    if resource_paths:
        return resource_paths

    raise FileNotFoundError(f"No FTL resources found for locale '{locale}' in {locale_dir}")


def _get_locale_resource_ids(locale: str) -> list[str]:
    locale_dir = LOCALES_DIR / locale
    return [path.relative_to(locale_dir).as_posix() for path in _get_locale_resource_paths(locale)]


class ProjectFluentRuntimeCore(FluentRuntimeCore):
    """
    Loads all split locale modules from the locale directory.
    """

    def find_locales(self) -> dict[str, FluentBundle]:
        translations: dict[str, FluentBundle] = {}
        locales = self._extract_locales(self.path)

        for locale in locales:
            translations[locale] = FluentBundle(
                locales=[locale],
                use_isolating=self.use_isolating,
                functions=self.functions,
            )

            for resource_path in _get_locale_resource_paths(locale):
                with resource_path.open("r", encoding="utf8") as fp:
                    translations[locale].add_resource(FluentResource(fp.read()))

            if self.pre_compile:
                self._FluentRuntimeCore__compile_runtime(translations[locale])

        return translations


def build_app_i18n_core() -> FluentRuntimeCore:
    return ProjectFluentRuntimeCore(
        path=LOCALES_DIR,
        default_locale=DEFAULT_LOCALE,
        raise_key_error=True,
    )


class BackgroundI18n:
    def __init__(self) -> None:
        loader = FluentResourceLoader(f"{LOCALES_DIR}/{{locale}}")
        self._localizations = {
            locale: FluentLocalization([locale], _get_locale_resource_ids(locale), loader)
            for locale in SUPPORTED_LOCALES
        }

    def get(self, key: str, *, locale: str | None = None, **kwargs: object) -> str:
        normalized_locale = normalize_locale_code(locale)
        localization = self._localizations[normalized_locale]
        args = kwargs or None
        return str(localization.format_value(key, args))


app_i18n_core = build_app_i18n_core()
background_i18n = BackgroundI18n()
