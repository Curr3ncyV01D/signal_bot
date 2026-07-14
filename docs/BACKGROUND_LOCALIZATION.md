# BACKGROUND_LOCALIZATION

Документ фиксирует архитектурное решение по локализации фоновых процессов (workers / background services) в проекте CSL.

---

## Explanation

### Проблема: ограничения `I18nContext` и `ContextVar` вне Telegram update-flow

В bot-layer (`aiogram` handlers) локализация обычно доступна через `I18nContext` (например, параметр `i18n: I18nContext` в хендлере). Этот механизм работает корректно только внутри обработки входящего Telegram события, потому что:

- `I18nContext` и middleware aiogram-i18n используют `ContextVar` для хранения текущего locale и доступа к core без явной передачи параметров;
- `ContextVar` гарантированно заполнен только во время обработки update (message/callback) и только в том task/coroutine, где middleware установил контекст.

Фоновые процессы (воркеры) работают:

- вне контекста Telegram update;
- в собственных async-задачах, которые не проходили через i18n middleware;
- иногда параллельно (gather/semaphore) и в другом жизненном цикле.

Следствие: попытка использовать `I18nContext`/`i18n.get()` в фоне приводит к ошибкам класса “контекст не инициализирован”, а также к трудноотлавливаемым багам, связанным с утечкой контекста между задачами.

### Решение: Runtime Localization (разделение bot-layer и background-layer)

Для фоновых сервисов введен принцип **Runtime Localization**:

- bot-layer использует “магический” контекст i18n (middleware + `I18nContext`) и автоматически определяет locale;
- background-layer не использует контекст вообще и работает только через **прямой вызов runtime i18n**, где locale передается явно.

Это реализовано через отдельный инфраструктурный модуль [i18n_runtime.py](file:///root/signal_bot_dev/src/core/i18n_runtime.py):

- `app_i18n_core`: core для bot middleware (FluentRuntimeCore).
- `background_i18n`: lightweight runtime локализация для фоновых задач (FluentLocalization), не зависящая от `ContextVar`.

Ключевой архитектурный инвариант:

> В фоновых задачах locale всегда берется из БД (`User.language_code`) и передается в i18n явным параметром `locale=...`.

---

## Reference

### `src/core/i18n_runtime.py`

Источник: [i18n_runtime.py](file:///root/signal_bot_dev/src/core/i18n_runtime.py)

Содержимое модуля:

- `build_app_i18n_core() -> FluentRuntimeCore`
  - создает core для использования в `aiogram_i18n` middleware;
  - конфигурируется путями локалей (`LOCALES_DIR`) и default locale.
- `BackgroundI18n`
  - при инициализации строит `FluentLocalization` для каждого locale из `SUPPORTED_LOCALES`;
  - предоставляет метод `get(key, locale=..., **kwargs) -> str`, который:
    - нормализует locale через `normalize_locale_code`;
    - выполняет `format_value` без `ContextVar`;
    - возвращает финальную строку.
- Экспортируемые singleton-объекты:
  - `app_i18n_core`
  - `background_i18n`

Это разделяет контекстный i18n (handler-only) и бесконтекстный i18n (background-only).

### Эталонный паттерн для воркеров

Источник: [payment_worker.py](file:///root/signal_bot_dev/src/services/payment_worker.py#L32-L37), [payment_worker.py](file:///root/signal_bot_dev/src/services/payment_worker.py#L53-L59)

1. Воркер получает пользователя из БД и извлекает `language_code`.
2. Воркер нормализует locale.
3. Воркер вызывает `background_i18n.get()` с явным `locale=...`.

Эталонная заготовка:

```python
from src.core.i18n_runtime import background_i18n
from src.core.localization import normalize_locale_code
from src.database.models import User

def _get_i18n_text(locale: str | None, key: str, **kwargs: object) -> str:
    return background_i18n.get(
        key,
        locale=normalize_locale_code(locale),
        **kwargs,
    )

async def worker_step(session, user_id: int) -> str:
    user = await session.get(User, user_id)
    user_locale = normalize_locale_code(user.language_code if user else None)
    return _get_i18n_text(user_locale, "some-i18n-key")
```

### Ключевые функции безопасной локализации в фоне

В проекте приняты следующие опорные элементы:

- `background_i18n.get(...)` — единственный корректный способ получать локализованные строки в воркерах.
- `_get_i18n_text(...)` — рекомендованный thin-wrapper, стандартизирующий нормализацию locale и передачу kwargs. Реализовано в [payment_worker.py](file:///root/signal_bot_dev/src/services/payment_worker.py#L32-L37).

### Правила (чтобы не вернуть ошибки `ContextVar`)

- Запрещено использовать `I18nContext` и `i18n.get()` в фоне.
- Запрещено рассчитывать locale “из воздуха”. Locale должен браться из `User.language_code` в БД и нормализоваться.
- Разрешено использовать только runtime подход: `background_i18n.get(key, locale=..., **kwargs)`.

Практический критерий ревью:

> Если код выполняется вне handler’а (worker/task/cron/service) — в нем не должно быть `I18nContext` и не должно быть вызовов `.get()` без явного `locale=...`.
