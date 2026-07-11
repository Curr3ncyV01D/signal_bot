main-menu-status-active = ✅ Active until { $subscription_end }
main-menu-status-inactive = ❌ Inactive

main-menu =
    👋 Welcome, <b>{ $full_name }</b>!

    I am a professional Bybit liquidation monitoring terminal.
    You will receive alerts when strong market moves begin.

    💎 Subscription: <b>{ $subscription_status }</b>
    💰 Balance: <b>{ $balance }</b> USDT

    👇 Choose an action below:

trial-button-news-channel = 📢 News channel
trial-button-check-subscription = 🎁 Activate access
main-button-home = 🏠 Main menu
main-button-private-channel = 🚀 Open private channel

onboarding-language-screen =
    🌐 <b>Welcome!</b>

    Choose your interface language to complete setup.
onboarding-language-selected = Language saved

trial-unavailable-news-channel = Channel-based trial is unavailable: `NEWS_CHANNEL_ID` is not configured.
trial-screen =
    🎁 <b>24-hour trial access</b>

    We provide you with test access for 24 hours.
    We also invite you to join our news channel to stay updated on important announcements.
trial-mode-disabled = Channel mode is disabled. Trial activation via channel is unavailable.
profile-not-found-start = Profile not found. Press /start.
trial-already-used = The trial period has already been used.
subscription-check-temporary-unavailable = Subscription check is temporarily unavailable. Try again a bit later.
trial-activation-failed = Failed to activate the trial period. Try again later.
trial-activated-screen =
    ✅ <b>The 24-hour trial period has been activated!</b>

    💎 We recommend that you open the settings menu and customize the signal filters to your liking! 💎
trial-activated-toast = 24-hour access activated

channel-mode-disabled = Channel mode is disabled: the private channel link is unavailable.
channel-link-caption =
    👉 Your channel access link:
    { $invite_link }
channel-link-error = Failed to get the invite link. The bot is not an admin.

system-status-title = System is active
status-refresh-success = ✅ Status refreshed successfully!
status-refresh-no-changes = 🔄 No data changes
status-refresh-error = Refresh error

settings-title =
    <b>📊 Liquidation Filters (Mode: { $threshold_mode }):</b>
    🔶 Volume threshold: <b>${ $threshold }</b>
    🔸 Cascade threshold: <b>${ $threshold_cascade }</b>
    🔷 MCAP volume threshold: <b>{ $threshold_mcap_pct }</b> (min. <b>${ $threshold_mcap_usd_min }</b>)
    🔹 MCAP cascade threshold: <b>{ $threshold_cascade_mcap_pct }</b> (min. <b>${ $threshold_cascade_mcap_usd_min }</b>)

    <b>📊 Analytics Filters (OI):</b>
    📈 Min. OI growth: <b>{ $threshold_oi_percent }</b> and <b>${ $threshold_oi_value }</b>

    💡 <i>Tip: Disable indicators you do not need below to keep alerts more compact.</i>

    <i>Press the '❓ Help' buttons below to see details.</i>

settings-profile-error = ❌ Failed to load profile. Press /start.
settings-save-error = ❌ Failed to save settings.
settings-saved = Setting saved
settings-mode-changed = Mode changed to { $mode }
settings-error-profile = Profile error
settings-error-save = Save error

settings-enter-mcap-pct =
    Enter the volume threshold as a percentage of market cap (for example, 0.005).
    Recommended value: 0.005%
settings-enter-mcap-min-usd = Enter the minimum USD floor for percentage mode (for example, 1000).
settings-enter-mcap-cascade-pct =
    Enter the cascade threshold as a percentage of market cap (for example, 0.01).
    Recommended value: 0.01%
settings-enter-mcap-cascade-min-usd = Enter the minimum USD floor for cascades (for example, 5000).
settings-positive-number-required = ❌ Please enter a positive number.
settings-mcap-pct-updated = ✅ Volume threshold set to { $value }
settings-mcap-min-usd-updated = ✅ Minimum volume floor set to ${ $value }
settings-mcap-cascade-pct-updated = ✅ Cascade threshold set to { $value }
settings-mcap-cascade-min-usd-updated = ✅ Minimum cascade floor set to ${ $value }

help-liquidations =
    📊 <b>Help: LIQUIDATIONS</b>

    The bot tracks forced trader position closures (margin calls).

    ⚡️ <b>Cascades:</b> A domino effect where one liquidation triggers stops from others within 1-2 minutes.
    <i>How to use it:</i> Look for extremes. A cascade stopping often marks a local bottom or top in the market.

    📊 <b>Volume:</b> The accumulated liquidation value over 1 hour.
    <i>How to use it:</i> Shows who is being broadly wiped out in the market.

    🔥 <b>Squeeze:</b> A sharp spike where the 5-minute volume is almost equal to the hourly volume.
    <i>How to use it:</i> Enter on local volatility bursts.

    <i>Still have questions about how the algorithms work? Contact our specialist.</i>

help-analytics =
    📈 <b>Help: ANALYTICS</b>

    The bot analyzes metrics to provide context for price action.

    🟢 <b>Open Interest (OI):</b> The volume of all open futures positions.
    <i>How to use it:</i> If price rises + OI rises, new money is entering longs (a strong trend). If price falls + OI falls, it is more likely just old longs closing.

    📊 <b>CVD (Delta):</b> The difference between market buys and sells.
    <i>How to use it:</i> "More Buys" means buyers are being aggressive right now. Great for spotting an entry point.

    ⚠️ <b>RSI (5m):</b> An indicator of asset overheating.
    <i>How to use it:</i> RSI > 70 means the asset is overbought. Combined with short liquidations, this becomes a very strong bearish reversal signal.

    <i>Still have questions about how the algorithms work? Contact our specialist.</i>

settings-enter-threshold = Enter a new volume threshold in USD (for example: 5000):
settings-enter-cascade-threshold = Enter a cascade threshold in USD (for example: 2000):
settings-invalid-amount = ❌ Please enter a valid numeric amount
settings-threshold-updated = ✅ Volume threshold changed to <b>${ $value }</b>!
settings-cascade-threshold-updated = ✅ Cascade threshold changed to <b>${ $value }</b>!

settings-oi-thresholds-prompt =
    📊 <b>Set Open Interest (OI) thresholds</b>

    Enter 2 numbers separated by a space:
    1. <b>Percent change</b> (for example, 5.0)
    2. <b>Value in USD</b> (for example, 500000)

    <i>Example:</i> <code>5 500000</code>
settings-oi-thresholds-updated =
    ✅ OI thresholds updated!
    Percent: <b>{ $percent }</b>
    Value: <b>${ $value }</b>

status-screen =
    { $status_emoji } <b>{ $title }</b>

    🌐 Connections: <b>{ $active_pool }</b> / <b>{ $total_pool }</b>
    💓 Last API signal: <b>{ $latency }</b> ago

    📡 Monitored pairs: <b>{ $active_symbols }</b>
    🧠 Cached events: <b>{ $total_events }</b>
    { $queue_status } <b>Processing queue:</b> <b>{ $queue_size }</b>
    📊 Load: CPU <b>{ $cpu_pct }</b>% | RAM <b>{ $ram_pct }</b>%

    🕒 Uptime: <b>{ $uptime }</b>
    🕒 Server time: { $server_time } UTC

kb-common-back = ⬅️ Back
kb-common-close = ❌ Close

kb-main-trial = 🎁 Trial period
kb-main-renew = ⚡️ Extend subscription
kb-main-private-channel = 🚀 Open private channel
kb-main-renew-left = ⚡️ Extend subscription ({ $days ->
    [one] { $days } day left
   *[other] { $days } days left
})
kb-main-wallet = 💰 Wallet ({ $balance } USDT)
kb-main-settings = ⚙️ Settings and filters
kb-main-support = 👨‍💻 Support

kb-status-refresh = 🔄 Refresh status

kb-settings-mode = ⚙️ Mode: { $mode ->
    [PERCENT] % MCAP 💎
   *[USD] USD 💵
}
kb-settings-help-liq = -- ❓ Help: LIQUIDATIONS --
kb-settings-help-analytics = -- ❓ Help: ANALYTICS --
kb-settings-threshold-volume-percent = 💰 Volume threshold (%)
kb-settings-threshold-cascade-percent = ⚡ Cascade threshold (%)
kb-settings-threshold-min-usd = Min threshold ($)
kb-settings-threshold-cascade-min-usd = Min cascade threshold ($)
kb-settings-threshold-volume-usd = 💰 Volume threshold ($)
kb-settings-threshold-cascade-usd = ⚡ Cascade threshold ($)
kb-settings-toggle-cascade = { $status } Cascade
kb-settings-toggle-volume = { $status } Volume
kb-settings-toggle-squeeze = { $status } Squeeze
kb-settings-toggle-longs = 🟢 LONG: { $status }
kb-settings-toggle-shorts = 🔴 SHORT: { $status }
kb-settings-toggle-oi = { $status } OI
kb-settings-toggle-rsi = { $status } RSI
kb-settings-toggle-cvd = { $status } CVD
kb-settings-oi-thresholds = ⚙️ OI thresholds (% and $)
kb-settings-back-main = ⬅️ Back to menu
kb-settings-ask-question = 💬 Ask a question
kb-settings-back = ⬅️ Back to settings

kb-wallet-renew = 💎 Extend subscription
kb-wallet-deposit = 💰 Top up balance
kb-wallet-autorenew-on = 🔁 Auto-renewal: ON
kb-wallet-autorenew-off = 🔁 Auto-renewal: OFF
kb-wallet-language-ru = 🌐 Language: Russian
kb-wallet-language-en = 🌐 Language: English
kb-wallet-partner = 🤝 Partner program
kb-wallet-history = 📜 Transaction history
kb-wallet-back-main = ⬅️ Back to menu
kb-wallet-pay-cryptobot = 🔗 Pay with CryptoBot
kb-wallet-check-payment = 🔄 Check payment
kb-wallet-payment-issue = 👨‍💻 Payment issue?
kb-wallet-plan-months = { $months ->
    [one] { $months } month
   *[other] { $months } months
}
kb-wallet-plan-days = { $days ->
    [one] { $days } day
   *[other] { $days } days
}
kb-wallet-plan-price = { $days ->
    [30] 1 month
    [60] 2 months
    [90] 3 months
    [150] 5 months
   *[other] { $days } days
} — { $price } USDT
kb-wallet-confirm-debit = ✅ Confirm debit
kb-wallet-cancel = ❌ Cancel

kb-admin-analytics = 📊 Analytics and metrics
kb-admin-broadcast = 📣 Create broadcast
kb-admin-channel-settings = 📢 Channel settings
kb-admin-users = 👥 Users list
kb-admin-main-menu = 🔙 Main menu
kb-admin-unblock = ✅ Unblock
kb-admin-block = 🛑 Block
kb-admin-edit-subscription = 📅 Edit subscription
kb-admin-send-message = ✉️ Send message
kb-admin-channel-posting-on = 🟢 Posting ON
kb-admin-channel-posting-off = 🔴 Posting OFF
kb-admin-channel-oi-thresholds = ⚙️ OI thresholds (% and $)
kb-admin-channel-restart-dashboard = 🔄 Restart dashboard
kb-admin-bi-finance = 💰 Finance
kb-admin-bi-audience = 👥 Audience
kb-admin-bi-system = ⚙️ System
kb-admin-bi-back-admin = ⬅️ Back to admin
kb-admin-refresh = 🔄 Refresh
kb-admin-bi-export-csv = 📄 Export .csv
kb-admin-bi-find-coin = 🔍 Find coin
kb-admin-bi-export-txt = 📄 List (TXT)
kb-admin-broadcast-all = 👥 Everyone
kb-admin-broadcast-vip = 💎 Subscribers only
kb-admin-broadcast-free = 🆓 Non-subscribers only
kb-admin-broadcast-start = 🚀 Start broadcast
kb-admin-broadcast-change-cancel = 🔄 Change / Cancel

shop-subscription-menu =
    💎 <b>VIP Subscription</b>

    VIP access benefits:
    • Personal alert flow inside the bot
    • Personal bot settings
    • Real-time analytics

    Choose a suitable plan:
shop-referral-bonus-notification =
    🤝 <b>Referral bonus credited!</b>

    Your referral made a purchase and you received { $bonus_amount }.
shop-invite-link =

    👉 <b>Your access link:</b>
    { $invite_link }
shop-invite-link-error =

    <i>(Error: the bot could not create an invite link. Contact an admin.)</i>
shop-invalid-plan-params = ❌ Invalid plan parameters.
shop-plan-not-found = Error: plan not found.
shop-balance-purchase-confirm =
    💎 <b>Subscription extension from balance</b>

    You have enough balance: { $balance }.

    Extend the subscription for { $plan_label } for { $price }?
shop-direct-pay-screen =
    💎 <b>Subscription payment: { $plan_label }</b>

    💰 Price: { $price }
    💳 Current balance: { $balance }

    Your balance is insufficient, so we prepared a CryptoBot payment link.
shop-insufficient-balance = ❌ Insufficient balance.
shop-purchase-success =
    🎉 <b>Subscription activated successfully!</b>

    📅 Active until: { $new_end }
    💰 Deducted from balance: { $price }
shop-subscription-extended = Subscription extended
shop-purchase-cancelled = Purchase cancelled

wallet-main-screen =
    👛 <b>Wallet</b>

    💰 Current balance: { $balance } USDT
    Monthly subscription price: { $monthly_price } USDT

    🆔 Your ID: { $user_id }

    If you have payment issues, contact support
wallet-language-changed = Language changed
wallet-autorenew-enabled = enabled
wallet-autorenew-disabled = disabled
wallet-autorenew-status = Auto-renewal { $status }
wallet-history-empty = <i>Transaction history is empty</i>
wallet-history-title = 📜 <b>Transaction history</b>
wallet-partner-screen =
    🤝 <b>Partner program</b>

    Invite friends and get { $bonus_percent }% of their purchases credited to your balance for life!

    🔗 <b>Your link:</b>
    { $referral_link }

    👥 Invited: { $invited_count }
    💸 Earned: { $total_rewards }
wallet-deposit-screen =
    ➕ <b>Balance top-up</b>

    Choose the top-up amount in USDT.
    Payment is accepted via { $cryptobot }.
wallet-cryptopay-timeout = ❌ CryptoPay API timeout. Try again later.
wallet-cryptopay-error = ❌ CryptoPay API error. Try again later.
wallet-invoice-screen =
    🧾 <b>Invoice #{ $invoice_id }</b>

    Amount: { $amount }
    Status: { $pending_status }

    Click the button below to open CryptoBot:
wallet-payment-pending-status = Pending payment
wallet-invalid-invoice-id = ❌ Invalid invoice ID.
wallet-invoice-not-found = ❌ Invoice not found in the database.
wallet-invalid-subscription-payload = ❌ Invalid subscription payload.
wallet-subscription-activation-failed = ❌ Failed to activate the subscription after payment. Contact support.
wallet-subscription-paid-success-screen =
    ✅ <b>Payment confirmed!</b>

    Subscription is active until { $new_end }.
wallet-subscription-activated-toast = Subscription activated
wallet-balance-paid-success-screen =
    ✅ <b>Payment confirmed!</b>

    Your balance was topped up. Current balance: { $balance }
wallet-success-toast = Success!
wallet-crediting-error = Crediting error. Contact support.
wallet-invoice-expired-screen = ❌ Invoice expired.
wallet-expired-toast = Expired
wallet-payment-not-found-yet = ⏳ Payment not detected yet.

admin-user-blocked-notification =
    ❌ <b>Your account has been blocked by an administrator.</b>
    Access to bot features is restricted.
admin-user-subscription-updated-notification =
    📅 <b>Your subscription was updated by an administrator!</b>

    New expiration date: { $subscription_end }
admin-user-subscription-cancelled-notification = ❌ <b>Your subscription was cancelled by an administrator.</b>
admin-personal-message-prompt =
    Enter a message for the user.

    Any format is supported: text, photo, voice messages.
admin-personal-message-success = ✅ Message successfully sent to user { $user_id }.
admin-personal-message-user-blocked = ❌ Error: the user has blocked the bot.
admin-personal-message-copy-failed = ❌ Error: failed to send the message to the user.
admin-personal-message-cancelled = Action cancelled.
admin-personal-message-user-not-found = ❌ User not found in the database.

join-request-declined-notification =
    ❌ <b>Your request to join was declined.</b>

    You do not have an active subscription or trial period. Please open the bot and use /start to purchase a subscription.
