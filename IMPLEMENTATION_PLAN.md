# IMPLEMENTATION_PLAN: Freemium Model & Media Subscription Gate (The Hive)

## Обзор и бизнес-логика
Переход на гибридную воронку **Freemium + Audience Building**:
1. **Onboarding & Bait:** Новый пользователь выбирает язык, получает бонус за вступление в группу и выбирает любимый пресет (Scalper / Balanced / Conservative). Ему выдается полнофункциональный VIP-триал на 3 дня.
2. **Degradation (Bouncer):** По истечении 3 дней воркер `Bouncer` обнуляет VIP-доступ и **принудительно перезаписывает настройки пользователя на скрытый шумный пресет `FREE_NOISE_PRESET`** с инвалидацией кэша в Redis.
3. **Restricted Free Tier:** Пользователь продолжает получать сигналы, но с высоким уровнем шума (заниженные пороги, отключенный CVD, без графиков).
4. **Gatekeeper:** Доставка сигналов бесплатному пользователю осуществляется **только при наличии активной подписки на Новостной канал и Чат сообщества**. Статус членства кешируется в Redis (`csl:gate:{user_id}`) с TTL 10 минут.
5. **UI Paywall:** Меню настроек открыто для просмотра, но **любая попытка изменить фильтр, тумблер или пресет блокируется** модальным окном (Alert) с предложением купить VIP.

---

## Фаза 1: Конфигурация и Скрытый пресет (`src/core/config.py`, `src/core/dto.py`)
**Цель:** Зафиксировать эталон «контролируемого шума» и параметры каналов.

1. **`src/core/dto.py`**:
   * Убедиться, что `SettingPresetDTO` поддерживает все поля (пороги USD, % MCAP, тумблеры алертов, границы RSI).
2. **`src/core/config.py`**:
   * Добавить в словарь `SETTING_PRESETS` скрытый пресет `FREE_NOISE`:
     * `threshold_mode`: `"USD"`
     * `threshold`: `2000.0` (низкий долларовый порог для частоты)
     * `threshold_cascade`: `1500.0`
     * `threshold_oi_percent`: `3.0`
     * `threshold_oi_value`: `50000.0`
     * `threshold_mcap_pct`: `0.005`
     * `threshold_mcap_usd_min`: `1000.0`
     * `threshold_cascade_mcap_pct`: `0.005`
     * `threshold_cascade_mcap_usd_min`: `1000.0`
     * `filter_rsi_min`: `40.0`, `filter_rsi_max`: `60.0` (умеренный коридор)
     * Тумблеры: `alert_cascade=True`, `alert_volume=True`, `alert_squeeze=True`, `alert_longs=True`, `alert_shorts=True`, `alert_oi=True`, `alert_rsi=True`, `alert_cvd=False` *(CVD выключен)*.
   * Проверить и зафиксировать переменные каналов:
     * `NEWS_CHANNEL_ID`: `int | str | None`
     * `NEWS_CHANNEL_URL`: `str | None`
     * `COMMUNITY_GROUP_ID`: `int | None`
     * `COMMUNITY_GROUP_LINK`: `str | None`
     * `GATE_CACHE_TTL_SEC`: `int = 600` (10 минут)
     * `FREE_TRIAL_TOTAL_DAYS`: `int = 3`

---

## Фаза 2: Слой данных и Логика деградации (`src/database/crud/user_service.py`, `src/services/bouncer.py`)
**Цель:** Автоматический сброс настроек на шумный пресет при истечении подписки/триала.

1. **`src/database/crud/user_service.py`**:
   * Реализовать функцию `is_user_vip(user: User) -> bool`:
     * Возвращает `True`, если `user.subscription_end is not None and user.subscription_end > get_utc_now() and not user.is_blocked`.
   * Реализовать функцию `degrade_user_to_free_tier(session: AsyncSession, user_id: int) -> User | None`:
     * Атомарно загружает пользователя `with_for_update=True`.
     * Обнуляет `subscription_end = None`.
     * Применяет настройки из `config.SETTING_PRESETS["FREE_NOISE"]`.
     * Сохраняет изменения и возвращает обновленный объект пользователя.
2. **`src/services/bouncer.py`**:
   * В функции `bouncer_worker` / `_check_expired_subscriptions`:
     * Для всех пользователей с истекшим сроком вызывать `degrade_user_to_free_tier`.
     * Вызывать `await analyzer.invalidate_user_cache(user_id)` для мгновенного переключения аналитического движка на шумные пороги.
     * Отправлять сервисное уведомление через `i18n_runtime`:
       * Текст: уведомление об окончании VIP-доступа, переводе на бесплатный базовый поток сигналов и инструкция по возврату персональных настроек через покупку VIP.

---

## Фаза 3: Шлюз обязательных подписок и Кэширование (`src/core/redis_bus.py`, `src/services/messenger_worker.py`)
**Цель:** Проверка членства в канале и чате для Free-пользователей с защитой от лимитов Telegram API.

1. **`src/core/redis_bus.py`**:
   * Реализовать методы работы с кэшем шлюза:
     * `set_gate_status(user_id: int, is_allowed: bool, ttl: int = 600) -> None`: записывает строковое/числовое значение в ключ `csl:gate:{user_id}` с TTL.
     * `get_gate_status(user_id: int) -> bool | None`: возвращает `True`/`False` или `None` (cache miss).
2. **`src/services/messenger_worker.py`**:
   * Реализовать вспомогательную асинхронную функцию `check_user_channel_membership(bot: Bot, user_id: int) -> bool`:
     * Проверяет наличие обязательных каналов (`NEWS_CHANNEL_ID`, `COMMUNITY_GROUP_ID`). Если не заданы — возвращает `True`.
     * Делает вызовы `bot.get_chat_member` для обоих ресурсов.
     * Считает пользователя подписанным, если статус в обоих чатах входит в `{"member", "administrator", "creator", "restricted"}` (с правом чтения).
     * Обрабатывает исключения `TelegramBadRequest` / `TelegramForbiddenError` (если бот заблокирован или юзер не найден -> `False`).
   * В методе обработки рассылки `_process_signal`:
     * Для каждого целевого пользователя `target`:
       * Если пользователь **VIP** (`subscription_end > now`): доставка выполняется без ограничений.
       * Если пользователь **Free**:
         * Проверяется `await redis_bus.get_gate_status(user_id)`.
         * Если `None`: вызывается `check_user_channel_membership`, результат пишется в `redis_bus.set_gate_status` с TTL 600 секунд.
         * Если статус `False`: сигнал **не отправляется** данному пользователю (пропуск итерации).
     * **Оптимизация рендера:** Если пользователь Free — `photo_file_id` графиков не генерируется / не отправляется (или используется облегченная текстовая доставка), экономя ресурсы.

---

## Фаза 4: Paywall и Блокировка UI Настроек (`src/bot/handlers/settings.py`, `src/bot/keyboards/settings_kb.py`)
**Цель:** Позволить просматривать текущие настройки, но блокировать любые попытки их модификации для Free-пользователей.

1. **`src/bot/handlers/settings.py`**:
   * Экран настроек (`render_settings_menu`, `settings_filters_sub`, `settings_display_sub`) остается доступным для входа и чтения.
   * На все хендлеры изменения параметров внедряется проверка:
     * `toggle_threshold_mode_handler`
     * `set_mcap_parameter_start`
     * `toggle_settings` (все тумблеры `cascade`, `volume`, `squeeze`, `oi`, `rsi`, `cvd`, `longs`, `shorts`)
     * `start_set_threshold`, `start_set_cascade_threshold`, `start_set_oi_thresholds`
     * Хендлеры выбора пресетов стратегий
   * **Поведение при отсутствии VIP:**
     * Вызов `await callback.answer(i18n.get("paywall-settings-locked-alert"), show_alert=True)`.
     * FSM-состояния **не запускаются**, изменения в БД **не вносятся**.
     * Под меню настроек при необходимости выводится/обновляется кнопка перехода в магазин `[ 💎 Купить VIP для настройки ]`.

---

## Фаза 5: Онбординг и Интеграция 3-дневного триала (`src/bot/handlers/onboarding.py`, `src/bot/handlers/commands.py`)
**Цель:** Выдача полноценного VIP на 3 дня и сборка идеального пресета на старте.

1. **`src/bot/handlers/onboarding.py`**:
   * Порядок экранов онбординга:
     1. Выбор языка (`onboarding_language_*`).
     2. Оффер Community Bonus (`community-bonus-screen`) с начислением бонусного времени.
     3. Экран Setup Wizard: выбор стартового пресета стратегии (`SCALPER`, `BALANCED`, `CONSERVATIVE`) или кнопка «Пропустить».
   * При выборе пресета или завершении онбординга:
     * Пользователю гарантируется суммарный 3-дневный VIP-период (`TRIAL_DURATION_DAYS` + бонус за группу).
     * Применяется выбранный пресет.
     * Завершается онбординг (`complete_user_setup`).
     * Вызывается `invalidate_user_cache`.
2. **`src/bot/handlers/commands.py` (Главное меню)**:
   * Если у бесплатного пользователя в Redis статус шлюза `is_allowed == False` (отписался от каналов):
     * В тексте главного меню или отдельной плашкой выводить предупреждение:
       * *«⚠️ Рассылка сигналов приостановлена. Для получения сигналов подпишитесь на наш канал и чат.»*
     * Отображать инлайн-кнопки со ссылками на канал и чат и кнопку `[ 🔄 Проверить подписку ]`.

---

## Фаза 6: Локализация (`assets/locales/ru/messages.ftl`, `assets/locales/en/messages.ftl`)
**Цель:** Обеспечить строгую синхронизацию текстовых ключей без `ContextVar` ошибок.

1. Добавить ключи для Paywall:
   * `paywall-settings-locked-alert`: всплывающее окно при попытке изменить настройку без VIP.
   * `paywall-settings-locked-banner`: текст с призывом перейти на VIP внутри меню настроек.
   * `bouncer-degraded-to-free-notification`: сервисное уведомление при сбросе настроек после окончания VIP.
   * `gate-unsubscribed-warning`: предупреждение об остановке сигналов из-за отписки от медиа-ресурсов.
   * `gate-verify-button`: кнопка ручной проверки подписок в главном меню.

---

## Спецификация состояний и матрица доступа

| Параметр / Функция | VIP-пользователь (Платный / Триал 3 дня) | Free-пользователь (Подписан на канал+чат) | Free-пользователь (Отписан) |
| :--- | :--- | :--- | :--- |
| **Доставка сигналов** | Без ограничений | Получает общий поток (`FREE_NOISE`) | Остановлена |
| **Пороги объемов** | Персональные (Кастом / Пресет) | Зафиксированы на $2,000 / $1,500 | Не применимо |
| **Индикаторы в сообщении**| Полные (OI, RSI, CVD) | Ограниченные (OI, RSI; CVD=Выкл) | Не применимо |
| **Графики 15m OHLC** | Доставляются с графиком | Только текст (без рендера) | Не применимо |
| **Просмотр настроек** | Разрешен | Разрешен | Разрешен |
| **Изменение настроек** | Разрешено | Заблокировано (Paywall Alert) | Заблокировано (Paywall Alert) |

---

## Инженерные правила и Guardrails для Trae

1. **No Telegram Flood in Loops:** Запрещено вызывать `bot.get_chat_member` на каждом входящем рыночном тике или сигнале. Только через `redis_bus.get_gate_status` с TTL $\ge 300$ сек.
2. **Explicit DB Isolation:** При сбросе настроек в `bouncer.py` и `user_service.py` использовать чистые запросы по `user_id` без ленивой загрузки связанных сущностей (предотвращение `MissingGreenlet` / `greenlet_spawn`).
3. **Cache Invalidation:** Любое изменение статуса (`degrade_user_to_free_tier`, покупка подписки, смена пресета) обязано триггерить `await analyzer.invalidate_user_cache(user_id)`.
4. **Non-blocking UI:** Все проверки членства в хендлерах бота должны сопровождаться обработкой таймаутов, чтобы сбои сети Telegram не вешали интерфейс пользователя.