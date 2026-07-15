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
kb-main-profile = 👤 Личный кабинет
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
kb-wallet-renew-pending-review = ⏳ Продлить подписку
kb-wallet-deposit = 💰 Пополнить баланс
kb-wallet-autorenew-on = 🔁 Автопродление: ВКЛ
kb-wallet-autorenew-off = 🔁 Автопродление: ВЫКЛ
kb-wallet-language-ru = 🌐 Язык: Русский (Click to change language)
kb-wallet-partner = 🤝 Партнерская программа
kb-wallet-history = 📜 История транзакций
kb-wallet-back-main = ⬅️ Назад в меню
kb-wallet-check-payment = 🔄 Проверить оплату
kb-wallet-payment-issue = 👨‍💻 Проблема с оплатой?
kb-wallet-card-guide = 💳 Как оплатить картой
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
    [30] 🔥 1 месяц
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
kb-admin-send-message = ✉️ Написать сообщение
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
kb-admin-pay-approve = ✅ Одобрить { $amount }
kb-admin-pay-custom = ✏️ Другая сумма
kb-admin-pay-reject = ❌ Отклонить
kb-wallet-pay-manual = 👛 Перевод на кошелек
kb-wallet-send-screenshot = 📸 Отправить скриншот
kb-wallet-send-topup-screenshot = 📸 Отправить скриншот доплаты

shop-subscription-menu =
    💎 <b>Приобритение премиум подписки</b>

    <b>Что вы получаете:</b>
    • <b>Отслеживание всей биржи:</b> 
    Мониторинг всех USDT-пар без исключений.

    • <b>Live-Графики:</b> 
    Мгновенный рендеринг 15m OHLC прямо в алерте 📊

    • <b>Умная аналитика:</b> 
    Метрики Cap/Vol Ratio — отличайте шум от реальных движений.

    • <b>Продвинутые метрики:</b> 
    Отслеживание CVD, RSI и Открытого интереса (OI) 📈

    • <b>Пользовательские фильтры:</b> 
    Гибкая настройка порогов под вашу стратегию.

    • <b>Моментальные сигналы:</b> 
    Секундная доставка сигналов через выделенные узлы ⚡️

    <i>Выберите подходящий тариф, чтобы получить преимущество прямо сейчас:</i>
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
shop-manual-pay-screen =
     <b>Оплата тарифа премиальной подписки: { $plan_label }</b>

    <b>📄 Номер инвойса:</b>
    { $invoice_id }

    🧾 Стоимость тарифа: { $price }
    💳 На балансе сейчас: { $balance }

    💰 Сумма к оплате: { $amount_to_pay }

    <b>🌐 Сеть:</b> { $network }
    <b>👛 Кошелек для оплаты:</b>

    { $wallet }
    <i>(нажмите на адрес, чтобы скопировать его)</i>

    🕒 Подтверждение платежа происходит администраторами и обычно занимает от нескольких минут до 2-х часов.

    🔐<b>Важно:</b> Для идентификации вашего платежа обязательно пришлите скриншот чека после перевода, чтобы его отправить нажмите кнопку снизу.
    
    <i>Если вы хотите провести оплату по карте, то обратитесь в тех. поддержку и мы вам поможем</i>
shop-manual-payment-unavailable = ❌ Ручная оплата сейчас недоступна. Попробуйте другой способ.
shop-manual-payment-screenshot-prompt = Отправьте скриншот оплаты в следующем сообщении
shop-manual-payment-photo-only = ❌ Пожалуйста, отправьте фото или файл-изображение со скриншотом оплаты.
shop-manual-payment-already-submitted = ⏳ Скриншот уже отправлен. Заявка ожидает проверки администратора.
shop-manual-payment-already-approved = ✅ Этот платеж уже подтвержден. Повторная отправка скриншота не требуется.
shop-manual-payment-expired = ❌ Время ожидания по этому платежу истекло. Пожалуйста, создайте новый платеж.
shop-manual-payment-upload-unavailable = ❌ Для этого платежа сейчас нельзя отправить скриншот повторно.
shop-manual-payment-request-accepted =
    ✅ <b>Скриншот получен и отправлен администраторам.</b>

    Оплата инвойса отправлена администраторам на проверку. Обычно это занимает от нескольких минут до 2-х часов.
    
    Как только администратор проверит оплату, мы сразу вам отправим уведомление о результатах!
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

    Если у вас возникли проблемы с оплатой, обратитесь в техническую поддержку. Мы обязательно вам поможем!
wallet-pending-verification-info = ⏳ Инвойс { $invoice_id } ожидает подтверждения администратором. Обычно это занимает от нескольких минут до 2-х часов.
wallet-language-changed = Язык изменен
profile-main-screen =
    👤 <b>Личный кабинет</b>

    🆔 Ваш ID: { $user_id }
    🌐 Язык: { $language }

    Баланс: { $balance }
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

    Ручное пополнение отключено. Оплата создается автоматически внутри покупки конкретного тарифа.
wallet-deposit-removed-toast = Ручное пополнение отключено. Выберите тариф
wallet-payment-gateway-timeout = ❌ Платежный шлюз не ответил вовремя. Попробуйте позже.
wallet-payment-gateway-error = ❌ Ошибка платежного шлюза. Попробуйте позже.
wallet-invoice-screen =
    🧾 <b>Счет на оплату #{ $invoice_id }</b>

    Сумма: { $amount }
    Статус: { $pending_status }

    Нажмите кнопку ниже для перехода в CryptoBot:
wallet-payment-pending-status = Ожидание оплаты
wallet-invalid-invoice-id = ❌ Некорректный идентификатор платежа.
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
wallet-payment-partial-screen =
    ⚠️ <b>Обнаружена частичная оплата.</b>

    Получено: { $paid_amount }
    Ожидалось: { $expected_amount }
    Не хватает: { $needed_amount }
wallet-payment-partial-toast = Обнаружена частичная оплата
wallet-payment-not-found-yet = ⏳ Оплата еще не обнаружена.
wallet-payment-processing = ⏳ Платеж уже обрабатывается. Подождите пару секунд.
wallet-payment-price-changed-screen =
    ✅ <b>Оплата подтверждена!</b>

    Средства зачислены на баланс: { $balance }
    Авто-активация не выполнена, потому что текущая цена изменилась.
    Для покупки тарифа не хватает: { $needed }
wallet-payment-price-changed-toast = Средства зачислены, авто-активация требует доплаты
payment-worker-reminder-active-link =
    ⏳ <b>Ваша ссылка на оплату всё еще активна.</b>

    Если возникли трудности с оплатой, обратитесь в тех поддержку. Мы обязательно вам поможем!
payment-worker-subscription-paid-notification =
    ✅ <b>Оплата подтверждена!</b>

    Баланс пополнен на <b>{ $amount }</b>.
    Тариф на <b>{ $days }</b> дн. активирован автоматически до <b>{ $new_end }</b>.
payment-worker-balance-paid-notification =
    ✅ <b>Оплата получена!</b>

    Ваш баланс пополнен на <b>{ $amount }</b>.
payment-worker-partial-payment-notification =
    ⚠️ <b>Обнаружена частичная оплата.</b>

    Получено: <b>{ $paid_amount }</b>
    Ожидалось: <b>{ $expected_amount }</b>
    
    Для активации тарифа доплатите еще <b>{ $needed_amount }</b> на тот же адрес.

    <b>🌐 Сеть:</b> { $network }
    <b>👛 Кошелек для оплаты:</b>

    { $wallet }
    <i>(нажмите на адрес, чтобы скопировать его)</i>
payment-worker-price-changed-notification =
    ✅ <b>Оплата подтверждена!</b>

    Средства зачислены на баланс: <b>{ $balance }</b>
    Авто-активация не выполнена: цена тарифа изменилась.
    Для покупки сейчас не хватает <b>{ $needed }</b>.
manual-payment-approved-notification =
    ✅ <b>Администратор подтвердил ваш платеж.</b>

    На баланс зачислено: <b>{ $amount }</b>
    Текущий баланс: <b>{ $balance }</b>
manual-payment-rejected-notification =
    ❌ <b>Факт оплаты инвойса отклонен администратором.</b>

    Причина: { $reason }
    <i>Если вы считаете, что это ошибка обратитесь в тех. поддержку</i>
manual-payment-rejected-reason-default = Пожалуйста, отправьте более четкий скриншот чека.
admin-pay-review-card-title-new = 📥 <b>Новая заявка на оплату инвойса</b>
admin-pay-review-card-title-topup = 🔄 <b>Заявка на ДОПЛАТУ</b>
admin-pay-review-card-already-paid = Уже подтверждено: { $amount }
admin-pay-review-card-needed = Осталось доплатить: { $amount }
admin-pay-user-profile-link = 👤 Профиль пользователя
admin-pay-wrong-chat = Эта кнопка работает только в закрытой группе проверки платежей.
admin-pay-invoice-not-found = Заявка не найдена или уже недоступна.
admin-pay-already-processed = Заявка уже была обработана ранее.
admin-pay-custom-amount-prompt =
    Введите подтвержденную сумму для инвойса { $invoice_id }.

    Ожидаемая сумма: { $expected_amount }
admin-pay-enter-rejection-reason = Введите причину отклонения для пользователя.
admin-pay-custom-amount-invalid = Некорректная сумма. Введите число, например `25` или `25.5`.
admin-pay-approve-done = Платеж подтвержден
admin-pay-reject-done = Платеж отклонен
admin-pay-review-processing = ⏳ Обработка: { $admin }
admin-pay-review-processed-by = 👤 Обработано админом: { $admin }
admin-pay-review-result-title = ✅ <b>Проверка завершена</b>
admin-pay-review-result-subscription = Подписка активирована до { $new_end }.
admin-pay-review-result-error = Код результата: { $error }
admin-pay-review-rejected =
    ❌ <b>Заявка отклонена</b>

    Invoice: { $invoice_id }
    Причина: { $reason }

admin-user-blocked-notification =
    ❌ <b>Ваш аккаунт был заблокирован администрацией.</b>
    Доступ к функциям бота ограничен.
admin-user-subscription-updated-notification =
    📅 <b>Ваша подписка обновлена администратором!</b>

    Новый срок действия: { $subscription_end }
admin-user-subscription-cancelled-notification = ❌ <b>Ваша подписка была аннулирована администратором.</b>
admin-personal-message-prompt =
    Введите сообщение для пользователя.

    Поддерживаются любые форматы: текст, фото, голосовые сообщения.
admin-personal-message-success = ✅ Сообщение успешно отправлено пользователю { $user_id }.
admin-personal-message-user-blocked = ❌ Ошибка: пользователь заблокировал бота.
admin-personal-message-copy-failed = ❌ Ошибка: не удалось отправить сообщение пользователю.
admin-personal-message-cancelled = Действие отменено.
admin-personal-message-user-not-found = ❌ Пользователь не найден в базе.

join-request-declined-notification =
    ❌ <b>Ваша заявка на вступление отклонена.</b>

    У вас нет активной подписки или пробного периода. Пожалуйста, перейдите в бота и нажмите /start для приобретения подписки.

bouncer-trial-expiry-warning =
    ⏳ <b>Ваш пробный доступ истекает через 1 час.</b>

    Чтобы не потерять доступ к сигналам, продлите подписку заранее в меню /start.

bouncer-subscription-expiry-warning =
    ⏳ <b>Ваша подписка истекает через 24 часа.</b>

    Убедитесь, что на балансе достаточно средств для автопродления, или продлите её вручную в меню /start.

bouncer-auto-renewal-success =
    ✅ <b>Подписка продлена!</b>

    Мы успешно списали <b>{ $amount } USDT</b> с вашего баланса. Спасибо, что остаетесь с нами.

bouncer-auto-renewal-failed-balance =
    ⚠️ <b>Недостаточно средств!</b>

    Мы не смогли продлить подписку автоматически. Пополните баланс, чтобы не потерять доступ к персональным сигналам через 1 час.

bouncer-subscription-expired =
    ⚠️ <b>Срок действия вашей подписки/триала истек.</b>

    Персональная рассылка сигналов приостановлена.
    Нажмите /start и продлите подписку, чтобы восстановить доступ.
