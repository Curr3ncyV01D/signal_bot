# Wallet screens, balance flow, and payment status messages.

wallet-main-screen =
    👛 <b>Кошелек</b>

    💰 Текущий баланс: { $balance } USDT
    Стоимость подписки в месяц { $monthly_price } USDT

    🆔 Ваш ID: { $user_id }

    Если у вас возникли проблемы с оплатой, обратитесь в техническую поддержку. Мы обязательно вам поможем!
wallet-pending-verification-info = ⏳ Инвойс { $invoice_id } ожидает подтверждения администратором. Обычно это занимает от нескольких минут до 2-х часов.

kb-wallet-renew = 💎 Продлить подписку
kb-wallet-renew-pending-review = ⏳ Продлить подписку
kb-wallet-autorenew-on = 🔁 Автопродление: ВКЛ
kb-wallet-autorenew-off = 🔁 Автопродление: ВЫКЛ
kb-wallet-history = 📜 История транзакций
kb-wallet-back-main = ⬅️ Назад в меню

wallet-history-empty = <i> История операций пуста </i>
wallet-history-title = 📜 <b>История транзакций</b>

wallet-deposit-removed-toast = Ручное пополнение отключено. Выберите тариф
wallet-payment-gateway-error = ❌ Ошибка платежного шлюза. Попробуйте позже.
wallet-invalid-invoice-id = ❌ Некорректный идентификатор платежа.
wallet-invoice-not-found = ❌ Счет не найден в базе.

wallet-subscription-paid-success-screen =
    ✅ <b>Оплата подтверждена!</b>

    Подписка активирована до { $new_end }.
wallet-subscription-activated-toast = Подписка активирована

wallet-balance-paid-success-screen =
    ✅ <b>Оплата подтверждена!</b>

    Ваш баланс пополнен. Текущий баланс: { $balance }
wallet-success-toast = Успешно!

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
