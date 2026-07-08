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
main-button-home = 🏠 Главное меню
main-button-private-channel = 🚀 Зайти в закрытый канал

onboarding-language-screen =
    🌐 <b>Добро пожаловать / Welcome!</b>

    Выберите язык интерфейса, чтобы завершить настройку.
    Choose your interface language to complete setup.
onboarding-language-selected = Язык сохранен

trial-unavailable-news-channel = Триал через канал недоступен: NEWS_CHANNEL_ID не задан.
trial-screen =
    🎁 <b>Пробный период на 24 часа</b>

    Мы предоставляем вам тестовый доступ на 24 часа.
    Также приглашаем вас в наш новостной канал, чтобы следить за обновлениями и важными анонсами.
trial-mode-disabled = Режим каналов отключен. Активация триала через канал недоступна.
profile-not-found-start = Профиль не найден. Нажмите /start.
trial-already-used = Пробный период уже был использован.
subscription-check-temporary-unavailable = Проверка подписки временно недоступна. Попробуйте чуть позже.
trial-activation-failed = Не удалось активировать пробный период. Попробуйте позже.
trial-activated-screen =
    ✅ <b>Пробный период на 24 часа активирован</b>
    
    💎 Мы рекомендуем вам открыть <b>меню настроек</b> и настроить фильтры сигналов по своему вкусу! 💎
trial-activated-toast = Доступ на 24 часа активирован

channel-mode-disabled = Режим каналов отключен: ссылка в канал недоступна.
channel-link-caption =
    👉 Ваша ссылка для входа в канал:
    { $invite_link }
channel-link-error = Ошибка получения ссылки. Бот не админ.

system-status-title = Система активна
status-refresh-success = ✅ Статус успешно обновлен!
status-refresh-no-changes = 🔄 Данные не изменились
status-refresh-error = Ошибка обновления

settings-title =
    <b>📊 Фильтры ликвидаций (Режим: { $threshold_mode }):</b>
    🔶 Порог объема: <b>${ $threshold }</b>
    🔸 Порог каскада: <b>${ $threshold_cascade }</b>
    🔷 Порог объема MCAP: <b>{ $threshold_mcap_pct }</b> (мин. <b>${ $threshold_mcap_usd_min }</b>)
    🔹 Порог каскада MCAP: <b>{ $threshold_cascade_mcap_pct }</b> (мин. <b>${ $threshold_cascade_mcap_usd_min }</b>)

    <b>📊 Фильтры аналитики (OI):</b>
    📈 Мин. рост OI: <b>{ $threshold_oi_percent }</b> и <b>${ $threshold_oi_value }</b>

    💡 <i>Подсказка: Отключайте неинтересующие индикаторы ниже, чтобы сделать уведомления компактнее.</i>

    <i>Нажмите на кнопки '❓ Справка', чтобы узнать подробности.</i>

settings-profile-error = ❌ Ошибка при получении профиля. Нажмите /start
settings-save-error = ❌ Ошибка при сохранении настроек.
settings-saved = Настройка сохранена
settings-mode-changed = Режим изменен на { $mode }
settings-error-profile = Ошибка профиля
settings-error-save = Ошибка сохранения

settings-enter-mcap-pct =
    Введите порог объема в % от капитализации (например, 0.005).
    Рекомендуемое значение: 0.005%
settings-enter-mcap-min-usd = Введите минимальный долларовый пол для режима % (например, 1000).
settings-enter-mcap-cascade-pct =
    Введите порог каскада в % от капитализации (например, 0.01).
    Рекомендуемое значение: 0.01%
settings-enter-mcap-cascade-min-usd = Введите минимальный долларовый пол для каскада (например, 5000).
settings-positive-number-required = ❌ Пожалуйста, введите положительное число.
settings-mcap-pct-updated = ✅ Порог объема установлен на { $value }
settings-mcap-min-usd-updated = ✅ Мин. порог объема установлен на ${ $value }
settings-mcap-cascade-pct-updated = ✅ Порог каскада установлен на { $value }
settings-mcap-cascade-min-usd-updated = ✅ Мин. порог каскада установлен на ${ $value }

help-liquidations =
    📊 <b>Справка: ЛИКВИДАЦИИ</b>

    Бот отслеживает принудительные закрытия позиций трейдеров (Margin Calls).

    ⚡️ <b>Каскады:</b> Эффект «домино», когда одна ликвидация цепляет стопы других за 1-2 минуты.
    <i>Как применять:</i> Поиск экстремумов. Остановка каскада часто означает локальное дно или пик рынка.

    📊 <b>Объем:</b> Накопленная сумма ликвидаций за 1 час.
    <i>Как применять:</i> Показывает, кого глобально «бреют» на рынке.

    🔥 <b>Сквиз:</b> Резкий всплеск, когда 5-минутный объем почти равен часовому.
    <i>Как применять:</i> Вход на локальных прострелах волатильности.

    <i>Остались вопросы по работе алгоритмов? Напишите нашему специалисту.</i>

help-analytics =
    📈 <b>Справка: АНАЛИТИКА</b>

    Бот анализирует метрики, чтобы дать контекст движению цены.

    🟢 <b>Открытый интерес (OI):</b> Объем всех открытых фьючерсных позиций.
    <i>Как применять:</i> Если Цена растет + OI растет = в лонги заходят новые деньги (сильный тренд). Если Цена падает + OI падает = просто закрытие старых лонгов.

    📊 <b>CVD (Дельта):</b> Разница между рыночными покупками и продажами.
    <i>Как применять:</i> «More Buys» означает агрессию покупателей в моменте. Идеально для поиска точки входа.

    ⚠️ <b>RSI (5m):</b> Индикатор перегретости актива.
    <i>Как применять:</i> RSI > 70 — актив перекуплен. В комбинации с ликвидацией шортов — сильнейший сигнал на разворот вниз.

    <i>Остались вопросы по работе алгоритмов? Напишите нашему специалисту.</i>

settings-enter-threshold = Введите новый порог объема в долларах (например: 5000):
settings-enter-cascade-threshold = Введите порог для КАСКАДОВ в долларах (например: 2000):
settings-invalid-amount = ❌ Пожалуйста, введите корректную сумму цифрами
settings-threshold-updated = ✅ Порог объема изменен на <b>${ $value }</b>!
settings-cascade-threshold-updated = ✅ Порог каскадов изменен на <b>${ $value }</b>!

settings-oi-thresholds-prompt =
    📊 <b>Настройка порогов Открытого Интереса (OI)</b>

    Введите 2 числа через пробел:
    1. <b>Процент изменения</b> (например, 5.0)
    2. <b>Объем в долларах</b> (например, 500000)

    <i>Пример:</i> <code>5 500000</code>
settings-oi-thresholds-updated =
    ✅ Пороги ОИ изменены!
    Процент: <b>{ $percent }</b>
    Объем: <b>${ $value }</b>

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

kb-common-back = ⬅️ Назад
kb-common-close = ❌ Закрыть

kb-main-trial = 🎁 Пробный период
kb-main-renew = ⚡️ Продлить подписку
kb-main-private-channel = 🚀 Зайти в закрытый канал
kb-main-renew-left = ⚡️ Продлить подписку (осталось { $days ->
    [one] { $days } день
    [few] { $days } дня
   *[other] { $days } дней
})
kb-main-wallet = 💰 Кошелек ({ $balance } USDT)
kb-main-settings = ⚙️ Настройки и фильтры
kb-main-support = 👨‍💻 Тех. поддержка

kb-status-refresh = 🔄 Обновить статус

kb-settings-mode = ⚙️ Режим: { $mode ->
    [PERCENT] % MCAP 💎
    *[USD] USD 💵
}
kb-settings-help-liq = -- ❓ Справка: ЛИКВИДАЦИИ --
kb-settings-help-analytics = -- ❓ Справка: АНАЛИТИКА --
kb-settings-threshold-volume-percent = 💰 Порог объема (%)
kb-settings-threshold-cascade-percent = ⚡ Порог каскада (%)
kb-settings-threshold-min-usd = Мин. порог ($)
kb-settings-threshold-cascade-min-usd = Мин. порог каскада ($)
kb-settings-threshold-volume-usd = 💰 Порог объема ($)
kb-settings-threshold-cascade-usd = ⚡ Порог каскада ($)
kb-settings-toggle-cascade = { $status } Каскад
kb-settings-toggle-volume = { $status } Объем
kb-settings-toggle-squeeze = { $status } Сквиз
kb-settings-toggle-longs = 🟢 LONG: { $status }
kb-settings-toggle-shorts = 🔴 SHORT: { $status }
kb-settings-toggle-oi = { $status } OI
kb-settings-toggle-rsi = { $status } RSI
kb-settings-toggle-cvd = { $status } CVD
kb-settings-oi-thresholds = ⚙️ Пороги ОИ (% и $)
kb-settings-back-main = ⬅️ Назад в меню
kb-settings-ask-question = 💬 Задать вопрос
kb-settings-back = ⬅️ Назад к настройкам

kb-wallet-renew = 💎 Продлить подписку
kb-wallet-deposit = 💰 Пополнить баланс
kb-wallet-autorenew-on = 🔁 Автопродление: ВКЛ
kb-wallet-autorenew-off = 🔁 Автопродление: ВЫКЛ
kb-wallet-language-ru = 🌐 Язык: Русский (Click to change language)
kb-wallet-language-en = 🌐 Язык: English (Click to change language)
kb-wallet-partner = 🤝 Партнерская программа
kb-wallet-history = 📜 История транзакций
kb-wallet-back-main = ⬅️ Назад в меню
kb-wallet-pay-cryptobot = 🔗 Оплатить (CryptoBot)
kb-wallet-check-payment = 🔄 Проверить оплату
kb-wallet-payment-issue = 👨‍💻 Проблема с оплатой?
kb-wallet-plan-months = { $months ->
    [one] { $months } месяц
    [few] { $months } месяца
   *[other] { $months } месяцев
}
kb-wallet-plan-days = { $days ->
    [one] { $days } день
    [few] { $days } дня
   *[other] { $days } дней
}
kb-wallet-plan-price = { $days ->
    [30] 1 месяц
    [60] 2 месяца
    [90] 3 месяца
    [150] 5 месяцев
    *[other] { $days ->
        [one] { $days } день
        [few] { $days } дня
       *[many] { $days } дней
    }
} — { $price } USDT
kb-wallet-confirm-debit = ✅ Подтвердить списание
kb-wallet-cancel = ❌ Отмена

kb-admin-analytics = 📊 Аналитика и метрики
kb-admin-broadcast = 📣 Создать рассылку
kb-admin-channel-settings = 📢 Настройки канала
kb-admin-users = 👥 Список пользователей
kb-admin-main-menu = 🔙 В главное меню
kb-admin-unblock = ✅ Разблокировать
kb-admin-block = 🛑 Заблокировать
kb-admin-edit-subscription = 📅 Изменить подписку
kb-admin-channel-posting-on = 🟢 Постинг ВКЛЮЧЕН
kb-admin-channel-posting-off = 🔴 Постинг ВЫКЛЮЧЕН
kb-admin-channel-oi-thresholds = ⚙️ Пороги OI (% и $)
kb-admin-channel-restart-dashboard = 🔄 Перезапустить Дэшборд
kb-admin-bi-finance = 💰 Финансы
kb-admin-bi-audience = 👥 Аудитория
kb-admin-bi-system = ⚙️ Система
kb-admin-bi-back-admin = ⬅️ Назад в админку
kb-admin-refresh = 🔄 Обновить
kb-admin-bi-export-csv = 📄 Выгрузить .csv
kb-admin-bi-find-coin = 🔍 Найти монету
kb-admin-bi-export-txt = 📄 Список (TXT)
kb-admin-broadcast-all = 👥 Всем
kb-admin-broadcast-vip = 💎 Только с подпиской
kb-admin-broadcast-free = 🆓 Только без подписки
kb-admin-broadcast-start = 🚀 Запустить рассылку
kb-admin-broadcast-change-cancel = 🔄 Изменить / Отмена

shop-subscription-menu =
    💎 <b>VIP-Подписка</b>

    Преимущества VIP-доступа:
    • Персональный поток сигналов в боте
    • Персональные настройки в боте
    • Аналитика в реальном времени

    Выберите подходящий тариф:
shop-referral-bonus-notification =
    🤝 <b>Партнерский бонус начислен!</b>

    Ваш реферал совершил покупку, и вам начислено { $bonus_amount }.
shop-invite-link =

    👉 <b>Ваша ссылка для входа:</b>
    { $invite_link }
shop-invite-link-error =

    <i>(Ошибка: Бот не смог создать ссылку. Обратитесь к админу.)</i>
shop-invalid-plan-params = ❌ Некорректные параметры тарифа.
shop-plan-not-found = Ошибка: Тариф не найден.
shop-balance-purchase-confirm =
    💎 <b>Продление подписки из баланса</b>

    У вас достаточно средств на балансе: { $balance }.

    Хотите продлить подписку на { $plan_label } за { $price }?
shop-direct-pay-screen =
    💎 <b>Оплата подписки: { $plan_label }</b>

    💰 Стоимость: { $price }
    💳 На балансе сейчас: { $balance }

    На балансе недостаточно средств, поэтому мы подготовили ссылку на оплату в CryptoBot.
shop-insufficient-balance = ❌ Недостаточно средств на балансе.
shop-purchase-success =
    🎉 <b>Подписка успешно оформлена!</b>

    📅 Срок действия до: { $new_end }
    💰 Списано с баланса: { $price }
shop-subscription-extended = Подписка продлена
shop-purchase-cancelled = Покупка отменена

wallet-main-screen =
    👛 <b>Кошелек</b>

    💰 Текущий баланс: { $balance } USDT
    Стоимость подписки в месяц { $monthly_price } USDT

    🆔 Ваш ID: { $user_id }

    Если у вас возникли проблемы с оплатой, обратитесь в техническую поддержку
wallet-language-changed = Язык изменен
wallet-autorenew-enabled = включено
wallet-autorenew-disabled = выключено
wallet-autorenew-status = Автопродление { $status }
wallet-history-empty = <i> История операций пуста </i>
wallet-history-title = 📜 <b>История транзакций</b>
wallet-partner-screen =
    🤝 <b>Партнерская программа</b>

    Приглашайте друзей и получайте { $bonus_percent }% от их покупок пожизненно на ваш баланс!

    🔗 <b>Ваша ссылка:</b>
    { $referral_link }

    👥 Приглашено: { $invited_count }
    💸 Заработано: { $total_rewards }
wallet-deposit-screen =
    ➕ <b>Пополнение баланса</b>

    Выберите сумму пополнения в USDT.
    Оплата принимается через { $cryptobot }.
wallet-cryptopay-timeout = ❌ Таймаут CryptoPay API. Попробуйте позже.
wallet-cryptopay-error = ❌ Ошибка CryptoPay API. Попробуйте позже.
wallet-invoice-screen =
    🧾 <b>Счет на оплату #{ $invoice_id }</b>

    Сумма: { $amount }
    Статус: { $pending_status }

    Нажмите кнопку ниже для перехода в CryptoBot:
wallet-payment-pending-status = Ожидание оплаты
wallet-invalid-invoice-id = ❌ Некорректный ID счета.
wallet-invoice-not-found = ❌ Счет не найден в базе.
wallet-invalid-subscription-payload = ❌ Некорректный payload подписки.
wallet-subscription-activation-failed = ❌ Не удалось активировать подписку после оплаты. Обратитесь в поддержку.
wallet-subscription-paid-success-screen =
    ✅ <b>Оплата подтверждена!</b>

    Подписка активирована до { $new_end }.
wallet-subscription-activated-toast = Подписка активирована
wallet-balance-paid-success-screen =
    ✅ <b>Оплата подтверждена!</b>

    Ваш баланс пополнен. Текущий баланс: { $balance }
wallet-success-toast = Успешно!
wallet-crediting-error = Ошибка при зачислении. Обратитесь в поддержку.
wallet-invoice-expired-screen = ❌ Срок действия счета истек.
wallet-expired-toast = Истек
wallet-payment-not-found-yet = ⏳ Оплата еще не обнаружена.

admin-user-blocked-notification =
    ❌ <b>Ваш аккаунт был заблокирован администрацией.</b>
    Доступ к функциям бота ограничен.
admin-user-subscription-updated-notification =
    📅 <b>Ваша подписка обновлена администратором!</b>

    Новый срок действия: { $subscription_end }
admin-user-subscription-cancelled-notification = ❌ <b>Ваша подписка была аннулирована администратором.</b>

join-request-declined-notification =
    ❌ <b>Ваша заявка на вступление отклонена.</b>

    У вас нет активной подписки или пробного периода. Пожалуйста, перейдите в бота и нажмите /start для приобретения подписки.
