# 🗄 Архитектура Базы Данных

## 📊 Общая схема
Используется **PostgreSQL** с асинхронным драйвером `SQLAlchemy 2.0`. Все финансовые операции проходят через систему Ledger (журналирование транзакций).

---

## 📑 Таблицы

### 1. `users` (Пользователи)
Хранит профили пользователей, настройки алертов и финансовое состояние.
- `id` (BigInteger, PK): Telegram ID.
- `username` (String): Юзернейм в TG.
- `balance` (Float): Текущий баланс (USDT). Округляется до 2 знаков.
- `referrer_id` (BigInteger, FK): ID пригласившего пользователя.
- `subscription_end` (DateTime): Дата окончания подписки.
- `is_trial_used` (Boolean): Флаг использования пробного периода.
- `is_admin` / `is_blocked` (Boolean): Права доступа.
- *Настройки алертов:* Пороги ликвидаций, тумблеры OI, CVD, RSI.

### 2. `transactions` (История транзакций)
Ledger-таблица для всех изменений баланса.
- `id` (Integer, PK): Автоинкремент.
- `user_id` (BigInteger, FK): Ссылка на пользователя.
- `amount` (Float): Сумма (положительная для DEPOSIT/REWARD, отрицательная для WITHDRAW).
- `type` (String): Тип операции (`DEPOSIT`, `WITHDRAW`, `REWARD`).
- `description` (String): Описание операции для истории.
- `created_at` (DateTime): Время записи.

### 3. `invoices` (Счета на оплату)
Отслеживание внешних платежей через CryptoPay.
- `id` (Integer, PK): Автоинкремент.
- `user_id` (BigInteger, FK): Ссылка на пользователя.
- `amount` (Float): Сумма к оплате.
- `tariff_days` (Integer): На сколько дней продлевается подписка.
- `crypto_pay_id` (String, Unique): Внешний ID счета в CryptoPay.
- `status` (String): Статус счета (`PENDING`, `PAID`, `EXPIRED`).
- `created_at` (DateTime): Время создания.

### 4. `liquidations` (Аналитика)
Хранение данных о ликвидациях для формирования дашбордов.
- `symbol` (String, Index): Тикер.
- `value` (Float, Index): Объем ликвидации в $.
- `timestamp` (DateTime, Index): Время события.

---

## 🛡 Безопасность и Целостность
1. **Race Conditions:** При изменении баланса используется блокировка `SELECT FOR UPDATE` на уровне строки пользователя.
2. **Атомарность:** Пополнение баланса и запись транзакции всегда происходят в одной БД-транзакции.
3. **Точность:** Все финансовые расчеты в коде проходят через `round(val, 2)`.
4. **Констрейнты:** Установлены `ForeignKey` и `nullable=False` для обеспечения ссылочной целостности.
