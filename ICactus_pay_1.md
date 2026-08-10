# План реализации: Интеграция CactusPay H2H

## Фаза 1: Рефакторинг моделей и конфигурации
**Цель:** Перейти от простых цен к объектам тарифов и подготовить БД к хранению рублевых данных.

1.  **`src/core/dto.py`**:
    *   Создать `TariffDTO(days, price_usd, price_rub)`.
2.  **`src/core/config.py`**:
    *   Обновить `TARIFFS`: перевести из `dict[int, float]` в `dict[int, TariffDTO]`.
    *   Добавить константы: `CACTUS_MERCHANT_ID`, `CACTUS_SECRET_KEY`, `CACTUS_API_URL`.
3.  **`src/database/models.py`**:
    *   Добавить в `Invoice` поля:
        *   `currency`: `String(3)` (по умолчанию 'USD').
        *   `amount_expected_native`: `Float` (сумма в валюте провайдера, например, 3200.15 RUB).
        *   `amount_actual_native`: `Float` (сколько реально пришло в RUB).
        *   `expires_at`: `DateTime` (критично для P2P-карт).
    *   **Alembic:** Сгенерировать и применить миграцию.

---
### ⚠️ Отхождение от плана (Senior Architect Note)
**Причина:** Немедленная обратная совместимость существующей логики.
После замены `TARIFFS: dict[int, float]` на `dict[int, TariffDTO]` **все** существующие места использования (`billing_kb.py`, `shop.py`, `billing_processor.py`) немедленно ломаются, так как ожидают `float`, а получают объект.
**Корректировка:** В рамках **Фазы 1** дополнительно обновлены все 7 точек доступа к `TARIFFS` — вместо `config.TARIFFS.get(days)` теперь читается `.price_usd` из объекта (`tariff.price_usd`).
`SUB_MONTHLY_PRICE` переведён на `Field(default_factory=lambda: 25.0)`, так как класс `Settings` не может инициализировать поле через доступ к другому полю с `Field(default_factory=...)` на этапе определения класса.

---
### ⚠️ Отхождение от плана (Фаза 2 — Cactus API Auth)
**Причина:** Расхождение плана с реальной документацией CactusPay.
План предписывал MD5-подпись `md5(merchant_id + amount + order_id + secret_key)` для **каждого** запроса.
Реальная документация CactusPay API (страницы `create-payment` / `payment-info`) использует **простой токен** в JSON-body: поле `token` (ключ магазина, он же `CACTUS_SECRET_KEY`). MD5-подпись в текущей версии API **не запрашивается**.
**Корректировка:** Метод `_generate_sign` оставлен в классе `CactusClient` как задел на будущее / для верификации webhook (если потребуется), но основные запросы (`create_payment`, `get_status`) шлют `token` в body без хеширования, строго по доке шлюза.

---

## Фаза 2: Слой API (Cactus Gateway)
**Цель:** Создать надежный клиент для взаимодействия с CactusPay.

1.  **`src/services/cactus_client.py` (Новый файл)**:
    *   Реализовать класс `CactusClient`.
    *   **Метод `_generate_sign(amount, order_id)`**: Хеширование `md5(merchant_id + amount + order_id + secret_key)`.
    *   **Метод `create_payment(amount, order_id)`**: POST запрос на `/payment`. Должен поддерживать возврат реквизитов H2H (card_number, bank_name).
    *   **Метод `get_status(order_id)`**: GET запрос на `/payment-info`.
    *   **Mock-режим:** В `DEV_MODE` возвращать фейковую карту `2200 **** 1234` и статус `success` при ручной правке БД.

---

## Фаза 3: Слой логики (Billing Processor Extension)
**Цель:** Научить «Мозг» системы обрабатывать рублевые платежи.

1.  **`src/services/logic/billing_processor.py`**:
    *   Обновить `process_payment_update` для случая `provider == "CACTUS"`.
    *   **Логика начисления:** 
        1. Если статус от Cactus `success` (строка `ACCEPT` в реальном API).
        2. Процессор находит в `payload` инвойса **поле `u`** (цена USDT, зафиксированная в момент создания; см. отхождение ниже).
        3. Берёт `price_usd` из фиксации `payload["u"]` (Primary) или `config.TARIFFS[days].price_usd` (Fallback).
        4. Начисляет на баланс именно эту сумму в USDT (строгий Delta-Accounting по USDT; tolerance-логика 0.5 USD для CACTUS **отключена**).
        5. Поле `amount_actual_native` обновляется из Cactus `total_amount` (кол-во RUB, факт. пришедших); это информационное поле, не влияет на расчёт баланса.
        6. Активирует подписку (если intent_action == sub) строго как у Cryptomus: списание price_usd → продление days.
2.  **`src/services/payment_worker.py`**:
    *   Для `provider == "CACTUS"` срок жизни реквизитов определяется **строго из `expires_at`** в БД, а не из константы `INVOICE_EXPIRE_MINUTES = 120` (P2P-карты живут ~8 минут, не 2 часа).
    *   Cactus-инвойсы автоматически попадают в polling (т.к. провайдер != MANUAL), дополнительная SQL-правка не требуется.
3.  **`src/database/crud/billing_service.py`**:
    *   `create_invoice` расширен параметрами `currency`, `amount_expected_native`, `amount_actual_native`, `expires_at` (Backward compatible — default "USD"/0/0/None).
    *   `update_invoice_record` расширен необязательным kwarg `amount_actual_native`.

---
### ⚠️ Отхождение от плана (Фаза 3 — Price-At-Creation Safety)
**Причина:** Гонка изменения тарифа между moment-ом создания инвойса и моментом подтверждения платежа.
Оригинальный план предписывал при подтверждении брать цену из `config.TARIFFS[30].price_usd` **во время обработки**. Если админ поменяет тариф (например, 30д с 25 → 30 USDT) пока пользователь переводит рубли — получим неконсистентность: пользователь согласился на 25 USDT, а мы начислим/спишем 30.
**Корректировка:** В payload Cactus-инвойса будет записано поле `"u"` (price_usd_at_creation). При подтверждении начисляется **именно эта сумма**, а из config берётся только Fallback для старых инвойсов. Tolerance (`PAYMENT_TOLERANCE_USD=0.5`) для CACTUS-провайдера тоже принудительно отключен — мы сравниваем `api_amount == target_usdt` буквально.

---



## Фаза 4: Пользовательский интерфейс и выбор методов (UI/UX Transformation)
**Цель:** Реализовать промежуточный шаг выбора способа оплаты (Крипта vs Карта) и обеспечить вывод реквизитов для рублевых платежей.

### 4.1. Слой клавиатур (`src/bot/keyboards/billing_kb.py`)
*   **Метод `get_payment_method_selection_kb(days, *, show_cactus, show_manual)`**: 
    Экран выбора после клика по тарифу.
    *   Кнопка 1: `💳 Оплата картой РФ (CactusPay)` → `pay_cactus_card_{days}`
    *   Кнопка 2: `⚡ Оплата через СБП (CactusPay)` → `pay_cactus_sbp_{days}`
    *   Кнопка 3: `₿ Оплата криптовалютой (USDT TRC20)` → `pay_manual_{days}`
    *   Кнопка 4: `⬅️ Назад` → в меню выбора тарифов (`buy_subscription`).
    *   Flag-параметры определяют доступность по факту настроенных кредов.

*   **Метод `get_cactus_payment_kb(external_id: str)`**:
    Клавиатура для H2H-экрана реквизитов.
    *   Кнопка 1: `✅ Я оплатил. Проверить статус` → `cactus_check_{external_id}`
    *   Кнопка 2: `⬅️ Назад` → возврат к выбору тарифов.

### 4.2. Слой хендлеров (`src/bot/handlers/shop.py`)
*   **Рефакторинг `callback_process_purchase`**:
    1. Если `balance < price` — вместо авто manual-flow отправляет экран выбора метода.
    2. Доступность методов детектится по `cactus_client.enabled` и `PAYMENT_MANUAL_WALLET`.
    3. Если ни один метод не настроен — `shop-no-payment-methods`.

*   **Хендлеры `callback_pay_cactus_card_` / `callback_pay_cactus_sbp_`**:
    Объединяются в единую функцию `_start_cactus_payment_flow(method)`:
    1. Берёт `price_rub` / `price_usd` из `config.TARIFFS[days]`.
    2. Если баланс > 0 — native_amount масштабируется линейно (`(amount_to_pay_usd / price_usd) * price_rub`).
    3. Вызывает `cactus_client.create_payment(amount_rub, order_id, h2h=True, method=card|sbp)`.
    4. Создаёт Invoice с `provider=CACTUS`, `currency=RUB`, `payload={'a':'sub','d':days,'u':amount_to_pay_usd}` (price_at_creation в поле `u`), `expires_at` из `requisite.until_timestamp`.
    5. Рендерит Zero-Friction H2H-экран: card_number / receiver_phone прямо в HTML.
    6. Выводит countdown `MM:SS` в формате `_format_cactus_countdown_seconds`.

*   **Хендлер `callback_cactus_check_payment_`**:
    User-invoked trigger process_payment_update — мгновенно триггерит polling-path вместо ожидания воркера 30–180 сек.

### 4.3. Дизайн экранов (Локализация)
Симметричное обновление `assets/locales/{ru,en}/shop.ftl`:

| Ключ | Назначение |
|---|---|
| `kb-shop-method-cactus-card` | 💳 Оплата картой РФ |
| `kb-shop-method-cactus-sbp` | ⚡ Оплата через СБП |
| `kb-shop-method-crypto-manual` | ₿ Оплата криптой |
| `kb-shop-cactus-check-payment` | ✅ Я оплатил |
| `shop-payment-method-selection` | Экран выбора метода с эквивалентом RUB / USDT |
| `shop-cactus-pay-screen-card` | H2H-экран Карты (16-значный номер в блоки 4-4-4-4 через `_format_card_number`, получатель, банк, countdown, 3 пункта Important) |
| `shop-cactus-pay-screen-sbp` | H2H-экран СБП (телефон / банк / countdown) |
| `shop-cactus-unavailable` / `shop-cactus-expired` / `shop-no-payment-methods` | Защитные тосты |
| `shop-balance-credited-but-auto-activation-skipped` | Safety-экран при расхождении price_at_creation vs текущего тарифа (не удалось авто-активировать) |

### 4.4. Технические нюансы (H2H Flow)
*   `expires_at` в БД заполняется из `requisite.until_timestamp` (Unix time от Cactus), а не из локальной константы.
*   Countdown в сообщении пересчитывается относительно того же until_timestamp.
*   Safety payload: `{"u": amount_to_pay_usd}` — целевая сумма начисления в USDT (Price-At-Creation).

---
### ⚠️ Отхождение от плана (Фаза 4 — Отдельные callback для card vs sbp вместо единого `pay_method:cactus`)
**Причина:** Строго вложенная навигация (UX-предпочтения пользователя). План предлагал единый экран выбора «card или sbp» после метода «cactus». Итоговая реализация делает card и sbp **отдельными** top-level кнопками на экране выбора метода (3 кнопки: Card, SBP, Crypto). Это сокращает количество кликов на 1 (меньше переходов).

---

## Фаза 5: Фоновая автоматизация + Безопасность Webhook
**Цель:** Опрос статусов CactusPay + строгая валидация сигнатур webhook.

1.  **`src/services/payment_worker.py`** (реализовано в Фазе 3 ранее, здесь суммарно):
    *   `CACTUS` попадает в polling как `!= MANUAL`.
    *   `expires_at` (а не `INVOICE_EXPIRE_MINUTES = 120`) — primary источник истины для закрытия просроченных инвойсов.
2.  **`src/services/cactus_client.py`** — Webhook-utilities (new in Phase 5):
    *   `validate_cactus_webhook_signature(body_bytes, received_signature, secret_key)` — defensive-style: поддерживает MD5/HMAC-SHA256-hex/HMAC-SHA256-base64 через `hmac.compare_digest` (anti timing).
    *   `validate_cactus_webhook_event_payload(dict)` — tolerant извлечение `(order_id, status, amount_rub, cactus_id)` с fallback на разные нотации полей (`order_id`/`orderId`/`invoice_id`, `status`/`payment_status`, и т.д.).
3.  **Webhook-handler endpoint**: не реализовывался в этой сессии (проект не имеет HTTP-router в текущем составе; предполагается подключить в compose при миграции на aiohttp/FastAPI), но security-primitive подготовлена выше.

---
### ⚠️ Отхождение от плана (Фаза 5 — Только utility без webhook-роутера)
**Причина:** В текущей архитектуре проекта **нет HTTP-сервера** (только aiogram long-polling). План Фазы 5 упоминал `/payment/cactus` webhook, но для этого нужно поднимать aiohttp/FastAPI, что выходит далеко за рамки Фазы 5 и затрагивает docker-compose/entrypoints. Реализован Safety-primitive (`validate_cactus_webhook_signature` + `validate_cactus_webhook_event_payload`), чтобы при подключении роутера в будущем не изобретать заново и не допустить неавторизованных запросов.

---

# Подводные камни (Senior Architect Notes для Trae)

1.  **Formatting RUB:** В CactusPay суммы передаются как строки. Нужно следить за форматом (например, `3200.00`). Ошибка в 1 копейку может привести к тому, что платеж не найдется.
2.  **H2H Response:** В `create_payment` CactusPay может вернуть реквизиты в разных полях в зависимости от метода (карта или СБП). Нужно сделать гибкий парсинг.
3.  **Atomicity:** При начислении USDT за рублевый платеж, цена в USDT должна браться из конфига **на момент обработки платежа**, либо сохраняться в `payload` инвойса в момент создания (`price_at_creation`), чтобы защититься от изменения цен в конфиге. Мы будем использовать `price_at_creation` из `payload`.
4.  **Race Conditions:** Помним про Redis-локи. Ручное нажатие "Проверить" и работа воркера не должны привести к двойному начислению за один рублевый перевод.
