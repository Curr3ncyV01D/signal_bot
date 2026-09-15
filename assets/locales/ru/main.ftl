# Main menu, onboarding, and entry flow.

main-menu-status-active = ✅ Активна до { $subscription_end }
main-menu-status-inactive = ❌ Не активна

main-menu =
    👋 Добро пожаловать, <b>{ $full_name }</b>!

    Я профессиональный терминал для мониторинга ликвидаций.
    Вы будете получать уведомления, когда на рынке начнутся сильные движения.

    💎 Подписка: <b>{ $subscription_status }</b>
    💰 Баланс: <b>{ $balance }</b> USDT

    👇 Выберите действие ниже:

trial-button-news-channel = 📢 Новостной канал
trial-button-check-subscription = 🎁 Активировать доступ

onboarding-language-screen =
    🌐 <b>Добро пожаловать / Welcome!</b>

    Выберите язык интерфейса, чтобы завершить настройку.
    Choose your interface language to complete setup.
onboarding-language-selected = Язык сохранен

onboarding-presets-screen =
    🎯 <b>Выберите профиль стратегии</b>

    Это быстрый старт для фильтров CSL. Один клик применит готовые настройки фильтров и включит все основные типы сигналов.

    <b>⚡ Скальпинг</b>
    Использует наши инструменты для поиска аномалий на альтах.
    • Частота сигналов: <b>Высокая</b>
    • Примерный объем ликвидаций: <b>{ $scalper_threshold }</b> $

    <b>⚖️ Сбалансированный</b>
    Гибридный профиль для повседневной торговли.
    • Частота сигналов: <b>Средняя</b>
    • Примерный объем ликвидаций: <b>{ $balanced_threshold }</b> $

    <b>🛡 Консервативный</b>
    Делает упор на крупные движения и высокий шум-фильтр.
    • Частота сигналов: <b>Низкая</b>
    • Примерный объем ликвидаций: <b>{ $conservative_threshold }</b> $
onboarding-preset-button-scalper = ⚡ Скальпинг
onboarding-preset-button-balanced = ⚖️ Сбалансированный
onboarding-preset-button-conservative = 🛡 Консервативный
onboarding-preset-button-skip = Пропустить
onboarding-preset-applied-scalper = Профиль «Скальпинг» применен
onboarding-preset-applied-balanced = Профиль «Сбалансированный» применен
onboarding-preset-applied-conservative = Профиль «Консервативный» применен
onboarding-preset-skipped = Онбординг завершен с дефолтными настройками

community-bonus-screen =
    🎁 <b>Ваш приветственный бонус: + { $hours } часов VIP-доступа!</b>

    Мы строим не просто инструмент, а закрытое сообщество трейдеров. Присоединяйтесь к нашему чату, чтобы:

    🔹 Обсуждать сигналы Bybit в реальном времени.
    🔹 Делиться рабочими стратегиями и настройками.
    🔹 Получать помощь от опытных участников

    <b>Вступите в группу и нажмите кнопку ниже, чтобы мгновенно забрать дополнительные 2 дня подписки</b>
community-bonus-button-join = 🎁 Вступить в чат
community-bonus-button-verify = ✅ Получить бонус
community-bonus-button-later = Вступить позже
community-bonus-unavailable = Бонус сообщества сейчас недоступен.
community-bonus-already-used = Бонус за вступление в сообщество уже получен.
community-bonus-verification-error = Не удалось проверить участие в сообществе. Попробуйте позже.
community-bonus-join-required = Сначала вступите в сообщество, затем повторите проверку.
community-bonus-activation-failed = Не удалось начислить бонусный доступ. Попробуйте позже.
community-bonus-granted-toast = +{ $hours }ч. доступа начислено
community-bonus-later-toast = Сможете активировать бонус позже из главного меню

trial-unavailable-news-channel = Триал через канал недоступен: NEWS_CHANNEL_ID не задан.
trial-screen =
    🎁 <b>Пробный период на 24 часа</b>

    Мы предоставляем вам тестовый доступ на 24 часа.
    Также приглашаем вас в наш новостной канал, чтобы следить за обновлениями и важными анонсами.
trial-mode-disabled = Режим каналов отключен. Активация триала через канал недоступна.
trial-already-used = Пробный период уже был использован.
trial-activation-failed = Не удалось активировать пробный период. Попробуйте позже.
trial-activated-screen =
    ✅ <b>Пробный период на 24 часа активирован</b>

    💎 Мы рекомендуем вам открыть <b>меню настроек</b> и настроить фильтры сигналов по своему вкусу! 💎
trial-activated-toast = Доступ на 24 часа активирован

system-status-title = Система активна
status-refresh-success = ✅ Статус успешно обновлен!
status-refresh-no-changes = 🔄 Данные не изменились
status-refresh-error = Ошибка обновления
status-screen =
    { $status_emoji } <b>{ $title }</b>

    🌐 Соединения: <b>{ $active_pool }</b> / <b>{ $total_pool }</b>
    💓 Последний сигнал API: <b>{ $latency }</b> назад

    📡 Мониторинг пар: <b>{ $active_symbols }</b>
    🧠 Событий в кэше: <b>{ $total_events }</b>
    { $queue_status } <b>Очередь обработки:</b> <b>{ $queue_size }</b>
    📊 Нагрузка: CPU <b>{ $cpu_pct }</b>% | RAM <b>{ $ram_pct }</b>%

    🕒 Время работы: <b>{ $uptime }</b>
    🕒 Время сервера: { $server_time } UTC

kb-main-trial = 🎁 Пробный период
kb-main-community-bonus = 🎁 Вступить в чат и получить подарок
kb-main-renew = ⚡️ Продлить подписку
kb-main-renew-left = ⚡️ Продлить подписку (осталось { $days ->
    [one] { $days } день
    [few] { $days } дня
   *[other] { $days } дней
})
kb-main-wallet = 💰 Кошелек ({ $balance } USDT)
kb-main-profile = 👤 Личный кабинет
kb-main-settings = ⚙️ Настройки и фильтры
kb-main-support = 👨‍💻 Тех. поддержка
kb-main-chat = 📥 Чат сообщества

kb-status-refresh = 🔄 Обновить статус

gate-subscription-verified = ✅ Подписка подтверждена! Бесплатный поток сигналов возобновлен.
gate-subscription-not-found = ❌ Вы еще не подписались на наш канал и чат. Пожалуйста, вступите в оба ресурса и повторите проверку.
gate-unsubscribed-warning = ⚠️ Рассылка сигналов приостановлена. Для получения сигналов подпишитесь на наш канал и чат.
gate-verify-button = 🔄 Проверить подписку

# ===== Clean State Model (Главное меню 4-состояний / Gate Screen) =====
main-menu-status-vip-active = ✅ Активна до { $subscription_end }
main-menu-status-free-active = 🆓 Бесплатный тариф
main-menu-status-free-paused = ❌ Не активна.

⚠️ Рассылка сигналов приостановлена. Для получения сигналов нажмите кнопку разблокировки ниже.
main-menu-status-trial-available = ❌ Не активна.

🎁 Вам доступен бесплатный VIP-тест на 3 дня.
kb-main-unlock-signals = 🔓 Включить бесплатные сигналы
kb-main-upgrade-vip = 💎 Перейти на VIP (Убрать шум)
gate-unlock-screen = ⚠️ Активация бесплатного тарифа.

Чтобы бесплатно получать сигналы:
1. Подпишитесь на наш Новостной канал
2. Вступите в Чат сообщества

После вступления нажмите кнопку подтверждения ниже:
gate-button-verify-action = ✅ Проверить и включить сигналы
