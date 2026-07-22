# Wallet screens, balance flow, and payment status messages.

wallet-main-screen =
    👛 <b>Wallet</b>

    💰 Account Balance: { $balance } USDT
    Monthly subscription price: { $monthly_price } USDT

    🆔 Your ID: { $user_id }

    If you run into payment issues, contact Technical Support. We will help you resolve them.
wallet-pending-verification-info = ⏳ Invoice { $invoice_id } is awaiting administrator confirmation. This usually takes anywhere from a few minutes up to 2 hours.

kb-wallet-renew = 💎 Extend Subscription
kb-wallet-renew-pending-review = ⏳ Extend Subscription
kb-wallet-autorenew-on = 🔁 Auto-Renewal: ON
kb-wallet-autorenew-off = 🔁 Auto-Renewal: OFF
kb-wallet-history = 📜 Transaction History
kb-wallet-back-main = ⬅️ Back to Menu

wallet-history-empty = <i> Transaction history is empty </i>
wallet-history-title = 📜 <b>Transaction History</b>

wallet-deposit-removed-toast = Manual top-up is disabled. Select a plan
wallet-payment-gateway-error = ❌ Payment gateway error. Please try again later.
wallet-invalid-invoice-id = ❌ Invalid payment identifier.
wallet-invoice-not-found = ❌ Invoice not found in the database.

wallet-subscription-paid-success-screen =
    ✅ <b>Payment confirmed!</b>

    Subscription is active until { $new_end }.
wallet-subscription-activated-toast = Subscription activated

wallet-balance-paid-success-screen =
    ✅ <b>Payment confirmed!</b>

    Your balance has been credited. Current balance: { $balance }
wallet-success-toast = Success!
billing-tx-trial-description = Trial period { $days }d.
billing-tx-community-bonus-description = Bonus for joining the community

wallet-invoice-expired-screen = ❌ Invoice has expired.
wallet-expired-toast = Expired

wallet-payment-partial-screen =
    ⚠️ <b>Partial payment detected.</b>

    Received: { $paid_amount }
    Expected: { $expected_amount }
    Still needed: { $needed_amount }
wallet-payment-partial-toast = Partial payment detected
wallet-payment-not-found-yet = ⏳ Payment has not been detected yet.
wallet-payment-processing = ⏳ Payment is already being processed. Please wait a few seconds.

wallet-payment-price-changed-screen =
    ✅ <b>Payment confirmed!</b>

    Funds were credited to your balance: { $balance }
    Auto-activation was not completed because the current price has changed.
    Additional funds needed to purchase the plan: { $needed }
wallet-payment-price-changed-toast = Funds credited, auto-activation requires an additional payment
