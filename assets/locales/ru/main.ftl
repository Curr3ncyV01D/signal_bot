# Main menu, onboarding, and entry flow.

main-menu-status-active = ✅ Активна до { $subscription_end }
main-menu-status-inactive = ❌ Не активна

main-menu =
    👋 Добро пожаловать, <b>{ $full_name }</b>!

    Я профессиональный терминал для мониторинга ликвидаций на Bybit.
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

community-bonus-screen =
    🎁 <b>Ваш приветственный бонус: + { $hours } часов VIP-доступа!</b>

    Мы строим не просто инструмент, а закрытое сообщество трейдеров. Присоединяйтесь к нашему чату, чтобы:

    🔹 Обсуждать сигналы Bybit в реальном времени.
    🔹 Делиться рабочими стратегиями и настройками.
    🔹 Получать помощь от опытных участников «Улья».

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

kb-status-refresh = 🔄 Обновить статус
