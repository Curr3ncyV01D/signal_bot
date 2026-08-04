# Settings menu, prompts, and explanatory texts.

settings-title =
    <b>📊 Фильтры ликвидаций (Режим: { $threshold_mode }):</b>
    - Порог объема: ${ $threshold }
    - Порог каскада: ${ $threshold_cascade }

    - Порог объема MCAP: { $threshold_mcap_pct } (мин. ${ $threshold_mcap_usd_min })
    - Порог каскада MCAP: { $threshold_cascade_mcap_pct } (мин. ${ $threshold_cascade_mcap_usd_min })

    📈 Фильтры аналитики:
    Мин. рост OI: { $threshold_oi_percent } и ${ $threshold_oi_value }
    RSI-фильтр: { $rsi_min } / { $rsi_max }

settings-filters-screen =
    <b>📊 Фильтры ликвидаций (Режим: { $threshold_mode }):</b>
    - Порог объема: ${ $threshold }
    - Порог каскада: ${ $threshold_cascade }

    - Порог объема MCAP: { $threshold_mcap_pct } 
    (минимум ${ $threshold_mcap_usd_min })
    - Порог каскада MCAP: { $threshold_cascade_mcap_pct } 
    (минимум ${ $threshold_cascade_mcap_usd_min })

    📈 Фильтры аналитики:
    Мин. рост OI: { $threshold_oi_percent } и ${ $threshold_oi_value }
    RSI-фильтр: { $rsi_min } / { $rsi_max }

    Эти настройки влияют на то, какие события запускают отправку сигнала.
    Ниже можно менять режим, пороги и состав триггеров.

    <i>Нажмите на кнопку '❓ Справка', чтобы узнать подробности.</i>

settings-display-screen =
    <b>👁 Вид сообщений</b>

    Эти настройки меняют только визуальный состав алертов.
    Они включают или скрывают дополнительные блоки данных внутри текста сообщения.

    <i>💡 Подсказка: Отключайте неинтересующие индикаторы ниже, чтобы сделать уведомления компактнее.</i>
    
    <i>Нажмите на кнопку '❓ Справка', чтобы узнать подробности.</i>
    
settings-display-state-on = Вкл
settings-display-state-off = Выкл

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

    🚦 <b>RSI-фильтр (фильтр по экстремумам):</b> Дополнительные ворота, через которые проходит сигнал. Установите границы 100/0 — фильтр выключен. 30/70 — стандарт. 20/80 — жесткий фильтр.
    <i>Как применять:</i> Сигнал пройдёт, только если текущий RSI ≤ нижней границы (перепроданность) ИЛИ ≥ верхней границы (перекупленность). Если данных RSI ещё нет — сигнал блокируется.

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
settings-rsi-thresholds-prompt =
    ⚠️ <b>Настройка RSI-фильтра</b>

    Введите 2 числа через пробел:
    1. <b>Нижняя граница (перепроданность)</b> — например, 30
    2. <b>Верхняя граница (перекупленность)</b> — например, 70

    Или выберите пресет ниже. Для выключения фильтра установите 100/0.
    Значения должны быть в диапазоне 0–100.

    <i>Пример:</i> <code>30 70</code>
settings-rsi-thresholds-updated =
    ✅ RSI-фильтр установлен: { $rsi_min } / { $rsi_max }
settings-rsi-thresholds-disabled =
    ✅ RSI-фильтр <b>выключен</b> (100/0). Сигналы проходят без RSI-фильтрации.
settings-rsi-gate-explain-disabled = Фильтр <b>выключен</b> — все сигналы проходят.
settings-rsi-gate-explain-conservative = <i>Сильный фильтр</i> — только явные экстремумы.
settings-rsi-gate-explain-balanced = <i>Стандартные зоны</i> — классика 30/70.
settings-rsi-gate-explain-scalper = <i>Узкая полоса</i> — сигнал на любом пике волатильности.
settings-rsi-gate-explain-custom = <i>Пользовательский режим</i>.
settings-rsi-thresholds-invalid = ❌ Введите 2 числа от 0 до 100 через пробел (пример: <code>30 70</code>).
settings-oi-thresholds-updated =
    ✅ Пороги ОИ изменены!
    Процент: <b>{ $percent }</b>
    Объем: <b>${ $value }</b>

settings-preset-catalog-screen =
    🎯 <b>Профили стратегии</b>

    Пресет заменяет текущие фильтры целиком: USD-пороги, MCAP-пороги, OI, RSI-фильтр и все тумблеры сигналов.

    <b>⚡ Скальпинг</b>
    Для активной торговли и частых алертов по альтам.

    Режим по умолчанию: <b>{ $scalper_mode }</b>
    Частота: <b>высокая</b>
    
    • Объем: <b>${ $scalper_threshold }</b> | Каскад: <b>${ $scalper_cascade }</b>
    • OI: <b>{ $scalper_oi_percent }</b> / <b>${ $scalper_oi_value }</b>
    • RSI-фильтр: <b>{ $scalper_rsi_min } / { $scalper_rsi_max }</b>

    <b>⚖️ Сбалансированный</b>
    Для ежедневной торговли с умеренным количеством сигналов.

    Режим по умолчанию: <b>{ $balanced_mode }</b>
    Частота: <b>средняя</b>

    • Объем: <b>${ $balanced_threshold }</b> | Каскад: <b>${ $balanced_cascade }</b>
    • OI: <b>{ $balanced_oi_percent }</b> / <b>${ $balanced_oi_value }</b>
    • RSI-фильтр: <b>{ $balanced_rsi_min } / { $balanced_rsi_max }</b>

    <b>🐋 Консервативный</b>
    Для фокуса на крупных движениях и редких, но сильных событиях.

    Режим по умолчанию: <b>{ $conservative_mode }</b>
    Частота: <b>низкая</b>

    • Объем: <b>${ $conservative_threshold }</b> | Каскад: <b>${ $conservative_cascade }</b>
    • OI: <b>{ $conservative_oi_percent }</b> / <b>${ $conservative_oi_value }</b>
    • RSI-фильтр: <b>{ $conservative_rsi_min } / { $conservative_rsi_max }</b>

settings-preset-confirm-screen =
    ⚠️ <b>Это заменит ваши текущие фильтры. Вы уверены?</b>

    <b>{ $preset_name }</b>
    { $preset_description }

    Режим по умолчанию: <b>{ $recommended_mode }</b>

    <b>USD:</b> объем <b>${ $threshold }</b>, каскад <b>${ $threshold_cascade }</b>
    <b>% MCAP:</b> объем <b>{ $threshold_mcap_pct }</b> (мин. <b>${ $threshold_mcap_usd_min }</b>)
    <b>% MCAP Каскад:</b> <b>{ $threshold_cascade_mcap_pct }</b> (мин. <b>${ $threshold_cascade_mcap_usd_min }</b>)
    <b>OI:</b> <b>{ $threshold_oi_percent }</b> и <b>${ $threshold_oi_value }</b>
    <b>RSI-фильтр:</b> <b>{ $rsi_min } / { $rsi_max }</b>

    После применения вы сможете вручную подстроить любой параметр.
settings-preset-name-scalper = ⚡ Скальпинг
settings-preset-name-balanced = ⚖️ Сбалансированный
settings-preset-name-conservative = 🐋 Консервативный
settings-preset-description-scalper = Ищет аномалии и быстрые импульсы на альтах. Подходит тем, кому нужен плотный поток сигналов.
settings-preset-description-balanced = Универсальный профиль для большинства пользователей. Снижает шум, но оставляет хорошую чувствительность.
settings-preset-description-conservative = Фильтрует рынок жестче остальных. Подходит тем, кто хочет видеть только наиболее значимые движения.
settings-preset-applied-toast = Пресет { $preset_name } применен

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
kb-settings-rsi-thresholds = ⚙️ Границы RSI: { $rsi_min } / { $rsi_max }
kb-settings-rsi-preset-conservative = [ 20 / 80 ]
kb-settings-rsi-preset-balanced = [ 30 / 70 ]
kb-settings-rsi-preset-scalper = [ 35 / 65 ]
kb-settings-rsi-disable = 🔓 Выключить [ 100 / 0 ]
kb-settings-rsi-manual = ✏️ Ввести вручную
kb-settings-rsi-back = ⬅️ Назад к фильтрам
kb-settings-preset-profiles = 🎯 Выбрать готовые стратегии
kb-settings-preset-scalper = ⚡ Скальпинг
kb-settings-preset-balanced = ⚖️ Сбалансированный
kb-settings-preset-conservative = 🐋 Консервативный
kb-settings-preset-confirm-apply = ✅ Применить профиль
kb-settings-preset-confirm-cancel = ⬅️ Назад к профилям
kb-settings-open-filters = 📊 Настроить фильтры триггеров
kb-settings-open-display = 👁 Настроить вид сообщений
kb-settings-back-root = ⬅️ Назад к общим настройкам
kb-settings-back-main = ⬅️ Назад в меню
kb-settings-ask-question = 💬 Задать вопрос
kb-settings-back = ⬅️ Назад к настройкам
