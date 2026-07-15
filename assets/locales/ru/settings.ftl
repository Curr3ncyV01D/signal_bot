# Settings menu, prompts, and explanatory texts.

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
