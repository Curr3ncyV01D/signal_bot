# Tariffs, purchase flow, and manual billing.

kb-wallet-plan-months = { $months ->
    [one] { $months } month
   *[other] { $months } months
}
kb-wallet-plan-days = { $days ->
    [one] { $days } day
   *[other] { $days } days
}
kb-wallet-plan-price = { $days ->
    [30] 🔥 1 month
    [60] 2 months
    [90] 3 months
    [150] 5 months
   *[other] { $days } days
} — { $price } USDT
kb-wallet-confirm-debit = ✅ Confirm Debit
kb-wallet-send-screenshot = 📸 Send Screenshot
kb-wallet-send-topup-screenshot = 📸 Send Additional Payment Screenshot

shop-subscription-menu =
    💎 <b>Premium Subscription Purchase</b>

    <b>What you get:</b>
    • <b>Full Exchange Coverage:</b>
    Monitor all USDT pairs without exceptions.

    • <b>Live Charts:</b>
    Instant 15m OHLC rendering directly inside the alert 📊

    • <b>Smart Analytics:</b>
    Cap/Vol Ratio metrics help you separate noise from real market moves.

    • <b>Advanced Metrics:</b>
    Track CVD, RSI, and Open Interest (OI) 📈

    • <b>Custom Filters:</b>
    Fine-tune thresholds to match your strategy.

    • <b>Instant Signals:</b>
    Low-latency signal delivery through dedicated nodes ⚡️

    <i>Select the plan that gives you an edge right now:</i>

shop-invalid-plan-params = ❌ Invalid plan parameters.
shop-plan-not-found = Error: plan not found.
shop-balance-purchase-confirm =
    💎 <b>Balance-Funded Subscription Renewal</b>

    You have enough funds on your balance: { $balance }.

    Do you want to renew your subscription for { $plan_label } at { $price }?
shop-manual-pay-screen =
    💎 <b>Premium subscription payment for plan: { $plan_label }</b>

    <b>📄 Invoice number:</b>
    { $invoice_id }

    🧾 Plan price: { $price }
    💳 Current balance: { $balance }

    💰 Amount due: { $amount_to_pay }

    <b>🌐 Network:</b> { $network }
    <b>👛 Payment wallet:</b>

    { $wallet }
    <i>(tap the address to copy it)</i>

    🕒 Payment confirmation is handled manually by administrators and usually takes from a few minutes up to 2 hours.

    🔐<b>Important:</b> To identify your payment, you must send a receipt screenshot after the transfer. Use the button below to submit it.

    <i>If you want to pay by bank card, contact Technical Support and we will help you arrange it.</i>
shop-manual-payment-unavailable = ❌ Manual payment is currently unavailable. Please use another payment method.
shop-manual-payment-screenshot-prompt = Send the payment screenshot in your next message
shop-manual-payment-photo-only = ❌ Please send a photo or image file with the payment screenshot.
shop-manual-payment-already-submitted = ⏳ The screenshot has already been submitted. The request is waiting for administrator review.
shop-manual-payment-already-approved = ✅ This payment has already been confirmed. No need to send the screenshot again.
shop-manual-payment-expired = ❌ The waiting window for this payment has expired. Please create a new payment.
shop-manual-payment-upload-unavailable = ❌ You cannot resubmit a screenshot for this payment right now.
shop-manual-payment-request-accepted =
    ✅ <b>The screenshot has been received and forwarded to the administrators.</b>

    The invoice payment has been sent for review. This usually takes from a few minutes up to 2 hours.

    As soon as an administrator reviews the payment, we will immediately send you the result.
shop-insufficient-balance = ❌ Insufficient balance.
shop-purchase-success =
    🎉 <b>Subscription purchased successfully!</b>

    📅 Active until: { $new_end }
    💰 Deducted from balance: { $price }
shop-subscription-extended = Subscription extended
shop-purchase-cancelled = Purchase cancelled
