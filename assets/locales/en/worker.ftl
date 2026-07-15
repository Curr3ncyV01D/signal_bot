# Background notifications and worker-side messages.

payment-worker-reminder-active-link =
    ⏳ <b>Your payment link is still active.</b>

    If you are experiencing payment issues, contact Technical Support. We will help you resolve them.
payment-worker-subscription-paid-notification =
    ✅ <b>Payment confirmed!</b>

    Your balance has been credited by <b>{ $amount }</b>.
    The <b>{ $days }</b>-day plan was activated automatically until <b>{ $new_end }</b>.
payment-worker-balance-paid-notification =
    ✅ <b>Payment received!</b>

    Your balance has been credited by <b>{ $amount }</b>.
payment-worker-partial-payment-notification =
    ⚠️ <b>Partial payment detected.</b>

    Received: <b>{ $paid_amount }</b>
    Expected: <b>{ $expected_amount }</b>

    To activate the plan, send an additional <b>{ $needed_amount }</b> to the same address.

    <b>🌐 Network:</b> { $network }
    <b>👛 Payment wallet:</b>

    { $wallet }
    <i>(tap the address to copy it)</i>
payment-worker-price-changed-notification =
    ✅ <b>Payment confirmed!</b>

    Funds were credited to your balance: <b>{ $balance }</b>
    Auto-activation was not completed because the plan price has changed.
    Additional funds needed to purchase the plan: <b>{ $needed }</b>.

manual-payment-approved-notification =
    ✅ <b>An administrator has confirmed your payment.</b>

    Credited to balance: <b>{ $amount }</b>
    Current balance: <b>{ $balance }</b>
manual-payment-rejected-notification =
    ❌ <b>The payment evidence for your invoice was rejected by an administrator.</b>

    Reason: { $reason }
    <i>If you believe this is an error, contact Technical Support.</i>

bouncer-trial-expiry-warning =
    ⏳ <b>Your trial access expires in 1 hour.</b>

    To avoid losing access to alerts, renew your subscription in advance via /start.

bouncer-subscription-expiry-warning =
    ⏳ <b>Your subscription expires in 24 hours.</b>

    Make sure your balance is sufficient for auto-renewal, or renew manually via /start.

bouncer-auto-renewal-success =
    ✅ <b>Subscription extended!</b>

    We successfully debited <b>{ $amount } USDT</b> from your balance. Thank you for staying with us.

bouncer-auto-renewal-failed-balance =
    ⚠️ <b>Insufficient funds!</b>

    We could not renew your subscription automatically. Top up your balance so you do not lose access to personal alerts in 1 hour.

bouncer-subscription-expired =
    ⚠️ <b>Your subscription/trial period has expired.</b>

    Personal signal delivery has been suspended.
    Press /start and renew your subscription to restore access.
