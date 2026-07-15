# Admin manual payment review and billing moderation texts.

kb-admin-pay-approve = ✅ Одобрить { $amount }
kb-admin-pay-custom = ✏️ Другая сумма
kb-admin-pay-reject = ❌ Отклонить

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
