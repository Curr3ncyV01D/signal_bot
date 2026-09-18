# Freemium & Gatekeeper — Гибридная воронка, 4-состоятельная модель интерфейса и шлюз медиа-подписок

---

## 1. Архитектурный обзор и бизнес-модель (Explanation)

### 1.1 Концепция Freemium + Audience Building

Проект CSL (Crypto Scanner Liquid) перешел от модели «закрытый платный терминал» к **бартерной модели**: продукт обменивает право на получение сигналов на **внимание и присутствие пользователя в медиа-ресурсах** (Новостной канал + Чат сообщества).

**Бизнес-обоснование:**
- Устранение порога первого входа (нулевая стоимость первого опыта продукта).
- Построение органической аудитории в Telegram-ресурсах для последующей рекламной/анонсной монетизации.
- Снижение CAC (Customer Acquisition Cost): триал не стоит ничего, а переход в платный сегмент происходит через психологический дискомфорт от «шумного» бесплатного потока.

### 1.2 Психологическая модель «Прикормить и ограничить» (Bait & Restrict)

```
┌─────────────────────────────────────────────────────────────────┐
│  Этап 1: Bait (Прикорм)                                         │
│  → Новый пользователь. 3 дня полноценного VIP.                  │
│  → Персональные фильтры, CVD, графики 15m OHLC, чистый поток.   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 3 дня прошло (Bouncer.degrade)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Этап 2: Restrict (Ограничение)                                 │
│  → Автоматический накат пресета FREE_NOISE (сигналы «как из     │
│    пожарного рукава»).                                          │
│  → CVD/RSI-фильтры отключены, графики удалены → поток шумный.   │
│  → Настройки Paywall-блокированы (модалка «Купи VIP»).         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Пользователь НЕ выходит из сообщества
                           ├──────────────────────────────────────┐
                           ▼                                      ▼
┌───────────────────────────────────┐  ┌──────────────────────────────┐
│  Сценарий А: СОСТОИТ В КАНАЛАХ    │  │  Сценарий Б: ОТПИСАЛСЯ       │
│  STATE_FREE_ACTIVE 🟡             │  │  STATE_FREE_PAUSED 🔴        │
│  → Шумный поток продолжает лить.  │  │  → Доставка заморожена       │
│  → Дискомфорт → покупка VIP $25   │  │  → Карточка «Вступи в канал»│
│  → Conversion (LTV)               │  │  → Re-engagement → возврат   │
└───────────────────────────────────┘  └──────────────────────────────┘
```

### 1.3 Разделение ценности тарифов (Value Prop Matrix)

| Возможность | 💎 VIP | 🆓 Free (в каналах) | 🔴 Free (отписан) |
|---|---|---|---|
| **Доставка сигналов** | 100% времени, без проверок | Только при активном членстве в двух ресурсах | ❌ Полностью приостановлена |
| **Пороги триггеров** | Персональные (пресет / кастом) | Зафиксированы `FREE_NOISE` (невозможно изменить) | N/A |
| **CVD (Cumulative Volume Delta)** | ✅ Включено по желанию | ❌ Принудительно `alert_cvd=False` | N/A |
| **RSI-фильтр (тонкая настройка полос)** | ✅ Полосы + пресеты + ручной ввод | ❌ `alert_rsi=False` (RSI-ветка выключена) | N/A |
| **15m OHLC-графики в алерте** | ✅ `photo_file_id=resolved` | ❌ `photo_file_id=None` (только текст) | N/A |
| **Просмотр настроек** | ✅ | ✅ (текущее состояние читается) | ✅ |
| **Модификация настроек** | ✅ Без ограничений | ❌ Paywall Alert (все 9 точек входа) | ❌ Paywall Alert |
| **Тумблер `is_signals_enabled` (глобальная пауза)** | ✅ | ✅ (единственная незащищенная настройка) | ✅ |
| **Обязательное членство в канале/чате** | ❌ Не требуется | ✅ Оба ресурса (AND) | ✅ Нужны для разблокировки |

### 1.4 Место Freemium/Gatekeeper в общей архитектуре «Улья»

```
┌──────────────────────────────────────────────────────────────────────┐
│  UI Layer (aiogram handlers)                                          │
│  commands.py: resolve_user_menu_state → get_start_kb (Clean State)    │
│  onboarding.py: LANGUAGE → BONUS → PRESET SELECTION (3 дн триал)      │
│  settings.py: Paywall Early Exit на 9 хендлеров модификаций           │
│  gate screen: render_gate_unlock_screen (подэкран разблокировки)      │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ CRUD (PostgreSQL + SQLAlchemy async)
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Persistence Layer: models.py + user_service.py                       │
│  User.subscription_end / is_trial_used / is_community_bonus_used      │
│  User.is_signals_enabled (глобальный master-выключатель доставки)     │
│  ⚙️ degrade_user_to_free_tier() → with_for_update → FREE_NOISE preset │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ Cache invalidation Pub/Sub
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Analytics Engine: analyzer.py + trigger_engine                       │
│  _cached_users[]: is_vip, is_signals_enabled → min_system_threshold   │
│  invalidate_user_cache(id) → _update_cache_logic + Redis Pub/Sub      │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ Redis: gate key + Stream ready + Locks
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Gatekeeper Layer: redis_bus.set/get_gate_status + bouncer.py         │
│  csl:gate:{user_id} → "1"/"0" → TTL config.GATE_CACHE_TTL_SEC (10м)   │
│  _check_media_resources_membership() → 2× bot.get_chat_member AND     │
│  ⚙️ bouncer_worker() → degrade + Fork A/B уведомлений                 │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ Stream:ready → Consumer Group messenger_group
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Delivery Layer: messenger_worker.py (MessengerWorker)                │
│  VIP → skip gate checks, render chart file_id                         │
│  FREE → get_gate_status() → cache miss → check_user_channel_membership│
│  FREE → photo_file_id=None (Stripped Signal, Artist CPU-saving)       │
│  is_signals_enabled=False → скип доставки на 1-м этапе цикла          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Матрица 4-х состояний пользователя (Reference & State Machine)

### 2.1 Формальные критерии 4 взаимоисключающих состояний

Состояния вычисляются **детерминированно** на рантайме функцией [resolve_user_menu_state](file:///root/signal_bot/src/bot/handlers/commands.py#L49-L66) и её дубликатом [_resolve_state](file:///root/signal_bot/src/bot/keyboards/main_kb.py#L30-L43) в клавиатурном слое (избегание циклических импортов).

Порядок проверок **строго фиксирован** (приоритет从上往下):

| # | Состояние | Emoji | Формальный предикат (lambda user, is_gate_allowed) |
|---|---|---|---|
| 1 | `STATE_TRIAL_AVAILABLE` | 🟢 Новичок | `user.is_trial_used == False AND is_user_vip(user) == False` |
| 2 | `STATE_VIP_ACTIVE` | 💎 VIP/Триал | `is_user_vip(user) == True` (`subscription_end is not None AND > now AND not is_blocked`) |
| 3 | `STATE_FREE_ACTIVE` | 🟡 Доставка идёт | `not VIP AND is_gate_allowed is True` (Redis `csl:gate:{id}=="1"`) |
| 4 | `STATE_FREE_PAUSED` | 🔴 Заморозка | `not VIP AND is_gate_allowed in {False, None}` (отписан / кэш пуст / Redis down) |

Где `is_user_vip` определена в [is_user_vip](file:///root/signal_bot/src/database/crud/user_service.py#L167-L173).

### 2.2 Mermaid State-Diagram переходов

```mermaid
stateDiagram-v2
    [*] --> TRIAL_AVAILABLE: Новый пользователь /onboarding_step=LANGUAGE

    TRIAL_AVAILABLE --> VIP_ACTIVE: apply_onboarding_preset / activate_trial + issue_bonus_subscription\n(1 день + 48ч community = 3 дн)
    TRIAL_AVAILABLE --> VIP_ACTIVE: community bonus (verify_community_join)\napply_community_bonus() + onboarding_step→PRESET
    TRIAL_AVAILABLE --> TRIAL_AVAILABLE: skip_onboarding_preset (бонусы начисляются тоже)

    VIP_ACTIVE --> FREE_ACTIVE: subscription_end <= now (Bouncer.expire)\nverify_member: is_member=True → gate="1"\ndegrade→FREE_NOISE preset + invalidate cache
    VIP_ACTIVE --> FREE_PAUSED: subscription_end <= now (Bouncer.expire)\nverify_member: is_member=False → gate="0"\nsend: gate_card + verify_buttons
    VIP_ACTIVE --> VIP_ACTIVE: manual buy / auto_renew (billing_service.charge_and_activate)

    FREE_PAUSED --> FREE_ACTIVE: verify_gate_sub callback\n_verify_gate_resources_membership: AND(News,Community)=True\nredis.set_gate("1") → render_main_menu (STATE_FREE_ACTIVE)

    FREE_ACTIVE --> FREE_PAUSED: GATE_CACHE_TTL (10 мин) истёк + проверка bot.get_chat_member: NOT member\nmessenger_worker writes gate="0" + пользователь видит переход при следующем /start

    FREE_ACTIVE --> VIP_ACTIVE: buy_subscription → billing_processor (CryptoPay / Cactus / Manual)
    FREE_PAUSED --> VIP_ACTIVE: buy_subscription (без необходимости вступать в каналы; VIP-проверка проходит раньше)

    state TRIAL_AVAILABLE {
        description: 🟢 is_trial_used=False + не VIP
    }
    state VIP_ACTIVE {
        description: 💎 subscription_end > now
    }
    state FREE_ACTIVE {
        description: 🟡 gate=1 (в каналах)
    }
    state FREE_PAUSED {
        description: 🔴 gate=0/None (отписан / неизвестно)
    }
```

---

## 3. Архитектура Главного Меню и Подэкрана разблокировки (UI/UX Specification)

### 3.1 Clean State Model: Монолитный футер + динамический CTA-слот

Клавиатура главного меню генерируется функцией [get_start_kb](file:///root/signal_bot/src/bot/keyboards/main_kb.py#L85-L146). **Структура неизменна**:

```
┌─────────────────────────────────────────────────┐
│  [ ДИНАМИЧЕСКИЙ CTA-СЛОТ ]  ← 0 или 1 кнопка   │
│  (строго 1 ряд, только верхний слот изменяется) │
├─────────────────────────────────────────────────┤
│  [ 💰 Кошелек (X.XX USDT) ] [ 👤 Личный кабинет ]│  ← Ряд 1
├─────────────────────────────────────────────────┤
│  [           ⚙️ Настройки и фильтры           ] │  ← Ряд 2
├─────────────────────────────────────────────────┤
│  [ 💬 Чат сообщества ↗ ]  [ 👨‍💻 Тех. поддержка ↗ ]│  ← Ряд 3
└─────────────────────────────────────────────────┘
```

Футер (3 ряда, 5 кнопок) рендерится [_build_static_footer](file:///root/signal_bot/src/bot/keyboards/main_kb.py#L46-L82), и **абсолютно идентичен** для всех 4-х состояний, включая пользователей, вылетевших из State 4 🔴.

### 3.2 Спецификация динамического CTA-слота (по состояниям)

Динамический слот — всегда 0 или 1 кнопка (не более, чем одна верхняя кнопка):

| Состояние | Верхняя CTA-кнопка | Callback-data |
|---|---|---|
| 🟢 `STATE_TRIAL_AVAILABLE` | 🎁 `kb-main-trial` → «Пробный период» | `activate_trial` (открывает экран триала с ссылкой на новостной канал) |
| 💎 `STATE_VIP_ACTIVE`, days_left > 5 | **СЛОТ ПУСТОЙ** (нет CTA-кнопки сверху) | — |
| 💎 `STATE_VIP_ACTIVE`, days_left ≤ 5 | ⚡️ `kb-main-renew-left` → «Продлить подписку (осталось N дн.)» | `buy_subscription` |
| 🟡 `STATE_FREE_ACTIVE` | 💎 `kb-main-upgrade-vip` → «Перейти на VIP (Убрать шум)» | `buy_subscription` |
| 🔴 `STATE_FREE_PAUSED` | 🔓 `kb-main-unlock-signals` → «Включить бесплатные сигналы» | `open_gate_unlock_screen` |

Порог перехода из «пустой CTA → renew CTA»: `VIP_RENEW_DAYS_THRESHOLD = 5` [main_kb.py:L18](file:///root/signal_bot/src/bot/keyboards/main_kb.py#L18).

Текст строки статуса подписки в сообщении главного меню генерируется [get_main_menu_text](file:///root/signal_bot/src/bot/handlers/commands.py#L83-L115) и использует 4 локал-ключа:
- `main-menu-status-vip-active` (с подстановкой `subscription_end`)
- `main-menu-status-free-active` («🆓 Бесплатный тариф»)
- `main-menu-status-free-paused` («❌ Не активна.»)
- `main-menu-status-trial-available` («❌ Не активна.» с доп.описанием в тексте ниже)

### 3.3 Паттерн отдельного экрана разблокировки (Gate Screen)

**Почему не «свалка кнопок» в главном меню?** Изначальный план [IMPLEMENTATION_PLAN.md:L116-L121](file:///root/signal_bot/IMPLEMENTATION_PLAN.md#L116-L121) предлагал встраивать ссылки на канал/чат и кнопку проверки **прямо в клавиатуру STATE_FREE_PAUSED**. В реальном коде принято решение вынести это на выделенный экран:

1. **Монолитность футера сохранена**: 3 нижних ряда идентичны даже для 🔴 STATE_FREE_PAUSED (иначе бы футер менялся, нарушая UX muscle memory).
2. **Кнопка «Чат сообщества» не дублируется**: футер уже содержит ссылку `Чат сообщества ↗`; добавление второй копии в CTA-слот создало бы визуальный дубликат.
3. **Достаточно места для двух ссылкок-рядов**: Gate Screen помещает все 4 ряда в одном экране.

#### Спецификация Gate Screen

Рендер функцией [render_gate_unlock_screen](file:///root/signal_bot/src/bot/handlers/commands.py#L191-L263):

```
┌────────────────────────────────────────────────────────┐
│  [ WELCOME БАННЕР: ImagePaths.WELCOME ]                │
│  ⚠️ Активация бесплатного тарифа.                      │
│  Чтобы бесплатно получать сигналы:                     │
│  1. Подпишитесь на наш Новостной канал                 │
│  2. Вступите в Чат сообщества                          │
│  После вступления нажмите кнопку подтверждения ниже:   │
├────────────────────────────────────────────────────────┤
│  [ 📢 Новостной канал ]                          (URL) │ ← News-channel URL (если NEWS_CHANNEL_URL задан)
├────────────────────────────────────────────────────────┤
│  [ 💬 Чат сообщества ]                           (URL) │ ← COMMUNITY_GROUP_LINK
├────────────────────────────────────────────────────────┤
│  [ ✅ Проверить и включить сигналы ]   (verify_gate_sub)│ ← callback: verify_gate_sub / verify_community_join (универсальный хендлер)
├────────────────────────────────────────────────────────┤
│  [ 🏡 Домой ]                              (back_to_main)│ ← возврат в STATE_FREE_PAUSED
└────────────────────────────────────────────────────────┘
```

Поведение при клике `verify_gate_sub`: универсальный обработчик [process_verify_gate_subscription](file:///root/signal_bot/src/bot/handlers/onboarding.py#L428-L529):
1. Вызывает `_verify_gate_resources_membership(bot, user_id)` → `(is_community_ok AND is_news_ok) = gate_approved`.
2. Пишет результат в Redis: `set_gate_status(user_id, gate_approved, TTL=600)`.
3. Если `gate_approved=True`: вызывает `render_main_menu()` → пользователь автоматом оказывается в 🟡 STATE_FREE_ACTIVE (с CTA-кнопкой «Перейти на VIP»).
4. Если `False`: показывает `gate-subscription-not-found` toast (show_alert=True).

---

## 4. Защита настроек и Paywall (Settings UI Protection)

### 4.1 Принцип «Просмотр разрешён, модификация заблокирована»

Паттерн **Early Exit**: корневые экраны настроек (`render_settings_menu`, `render_settings_filters_menu`, `render_settings_display_menu`, `render_setting_presets_catalog`) **не имеют** VIP-проверок — они рендерят текущее состояние настроек как есть. Paywall проверка внедряется **только на хендлеры, производящие запись в БД / изменение FSM-состояния**.

### 4.2 Полный перечень 11 защищённых точек входа (в [settings.py](file:///root/signal_bot/src/bot/handlers/settings.py))

| Точка входа | Callback / FSM-state | Paywall-строка в коде |
|---|---|---|
| Смена режима USD / PERCENT | `toggle_threshold_mode` | [L153-155](file:///root/signal_bot/src/bot/handlers/settings.py#L153-L155) |
| 4 числовых параметра MCAP (% / $ min для volume / cascade) | `set_mcap_parameter_start` → 4 FSM states | [L179-181](file:///root/signal_bot/src/bot/handlers/settings.py#L179-L181) |
| USD-порог объёма ликвидаций | `set_threshold` → FSM `waiting_for_threshold` | [L576-578](file:///root/signal_bot/src/bot/handlers/settings.py#L576-L578) |
| USD-порог каскада | `set_cascade_threshold` → FSM `waiting_for_cascade_threshold` | [L618-620](file:///root/signal_bot/src/bot/handlers/settings.py#L618-L620) |
| OI-пороги (% и $) | `menu_oi_thresholds` → FSM `waiting_for_oi_thresholds` | [L662-664](file:///root/signal_bot/src/bot/handlers/settings.py#L662-L664) |
| 8 тумблеров (cascade/volume/squeeze/longs/shorts/oi/rsi/cvd) | `toggle_<feature>` (catch-all `toggle_settings`) | [L540-542](file:///root/signal_bot/src/bot/handlers/settings.py#L540-L542) |
| RSI пресеты (4 кнопки) | `set_rsi_preset_{CONSERVATIVE/BALANCED/SCALPER/DISABLED}` | [L736-741](file:///root/signal_bot/src/bot/handlers/settings.py#L736-L741) |
| RSI ручной ввод | `set_rsi_manual_start` → FSM `waiting_for_rsi_thresholds` | [L775-777](file:///root/signal_bot/src/bot/handlers/settings.py#L775-L777) |
| Применение пресета стратегии | `apply_setting_preset_{SCALPER/BALANCED/CONSERVATIVE}` | [L476-481](file:///root/signal_bot/src/bot/handlers/settings.py#L476-L481) |

Механика Early Exit едина:
```python
if not is_user_vip(user_obj):
    return await callback.answer(i18n.get("paywall-settings-locked-alert"), show_alert=True)
```
- FSM-состояние **не запускается** (возврат до `await state.set_state(...)`).
- Записи в БД **не происходит**.
- Показывается **модальное окно** (Telegram show_alert popup) с ключом `paywall-settings-locked-alert`: «💎 Настройка фильтров и пресетов доступна только в VIP-тарифе».

### 4.3 Динамическая кнопка разблокировки настроек

Вспомогательная функция [_append_vip_unlock_button](file:///root/signal_bot/src/bot/keyboards/settings_kb.py#L13-L23) внедряется **в footer всех клавиатур настроек** (root, filters, display, presets-catalog, presets-confirm, rsi):

```python
if not is_user_vip(user):
    builder.row(
        InlineKeyboardButton(
            text=LazyProxy("kb-settings-buy-vip"),  # "💎 Купить VIP для настройки"
            callback_data="buy_subscription",
        )
    )
```

Таким образом пользователь сразу видит CTA «купи» при любом просмотре подэкрана настроек — без необходимости возвращаться в главное меню.

### 4.4 Критическое исключение: тумблер `is_signals_enabled` — Paywall-FREE

Единственная незащищенная настройка: глобальный master-переключатель «Сигналы: Вкл/Выкл» [toggle_global_signals](file:///root/signal_bot/src/bot/handlers/settings.py#L510-L530).

Она **не содержит** проверку `is_user_vip()`. На ряд 1 корневого экрана настроек она выводится всегда:
- «🔕 Сигналы: Выключены» / «🔔 Сигналы: Включены» (ключи `kb-settings-signals-on` / `kb-settings-signals-off`).

**Архитектурное обоснование (раздел 8 решения):**
Бесплатный пользователь, получающий 50+ шумных алертов в сутки от FREE_NOISE-пресета, **должен иметь возможность заглушить поток**, не покупая VIP. В противном случае пользователи будут жаловаться в Telegram на «спам от бота», что чревато банном бота в anti-spam filters Telegram (BotFather / Mass Report).

Поле `User.is_signals_enabled` хранится в [models.py:L20](file:///root/signal_bot/src/database/models.py#L20) (`Boolean, default=True, nullable=False`). Оно проверяется **до gate-проверки** в доставке:
1. [messenger_worker.py:L554-556](file:///root/signal_bot/src/services/messenger_worker.py#L554-L556): `if not target.get("is_signals_enabled", True): continue` — скипается раньше Gatekeeper.
2. [analyzer.py:L120-L122](file:///root/signal_bot/src/services/analyzer.py#L120-L122): пользователи с `is_signals_enabled=False` **не учитываются** в `_min_system_threshold` → движок не тратит CPU на анализ порогов для них.

---

## 5. Шлюз обязательных подписок в рантайме (Gatekeeper & Delivery Pipeline)

### 5.1 Архитектура кэша Redis: ключ `csl:gate:{user_id}`

Методы уровня шлюза в [redis_bus.py:L315-L360](file:///root/signal_bot/src/core/redis_bus.py#L315-L360):

| Метод | Семантика |
|---|---|
| `_gate_key(user_id)` → `"csl:gate:{user_id}"` | Строковый ключ, без хэшей/списков |
| `set_gate_status(user_id, is_allowed, ttl=None)` | Записывает `"1"` (True) / `"0"` (False) с `TTL = config.GATE_CACHE_TTL_SEC = 600` сек (10 минут по умолчанию [config.py:L206](file:///root/signal_bot/src/core/config.py#L206)). Если `ttl` передан явно (например, Bouncer при degrade использует тот же 600с) |
| `get_gate_status(user_id) -> bool \| None` | Возвращает: `True` для `"1"`, `False` для `"0"`, `None` — если ключа нет (cache miss) или Redis недоступен. |

**Три источника записи в gate:**
1. **Bouncer** при деградации подписки (L247 [bouncer.py](file:///root/signal_bot/src/services/bouncer.py#L247)): немедленно пишет актуальный статус.
2. **onboarding** / `verify_gate_sub` callback: пишет результат ручной проверки.
3. **messenger_worker runtime-fallback**: при cache-miss пишет результат реального `bot.get_chat_member`.

### 5.2 Runtime-ветка доставки в messenger_worker.py

Логика sharding delivery по сегментам [_process_signal](file:///root/signal_bot/src/services/messenger_worker.py#L538-L630):

```
┌─ Получен SignalDTO из Redis Stream READY ──────────────────────────┐
│                                                                    │
│  1. Cached targets: _get_targets_snapshot() → [CachedAlertTarget] │
│  2. photo_file_id_vip = _resolve_media_to_file_id(chart_msg_id)   │
│                                                                    │
│  ┌─ FOR EACH target ───────────────────────────────────────────┐  │
│  │                                                             │  │
│  │  [L555] ✂️ is_signals_enabled == False → continue (PAID/БЕСПЛ) │  │
│  │                                                             │  │
│  │  trigger_result = _check_triggers_from_dto(target, dto)    │  │
│  │  trigger_result is None → continue                          │  │
│  │                                                             │  │
│  │  IF target.is_vip = True:                                   │  │
│  │    → SKIP gate checks (бренная привилегия VIP)              │  │
│  │    → prepared_vip_alerts.append((user, payload))            │  │
│  │    → photo_file_id_vip (полноценный 15m график)             │  │
│  │                                                             │  │
│  │  ELSE (FREE segment):                                       │  │
│  │    ┌─ Gatekeeper branch ──────────────────────────────┐     │  │
│  │    │ L587 gate_status = redis.get_gate_status(id)     │     │  │
│  │    │ cache miss (None):                               │     │  │
│  │    │   → check_user_channel_membership(bot, id)       │     │  │
│  │    │     (2× Telegram API call: News + Chat AND)      │     │  │
│  │    │   → set_gate_status(id, is_allowed, TTL=600)     │     │  │
│  │    │ Redis error: gate_status=False (fail-closed)     │     │  │
│  │    │                                                   │     │  │
│  │    │ IF gate_status=False → continue (skip delivery)  │     │  │
│  │    └──────────────────────────────────────────────────┘     │  │
│  │    → prepared_free_alerts.append((user, payload))            │  │
│  │    → photo_file_id = None (Text-Only, Artist skip render)    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  _dispatch_batches() → 50-alert batches + asyncio.gather           │
└────────────────────────────────────────────────────────────────────┘
```

### 5.3 Оптимизация рендера: Stripped Signal для FREE сегмента

Самая дорогая операция пайплайна — вызов Artist-воркера рендера PNG-графика 15m OHLC (PIL / matplotlib) + resolve через Telegram forward-log channel. Для Free пользователей она **полностью выкидывается**:

```python
# VIP delivery (messenger_worker.py:L610-L618)
send_liquidation_alert(bot, id, photo_file_id=photo_file_id_vip, **payload)

# FREE delivery (messenger_worker.py:L620-L628)
send_liquidation_alert(bot, id, photo_file_id=None, **payload)
```

**Эффект:**
- Экономия CPU Artist-процесса (рендер для 1000 бесплатных пользователей → 0 вызовов).
- Экономия памяти и forward-резолва логического файл-ID (все resolve через LOG_CHANNEL_ID).
- Ценностное неравенство: VIP визуально получает совершенно другой, более богатый контент (картинка с графиком), а не только более точные фильтры.

### 5.4 Схема проверки членства в каналах

Обе независимые функции [_check_media_resources_membership](file:///root/signal_bot/src/services/bouncer.py#L148-L192) (Bouncer) и [check_user_channel_membership](file:///root/signal_bot/src/services/messenger_worker.py#L135-L178) (Messenger) реализуют одинаковый контракт:

- Множество валидных статусов: `_ALLOWED_MEMBER_STATUSES = {"member", "administrator", "creator", "restricted"}`. Статус `left`, `kicked` → False.
- Логика: `AND(NEWS_CHANNEL_ID membership, COMMUNITY_GROUP_ID membership)`.
- Fail-closed: `TelegramBadRequest` (чат не существует, бот не админ), `TelegramForbiddenError` (юзер заблокировал бота), любые др. исключения → возврат False.
- Если ресурс `None` или `""` в конфиге → условно считаем его «пройденным» (dev-mode fallback, без resources).

---

## 6. Жизненный цикл и механизм деградации (`Bouncer` & `UserService`)

### 6.1 Атомарная деградация: `degrade_user_to_free_tier`

Функция деградации в [user_service.py:L176-L226](file:///root/signal_bot/src/database/crud/user_service.py#L176-L226) — атомарная за 1 SQLAlchemy сессию:

```
Шаг 1: session.get(User, id, with_for_update=True)
         ↓ (PostgreSQL row-level FOR UPDATE lock,
            запрещает конкурентные Bouncer/воркеры на время TX)
Шаг 2: preset = config.SETTING_PRESETS["FREE_NOISE"]
Шаг 3: Перезапись 18 полей:
         ├─ user.subscription_end = None   # ← ОБЯЗАТЕЛЬНО первым полем
         ├─ user.last_expiry_warning_at = None
         ├─ threshold_mode, threshold, threshold_cascade
         ├─ threshold_oi_percent, threshold_oi_value
         ├─ threshold_mcap_pct, threshold_mcap_usd_min
         ├─ threshold_cascade_mcap_pct, threshold_cascade_mcap_usd_min
         ├─ filter_rsi_min, filter_rsi_max  ( RSI 40 / 60 )
         └─ 8 alert_* bool тумблеров
Шаг 4: session.commit() + session.refresh(user)
         ↓
         Возврат User или None (при ошибке БД)
```

Содержимое скрытого пресета `FREE_NOISE` в [config.py:L148-L168](file:///root/signal_bot/src/core/config.py#L148-L168):

| Поле | Значение FREE_NOISE | Отличие от VIP-пресетов |
|---|---|---|
| `threshold_mode` | `"USD"` | VIP-вариант BALANCED/SCALPER: `"PERCENT"` |
| `threshold` | `3000.0 $` (очень низкий) | BALANCED: 20000$ (6,7× «чище») |
| `threshold_cascade` | `2000.0 $` | BALANCED: 15000$ |
| `filter_rsi_min / max` | `40.0 / 60.0` | SCALPER: 35/65, BALANCED: 30/70, CONS: 20/80 |
| `alert_rsi` | **False** | VIP: **True** |
| `alert_cvd` | **False** | VIP: **True** |

`FREE_NOISE` **исключен** из UI-выбора: константа PRESET_ORDER в онбординге и settings.py кортежем `("SCALPER", "BALANCED", "CONSERVATIVE")`. На Free-аккаунт пресет накатывается **только программно** через degrade.

### 6.2 Развилка Bouncer-уведомлений при экспирации

[`_handle_subscription_expiry`](file:///root/signal_bot/src/services/bouncer.py#L235-L255) в bouncer.py реализует **Fork A/B** после успешного вызова `degrade_user_to_free_tier`:

```
user = degrade_user_to_free_tier(user_id)
invalidate_user_cache(user.id)  # ← Redis Pub/Sub cache invalidation
                                    (analyzer + messenger cache)
is_member = _check_media_resources_membership(bot, user.id)
redis.set_gate_status(user.id, is_member, ttl=GATE_CACHE_TTL_SEC)

┌─ IF is_member == True (FORK А: Пользователь СОСТОИТ В КАНАЛАХ) ─────┐
│                                                                    │
│  текст: bouncer-degraded-to-free-notification                       │
│  «Срок вашей подписки истек. Вы переведены на бесплатный тариф с   │
│   базовым потоком сигналов. Чтобы вернуть точные фильтры и CVD —   │
│   оформите VIP-подписку.»                                          │
│  reply_markup: None (чистое уведомление без кнопок)                │
└────────────────────────────────────────────────────────────────────┘

┌─ IF is_member == False (FORK Б: Пользователь ОТПИСАН) ─────────────┐
│                                                                    │
│  текст: bouncer-expired-unsubscribed-notification                   │
│  «Срок вашей подписки истек, а вы покинули наши ресурсы. Чтобы     │
│   продолжить получать бесплатные сигналы — вступите в канал и чат. │
│  reply_markup: _build_gate_verify_keyboard(user_locale)             │
│     3 ряда: [📢 News URL] → [💬 Chat URL] → [🔄 Проверить]          │
│     callback_data=verify_community_join (универсальный хендлер)     │
└────────────────────────────────────────────────────────────────────┘
```

### 6.3 Bouncer worker main loop

[bouncer_worker](file:///root/signal_bot/src/services/bouncer.py#L257-L309):

| Параметр | Значение |
|---|---|
| Интервал цикла | `interval_minutes = 15` (default, передаётся из main.py при запуске) |
| Кандидат-окно выборки | `User.subscription_end <= now + 25 ч` (EXPIRY_WARNING_24H_MAX_HOURS + буфер) |
| for-loop для каждого user_id: | 1. `with_for_update=True` lock строки → 2. `_handle_expiry_warning` (1 раз 24-часовой threshold, отдельно для trial 45-75 мин) → 3. `_handle_auto_renewal` (если auto_renewal + есть 25 USDT баланса → charge_and_activate, если нет → 1 раз в 24 часа notify о нехватке) → 4. Если `subscription_end <= now` → `_handle_subscription_expiry`. |

### 6.4 Обязательная инвалидация кэша после любого изменения статуса

Для немедленного вступления в силу деградации (не ждать 60-секундный `user_cache_refresher_task`) после событий:
- Bouncer-degrade → `invalidate_user_cache(user.id)` ([bouncer.py:L244](file:///root/signal_bot/src/services/bouncer.py#L244))
- apply_preset → локальная запись `update_values + COMMIT` → `invalidate_user_cache(id)`
- VIP-покупка / бонус начисление → `billing_service.*` делают `commit` + далее вызывают аналитик-инвалидацию.

Функция [`invalidate_user_cache`](file:///root/signal_bot/src/services/analyzer.py#L146-L153):
1. Вызывает `_update_cache_logic()` (перечитывает всех users из БД → актуализирует `_cached_users`, `_min_system_threshold`, `_min_system_cascade` для движка ликвидаций).
2. Публикует в Redis Pub/Sub `csl:cache_invalidation` строку: `user_id` или `ALL`.
3. Messenger-воркер слушает тот же канал через `_cache_invalidation_listener` и сбрасывает свою копию `_cached_users` (targets Snapshot).

---

## 7. Онбординг и формирование 3-дневного триала

### 7.1 Пошаговая цепочка первого входа

Машина состояний онбординга хранится в `User.onboarding_step` ([models.py:L16](file:///root/signal_bot/src/database/models.py#L16)) как строка-лема. Допустимые шаги: `{"LANGUAGE", "COMMUNITY_BONUS", "PRESET_SELECTION", "COMPLETED"}` ([dto.py:L10](file:///root/signal_bot/src/core/dto.py#L10)).

Рендер незавершённого шага функцией [render_pending_onboarding_screen](file:///root/signal_bot/src/bot/handlers/onboarding.py#L187-L200) с guard-логикой [_resolve_onboarding_step](file:///root/signal_bot/src/bot/handlers/onboarding.py#L178-L184) (если COMMUNITY_BONUS недоступен или уже использован — скип шага сразу на PRESET_SELECTION).

```
Шаг 0. get_or_create_user (новый id):
       onboarding_step = "LANGUAGE" по умолчанию.

Шаг 1. LANGUAGE (экран выбора RU/EN, L20-L25 main.ftl):
       Callback: onboarding_language_ru | onboarding_language_en
       → user.language_code = выбранный
       → user.onboarding_step = "COMMUNITY_BONUS"
          (ЕСЛИ COMMUNITY_GROUP_ID/link задан и is_community_bonus_used=False
            ИНАЧЕ → "PRESET_SELECTION" сразу)

Шаг 2. COMMUNITY_BONUS (экран оффера +48 ч VIP):
       community-bonus-screen + 3 кнопки:
          [🎁 Вступить в чат]       URL
          [✅ Получить бонус]       verify_community_join
          [Вступить позже]         dismiss_community_bonus

       Ветка verify_community_join:
           (a) _verify_gate_resources_membership(bot, user_id) →
               is_community_member и is_news_ok + gate_approved раздельно
           (b) is_community_member = True → billing_service.apply_community_bonus
               → начисляет 48 часов, is_community_bonus_used=True
               → user.onboarding_step = "PRESET_SELECTION"
               → redis.set_gate_status(gate_approved)
           (c) is_community_member = False → toast «Сначала вступите в чат»

       Ветка dismiss: → onboarding_step = "PRESET_SELECTION" (шаг пропущен)

Шаг 3. PRESET_SELECTION (Setup Wizard 3 пресета + skip):
       3 профиля стратегии:
          ⚡ СКАТ (SCALPER 8k, 5k cascade, PERCENT режим)
          ⚖️ BALANCED (20k/15k)
          🛡 CONSERVATIVE (100k/80k USD MODE)
       [Пропустить] (skip_onboarding_preset)

       Ветка apply_onboarding_preset_<PRESET> или skip:
           (a) IF is_trial_used == False:
                 → activate_trial() → is_trial_used=True
                 → issue_bonus_subscription(hours=TRIAL_DURATION_DAYS*24)
                   TRIAL_DURATION_DAYS = 1 в config (24 часа)
           (b) complete_user_setup():
                 is_setup_completed=True
                 onboarding_step="COMPLETED"
           (c) invalidate_user_cache(id)
           (d) render_main_menu(STATE_VIP_ACTIVE)
```

### 7.2 Суммирование итогового триала = 3 дня

| Составляющая триала | Источник | Длительность | Поле в config.py |
|---|---|---|---|
| Базовый trial-бонус (активация is_trial_used) | `billing_service.issue_bonus_subscription` в onboarding preset-step | 24 ч (1 сутки) | `TRIAL_DURATION_DAYS = 1` [L79](file:///root/signal_bot/src/core/config.py#L79) |
| Community Bonus (за чат) | `billing_service.apply_community_bonus` в шаге COMMUNITY_BONUS | 48 ч (2 суток) | `COMMUNITY_BONUS_HOURS = 48` [L80](file:///root/signal_bot/src/core/config.py#L80) |
| **Итого максимум** (идеальный сценарий) | | **72 ч = 3 дня** | `FREE_TRIAL_TOTAL_DAYS = 3` (целевое значение, для справки/тестов [config.py:L82](file:///root/signal_bot/src/core/config.py#L82)) |
| Итого (без community бонуса) | Пользователь откажется от бонуса в шаге 2 | 24 ч = 1 сутки | |

---

## 8. Архитектурный журнал решений и отклонений (Decisions & Deviations Log)

Журнал фиксирует **фактические решения в коде**, расходящиеся с первоначальным IMPLEMENTATION_PLAN.md, и поясняет WHY.

| # | Исходный план (IMPLEMENTATION_PLAN.md) | Реализация в коде | WHY (обоснование) |
|---|---|---|---|
| **1** | Прессет FREE_NOISE threshold=2000, cascade=1500 USD (Фаза 1) | threshold=3000, cascade=2000 [config.py:L150-L151](file:///root/signal_bot/src/core/config.py#L150-L151) | Внедрено более умеренное «шумное» значение, чтобы не вызывать 1000 алертов/сутки (был риск попасть под антиспам Telegram). 3000/2000 ≈ в 1,5 раза выше MVP-значения. |
| **2** | FREE_NOISE: alert_rsi=True (RSI алерты включены), только CVD=False [IMPLEMENTATION_PLAN.md:L30](file:///root/signal_bot/IMPLEMENTATION_PLAN.md#L30) | FREE_NOISE: `alert_rsi=False, alert_cvd=False` (оба выключены) [config.py:L166-L167](file:///root/signal_bot/src/core/config.py#L166-L167) | Максимальное ценностное расслоение между тарифами. CVD — ключевая платная фича; RSI-ветка тонкой настройки полос — также сильный аргумент в пользу VIP, так что на Free полностью выключена, а не просто «узкая полоса 40/60». |
| **3** | Встраивание инлайн-кнопок каналов + verify в главное меню STATE_FREE_PAUSED (Фаза 5, L117-L121) | Выделенный **подэкран Gate Screen** (`render_gate_unlock_screen`), CTA-слот меню = единственная кнопка `open_gate_unlock_screen` [commands.py:L191-L263](file:///root/signal_bot/src/bot/handlers/commands.py#L191-L263) и [main_kb.py:L133-L138](file:///root/signal_bot/src/bot/keyboards/main_kb.py#L133-L138). | Причина 1: монолитность статического футера (3 нижних ряда всегда одинаковые — muscle memory, нет прыгающих кнопок). Причина 2: футер уже содержит `Чат сообщества ↗`. Добавление второй ссылки в CTA-слот создало бы дубликат и визуальный шум. |
| **4** | Paywall баннер внутри меню настроек (`paywall-settings-locked-banner`) (Фаза 4, L99 и локали) | Баннер **не добавлен в caption**. Вместо него: (а) Early Exit модалка `paywall-settings-locked-alert` (show_alert=True) на каждый клик, (б) визуальная CTA-кнопка `kb-settings-buy-vip` в footer клавиатур всех подэкранов настроек (_append_vip_unlock_button). | Paywall баннер в caption-подписи заставлял бы перечитывать caption-описание порогов заново (VIP-пользователь его не видит, captions у Free/VIP одинаковые). _append_vip_unlock_button — менее навязчивый, при этом на 1 клик ближе к конверсии («ты на экране настроек → видишь кнопку «купи» снизу»). Ключ `paywall-settings-locked-banner` оставлен в ftl-локалях как legacy-запас. |
| **5** | Нет явного тумблера «глобальная пауза сигналов» | Добавлено поле `is_signals_enabled` (default True [models.py:L20](file:///root/signal_bot/src/database/models.py#L20)) + хендлер `toggle_global_signals` без paywall-проверки [settings.py:L510-L530](file:///root/signal_bot/src/bot/handlers/settings.py#L510-L530). | Критический UX + compliance: пользователь Free-tier, не купивший VIP, **не может сам перенастроить частоту** (Paywall). Если поток шумный (100+ алертов/сутки), у него ДОЛЖЕН быть способ остановить бота иначе — пожалуется в BotFather Report Spam, система получит spam-score + риск блокировки бота. Проверка доставки `is_signals_enabled=False → continue` стоит **до gate-проверки**, для экономии CPU даже если «всё равно не отправили бы». |
| **6** | Один Telegram-канал с сигналами (как у @whale_alert) в качестве альтернативного канала доставки | Отказ полностью. Весь поток идёт в **личные сообщения бота** (1-to-1 с пользователем). | (а) Упрощение инфраструктуры: 1 пайплайн delivery вместо 2; нет необходимости администрировать 3-й Telegram-ресурс. (б) Персонализация: VIP получают персональные фильтры, Free получают индивидуальный gate-статус — в публичном канале это невозможно (один поток для всех). (в) Отсутствие «public signal leakage»: в публичном канале сигналы были бы доступны без подписки. |
| **7** | Проверка членства в runtime ВСЕГДА идёт через кэш Redis | Cache-fallback path работает через OR; но при **cache miss** messenger_worker **идёт напрямую в Telegram API** и пишет результат. | Anti-429: TTL=600 секунд означает, что 1 пользователь генерирует максимум 1 вызов Telegram API в 10 минут × 2 ресурса (News + Chat) = 0,003 QPS/пользователя. Для 1000 Free это 3 QPS — в рамках лимитов Telegram (30/s global). Бонус: проверка «прямым вызовом» работает для пользователей, удаливших кэш ручным перезапуском Redis. |
| **8** | После verify_gate_sub — только toast | После успешной верификации членства выполняется **перерисовка главного меню** `render_main_menu` [onboarding.py:L503-L513](file:///root/signal_bot/src/bot/handlers/onboarding.py#L503-L513). | Clean State Model effect: пользователь 🔴 STATE_FREE_PAUSED после успешной проверки **должен немедленно увидеть** новое CTA-кнопку (теперь 🟡 STATE_FREE_ACTIVE, CTA «Перейти на VIP»). Без перерисовки меню пользователь видил бы старую кнопку «🔓 Включить сигналы», кликнув по которой снова попал бы в Gate Screen (dead loop UX). |

---

## 9. Руководство по тестированию и верификации (Testing & Verification Guide)

Требования к тестовому окружению:
- Переменные окружения: `NEWS_CHANNEL_ID`, `NEWS_CHANNEL_URL`, `COMMUNITY_GROUP_ID`, `COMMUNITY_GROUP_LINK` заданы корректно (используется боевой/тестовый Telegram-бот).
- Режим `DEV_MODE=False` (иначе поведение Gatekeeper аналогично, но нет смысла тестировать 429-защиту).

### 9.1 Чек-лист №1: Тест перехода в 🔴 STATE_FREE_PAUSED (заморозка при выходе из каналов)

Предварительные условия:
- Пользователь находится в STATE_VIP_ACTIVE (например, админ начислил 1 день VIP) и в обоих ресурсах.

| Шаг | Действие | Ожидаемый результат |
|---|---|---|
| 1. | **Выйти** пользователем из Новостного канала ИЛИ из Чата сообщества (достаточно 1). | |
| 2. | Подождать `GATE_CACHE_TTL_SEC = 600 с (10 мин)` или выполнить в Redis `DEL csl:gate:{user_id}` (сброс кэша вручную для быстроты). | |
| 3. | Подождать следующего прохода messenger_worker (пока приходит очередной сигнал) или вручную эмулировать: | |
| | `redis-cli` → `PUBLISH csl:cache_invalidation "{user_id}"` | Invalidation пробежит по подписчикам. |
| 4. | Открыть `/start` или нажать back_to_main в боте. | Статус пользователя: **❌ Не активна.** (ключ `main-menu-status-free-paused`). CTA-кнопка = **🔓 Включить бесплатные сигналы** (`open_gate_unlock_screen`). |
| 5. | Дождаться сигнала в runtime (другой пользователь с VIP получает алерт). | Тестовый user **НЕ получает алерт** — сработал gate=0. В логах messenger_worker присутствует `Gatekeeper error during send user_id=… skip delivery`. |

### 9.2 Чек-лист №2: Подэкран разблокировки и кнопка проверки (🔴 → 🟡)

| Шаг | Действие | Ожидаемый результат |
|---|---|---|
| 1. | Находясь в STATE_FREE_PAUSED, нажать кнопку **🔓 Включить бесплатные сигналы**. | Открыт Gate Screen: `gate-unlock-screen` caption 2 пункта + 4 ряда (News URL, Chat URL, Verify, Home). |
| 2. | **Вступить** в оба ресурса (News + Chat), кнопка не нажимать. | |
| 3. | Нажать **✅ Проверить и включить сигналы** (`verify_gate_sub`). | Toast модальное: `gate-subscription-verified = ✅ Подписка подтверждена! Бесплатный поток возобновлён.` |
| 4. | Автоматический редирект (перерисовка меню) | Пользователь видит статус «🆓 Бесплатный тариф» (STATE_FREE_ACTIVE). Верхняя CTA-кнопка: **💎 Перейти на VIP (Убрать шум)**. |
| 5. | Redis-проверка. | `redis-cli GET csl:gate:{user_id}` → `"1"`; `TTL csl:gate:{user_id}` → ~600 секунд. |

### 9.3 Чек-лист №3: Проверка доставки сигналов VIP vs Free

| Шаг | Действие | Ожидаемый результат |
|---|---|---|
| Конфигурация A: VIP | Пользователь находится в STATE_VIP_ACTIVE; ждём сигнал CASCADE (Chart Always Render). | В приходящем алерте: присутствует **PNG-график** (прикреплена фотография), в тексте присутствуют блоки CVD и RSI (если эти тумблеры у пользователя включены — по умолчанию ВКЛ). |
| Конфигурация B: Free-ACTIVE (в каналах) | Тот же пользователь, но руками в PostgreSQL выставить `subscription_end = NULL` и вызвать `degrade_user_to_free_tier(session, user.id)`. Ждём тот же сигнал. | (1) Алерт приходит как **чисто текстовое сообщение** (photo=none), без графика. (2) В тексте: `show_cvd=False, show_rsi=False` → блоки отсутствуют, даже если пользователь раньше их включал (degrade перетёр все 18 полей). (3) Частота пришедших алертов: примерно 3-5 раз выше VIP того же рынка (пресет FREE_NOISE threshold 3000$ намного ниже VIP BALANCED $20k). |

### 9.4 Чек-лист №4: Работа Bouncer (эмуляция экспирации)

| Шаг | Действие | Ожидаемый результат |
|---|---|---|
| 1. | Подготовить пользователя: подписка 30 дн, state VIP_ACTIVE, находится в каналах, auto_renewal=False. | |
| 2. | В PostgreSQL руками сдвинуть subscription_end на `now - 2 минуты` (гарантированно прошедшее). | |
| 3. | Дождаться очередного прохода Bouncer worker (интервал ≤ 15 мин) или вызвать `bouncer_worker` однократно через скрипт. | |
| 4.1 | Fork A: пользователь в каналах. | Пользователь получает сервисное сообщение `bouncer-degraded-to-free-notification`. В БД `subscription_end is NULL`. Все 18 настроек = FREE_NOISE. Redis gate: `"1"`. Кэш аналитики invalidated (`user_cache_refresher_task` выполнен). |
| 4.2 | Fork B: пользователь **выходит из каналов** после шага 1, до запуска bouncer. | Пользователь получает сообщение `bouncer-expired-unsubscribed-notification` **с 3-кнопочной клавиатурой** (News, Chat, Verify). Redis gate: `"0"`. |
| 5. | Проверка idempotency: Bouncer запускается повторно. | Повторного уведомления НЕТ (поле subscription_end уже None). `get_expired_users(session)` не возвращает его в выборке (WHERE subscription_end is NOT None). |

### 9.5 Чек-лист №5: Paywall Alert на все 11 точек модификации настроек

Предварительные условия: пользователь в STATE_FREE_ACTIVE, настройки читаются, но изменить нельзя.

| # | Действие | Ожидаемый show_alert |
|---|---|---|
| 1. | Клик «USD / PERCENT» (режим) в экране filters. | 💎 Настройка фильтров и пресетов доступна только в VIP-тарифе. popup. Экран settings НЕ меняется (caption тот же). |
| 2. | Клик «Установить $ порог объёма» → set_threshold FSM Prompt. | Попап, FSM `SettingsStates.waiting_for_threshold` НЕ запущен: следующее текстовое сообщение воспринимается ботом как обычное (не парсится как число). |
| 3. | Cascade threshold, OI thresholds, MCAP 4 поля. | Идентичный Paywall Alert. |
| 4. | Клик тумблера «Cascade / Volume / Squeeze / Longs / Shorts / OI / RSI / CVD» (8 штук). | Paywall Alert. Состояние toggle-значков НЕ переключается (в БД запись не пошла). |
| 5. | Экран пресетов → клик «Применить BALANCED» / «Применить SCALPER» / «Применить CONSERVATIVE». | Paywall Alert. |
| 6. | RSI-экран → пресеты Conservative / Disabled / ручной ввод. | Paywall Alert на все 4 действия. |
| 7. | Контроль: тумблер **Сигналы: Вкл/Выкл** (toggle_global_signals). | **НЕТ popup**. Значок обновляется на `🔕`/`🔔`. is_signals_enabled поле в БД действительно обновилось (SELECT проверка). |

---

## Приложение A: Справочник callback-data и FSM-состояний

### A.1 Clean State Model — CTA-слот и состояния

| Callback | Назначение | Состояние-источник |
|---|---|---|
| `activate_trial` | Открывает экран предложения пробного периода с ссылкой на новостной канал | 🟢 TRIAL_AVAILABLE |
| `confirm_trial_activation` | Прямая активация 24-часового базового триала | TRIAL_AVAILABLE (trial-screen) |
| `buy_subscription` | Переход в wallet/shop (общий для renew/upgrade) | 💎 VIP_Active≤5d, 🟡 FREE_ACTIVE, settings-paywall |
| `open_gate_unlock_screen` | Открывает подэкран разблокировки (баннер 2 пункта) | 🔴 FREE_PAUSED |
| `verify_community_join` | Универсальная проверка: бонус OR gate (экран community bonus или Bouncer-уведомление) | COMMUNITY_BONUS step |
| `verify_gate_sub` | Алиас-alias с тем же универсальным обработчиком | Gate Screen |
| `back_to_main` | Возврат в главное меню | Любой подэкран |

### A.2 Настройки Paywall vs Non-Paywall

| Callback/State | Paywall? |
|---|---|
| `toggle_threshold_mode` | ✅ VIP-only |
| `set_mcap_pct/set_mcap_min_usd/set_mcap_cas_pct/set_mcap_cas_min_usd` → 4 FSM | ✅ VIP-only |
| `set_threshold` → FSM waiting_for_threshold | ✅ VIP-only |
| `set_cascade_threshold` → FSM waiting_for_cascade_threshold | ✅ VIP-only |
| `menu_oi_thresholds` → waiting_for_oi_thresholds | ✅ VIP-only |
| `toggle_cascade / _volume / _squeeze / _longs / _shorts / _oi / _rsi / _cvd` → 8 шт | ✅ VIP-only |
| `apply_setting_preset_{SCALPER/BALANCED/CONSERVATIVE}` | ✅ VIP-only |
| `set_rsi_preset_{CONSERVATIVE/BALANCED/SCALPER/DISABLED}` | ✅ VIP-only |
| `set_rsi_manual_start` → waiting_for_rsi_thresholds | ✅ VIP-only |
| **`toggle_global_signals`** | **❌ ДОСТУПНО ВСЕМ** |

### A.3 Redis-ключи, участвующие в подсистеме

| Ключ (pattern) | Содержимое | TTL | Кто пишет |
|---|---|---|---|
| `csl:gate:{user_id}` | Строка `"1"` или `"0"` | `GATE_CACHE_TTL_SEC=600` | Bouncer, Onboarding verify, Messenger fallback |
| `csl:cache_invalidation` | Pub/Sub channel, payload `"{user_id}"` или `"ALL"` | — | `invalidate_user_cache()` (bouncer/apply_preset/bonus/billing) |
| `csl:msg:history:{target_id}:{symbol}:{side_label}` | JSON AlertHistoryEntry для анти-спама same-coin | 3600 (1ч) | Messenger worker dispatch |

### A.4 Локализация: ключи ftl по сегментам

| Категория | Ключи (ru/main.ftl как эталон) |
|---|---|
| Menu-статус 4 states | `main-menu-status-vip-active / -free-active / -free-paused / -trial-available` |
| Gate Screen + verify | `gate-unlock-screen`, `gate-button-verify-action`, `gate-subscription-verified`, `gate-subscription-not-found`, `gate-unsubscribed-warning` |
| Bouncer worker (ru/worker.ftl) | `bouncer-trial-expiry-warning / -subscription-expiry-warning / -auto-renewal-success / -auto-renewal-failed-balance / -degraded-to-free-notification / -expired-unsubscribed-notification` |
| Bouncer gate keyboard labels | `gate-button-channel`, `gate-button-chat`, `gate-button-verify` |
| Onboarding + Bonus | `onboarding-language-screen / -presets-screen`, `community-bonus-screen`, `community-bonus-button-*`, `trial-screen / trial-activated-screen` |
| Paywall alerts + banners | `paywall-settings-locked-alert`, `paywall-settings-locked-banner` (legacy-reserve) |
| Settings UI labels | `kb-settings-signals-on / -off` (master-toggle), `kb-settings-buy-vip` (append CTA) |

---

## Приложение B: Быстрый goto-карта кода по компонентам

| Компонент | Ключевой файл и диапазон строк |
|---|---|
| Resolver 4-состояний | [commands.py:L49-L66](file:///root/signal_bot/src/bot/handlers/commands.py#L49-L66) + [main_kb.py:L30-L43](file:///root/signal_bot/src/bot/keyboards/main_kb.py#L30-L43) |
| Главное меню — 3-рядный футер + CTA-слот | [main_kb.py:L46-L146](file:///root/signal_bot/src/bot/keyboards/main_kb.py#L46-L146) |
| Подэкран Gate Screen (рендер + 4 ряда) | [commands.py:L191-L263](file:///root/signal_bot/src/bot/handlers/commands.py#L191-L263) |
| Универсальный verify_gate_subscription (бонус + gate редирект на меню) | [onboarding.py:L428-L529](file:///root/signal_bot/src/bot/handlers/onboarding.py#L428-L529) |
| Gatekeeper Redis-методы set/get | [redis_bus.py:L315-L360](file:///root/signal_bot/src/core/redis_bus.py#L315-L360) |
| Gatekeeper AND-проверка двух ресурсов (Bouncer) | [bouncer.py:L148-L192](file:///root/signal_bot/src/services/bouncer.py#L148-L192) |
| Gatekeeper AND-проверка (Messenger runtime fallback) | [messenger_worker.py:L135-L178](file:///root/signal_bot/src/services/messenger_worker.py#L135-L178) |
| Runtime delivery shard VIP vs FREE + no-chart | [messenger_worker.py:L538-L630](file:///root/signal_bot/src/services/messenger_worker.py#L538-L630) |
| Деградация на FREE_NOISE (18 полей, with_for_update) | [user_service.py:L176-L226](file:///root/signal_bot/src/database/crud/user_service.py#L176-L226) |
| Bouncer worker + Fork A/B degradation уведомления | [bouncer.py:L235-L309](file:///root/signal_bot/src/services/bouncer.py#L235-L309) |
| Paywall check на тумблерах каскадов/настроек | [settings.py:L540-L542](file:///root/signal_bot/src/bot/handlers/settings.py#L540-L542) (catch-all) + [L153-L155](file:///root/signal_bot/src/bot/handlers/settings.py#L153-L155) (mode toggle) |
| Master тумблер is_signals_enabled (НЕ paywall) | [settings.py:L510-L530](file:///root/signal_bot/src/bot/handlers/settings.py#L510-L530) |
| Append CTA-кнопки «💎 Купи VIP» к settings клавиатурам | [settings_kb.py:L13-L23](file:///root/signal_bot/src/bot/keyboards/settings_kb.py#L13-L23) |
| Preset FREE_NOISE (пороги, CVD/RSI выключены) | [config.py:L148-L168](file:///root/signal_bot/src/core/config.py#L148-L168) |
| is_signals_enabled фильтр ДО доставки | [messenger_worker.py:L554-L556](file:///root/signal_bot/src/services/messenger_worker.py#L554-L556) |
| is_signals_enabled → мин. порог системы (не учитываем off) | [analyzer.py:L120-L122](file:///root/signal_bot/src/services/analyzer.py#L120-L122) |
| Onboarding 3-step machine (LANGUAGE → BONUS → PRESET) | [onboarding.py:L178-L630](file:///root/signal_bot/src/bot/handlers/onboarding.py#L178-L630) |
| Базовый триал 1 сутки + Community Bonus +48ч | `TRIAL_DURATION_DAYS`=1 [config.py:L79](file:///root/signal_bot/src/core/config.py#L79), `COMMUNITY_BONUS_HOURS`=48 [config.py:L80](file:///root/signal_bot/src/core/config.py#L80) |
| Invalidation Pub/Sub engine cache | [analyzer.py:L146-L153](file:///root/signal_bot/src/services/analyzer.py#L146-L153) |
| Messenger listener invalidation | [messenger_worker.py:L360-L393](file:///root/signal_bot/src/services/messenger_worker.py#L360-L393) |
