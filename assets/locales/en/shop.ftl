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
} — { $price } USDT { $extra }
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

# ---- CactusPay H2H (Payment via RU Cards / SBP) ----
kb-shop-method-cactus-card = 💳 Pay with RU Card (CactusPay)
kb-shop-method-cactus-sbp = ⚡ Pay via SBP (CactusPay)
kb-shop-method-crypto-manual = ₿ Pay with Crypto (USDT TRC20)
kb-shop-cactus-check-payment = ✅ I have paid. Check status
kb-shop-cactus-go-hosted = 🔗 Go to payment page

shop-no-payment-methods = ❌ No payment methods are currently configured. Please contact Support.
shop-cactus-unavailable = ❌ Card payment is temporarily unavailable. Please use another method or contact Support.
shop-cactus-requisite-error = ❌ Failed to fetch payment details. Please try again later or choose a different payment method.
shop-cactus-expired = ❌ The payment details have expired. Please create a new payment.
shop-cactus-wait-processing = ⏳ The transaction is being processed by the payment system. Please wait 1-2 minutes and check the status again.
shop-cactus-method-hosted = 🔗 Pay with CactusPay (RU Card / SBP / QR)
shop-cactus-description = CSL Subscription — { $days } days

shop-cactus-pay-hosted-screen =
    💎 <b>Payment for { $plan_label }</b>

    📌 To activate your subscription, go to the secure payment page via the button below.
    On the payment page you can choose any of these methods:
      • 💳 RU Card (Visa / MasterCard / MIR)
      • ⚡ SBP (Fast Payment System)
      • 📱 QR code

    🧾 Amount to pay: { $amount_rub }
    🪙 Tariff equivalent: { $amount_usd }
    💳 Your balance: { $balance }

    ⏳ This invoice is valid for { $lifetime_minutes } minutes.
    ⏱️ Time left: <b>{ $countdown }</b>

    ✅ After successful payment, come back here and tap «I have paid» for instant activation.

shop-payment-method-selection =
    💎 <b>Select a payment method: { $plan_label }</b>

    🧾 Full plan price: { $price_usd }
    💳 Your balance: { $balance }

    💰 Amount due: { $amount_to_pay_usd }
    🏷️ RUB equivalent: { $price_rub }

    <i>We recommend paying via RU Card or SBP — instant crediting, no screenshots required.</i>

shop-cactus-pay-screen-card =
    💎 <b>Payment via RU Card: { $plan_label }</b>

    📄 Invoice: { $invoice_id }

    🧾 Plan price: { $price_usd }
    💳 Your balance: { $balance }

    💰 To be credited on balance: { $amount_to_pay_usd }
    🏷️ <b>Transfer exactly</b>: { $amount_to_pay_rub }

    💳 <b>Recipient card number</b> (tap to copy):
    { $card_number }

    👤 <b>Recipient</b>: { $receiver_name }
    🏦 <b>Bank</b>: { $receiver_bank }

    ⏳ <b>Requisites valid for</b>: { $countdown } (min:sec)

    <b>🔐 Important:</b>
    • Transfer the exact RUB amount specified above (kopeck-to-kopeck).
    • After the transfer, tap «I have paid» — the status will update within 30 seconds.
    • If SBP is faster for you, go back and select the «SBP» payment method.

shop-cactus-pay-screen-sbp =
    💎 <b>Payment via SBP: { $plan_label }</b>

    📄 Invoice: { $invoice_id }

    🧾 Plan price: { $price_usd }
    💳 Your balance: { $balance }

    💰 To be credited on balance: { $amount_to_pay_usd }
    🏷️ <b>Transfer exactly via SBP</b>: { $amount_to_pay_rub }

    📱 <b>SBP phone number</b> (tap to copy):
    { $receiver_phone }

    🏦 <b>SBP Bank</b>: { $receiver_bank }

    ⏳ <b>Requisites valid for</b>: { $countdown } (min:sec)

    <b>🔐 Important:</b>
    • Transfer the exact RUB amount specified above through SBP in your banking app.
    • After the transfer, tap «I have paid» — the status will update within 30 seconds.

shop-balance-credited-but-auto-activation-skipped =
    ✅ <b>Funds credited successfully!</b>

    Your balance: { $balance }
    Unfortunately, the plan price has changed since the invoice was created, so auto-activation was skipped.

    Remaining amount needed to purchase the plan: { $needed }
    Tap «Renew subscription» in your Wallet to activate the subscription at the new price.
