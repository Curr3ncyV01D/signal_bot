# Main menu, onboarding, and entry flow.

main-menu-status-active = ✅ Active until { $subscription_end }
main-menu-status-inactive = ❌ Inactive

main-menu =
    👋 Welcome, <b>{ $full_name }</b>!

    I am a professional Bybit liquidation monitoring terminal.
    You will receive alerts when strong market moves begin.

    💎 Subscription: <b>{ $subscription_status }</b>
    💰 Account Balance: <b>{ $balance }</b> USDT

    👇 Select an action below:

trial-button-news-channel = 📢 News Channel
trial-button-check-subscription = 🎁 Activate Access

onboarding-language-screen =
    🌐 <b>Добро пожаловать / Welcome!</b>

    Выберите язык интерфейса, чтобы завершить настройку.
    Choose your interface language to complete setup.
onboarding-language-selected = Language saved

trial-unavailable-news-channel = Channel-based trial is unavailable: NEWS_CHANNEL_ID is not configured.
trial-screen =
    🎁 <b>24-Hour Trial Access</b>

    We grant you 24 hours of trial access.
    We also invite you to our news channel so you can follow product updates and key announcements.
trial-mode-disabled = Channel mode is disabled. Trial activation via channel is unavailable.
trial-already-used = The trial period has already been used.
trial-activation-failed = Failed to activate the trial period. Please try again later.
trial-activated-screen =
    ✅ <b>Your 24-hour trial has been activated</b>

    💎 We recommend opening the <b>settings menu</b> and tuning signal filters to match your trading style. 💎
trial-activated-toast = 24-hour access activated

system-status-title = System is active
status-refresh-success = ✅ Status refreshed successfully!
status-refresh-no-changes = 🔄 No data changes
status-refresh-error = Refresh error
status-screen =
    { $status_emoji } <b>{ $title }</b>

    🌐 Connections: <b>{ $active_pool }</b> / <b>{ $total_pool }</b>
    💓 Last API heartbeat: <b>{ $latency }</b> ago

    📡 Monitored pairs: <b>{ $active_symbols }</b>
    🧠 Cached events: <b>{ $total_events }</b>
    { $queue_status } <b>Processing queue:</b> <b>{ $queue_size }</b>
    📊 Load: CPU <b>{ $cpu_pct }</b>% | RAM <b>{ $ram_pct }</b>%

    🕒 Uptime: <b>{ $uptime }</b>
    🕒 Server time: { $server_time } UTC

kb-main-trial = 🎁 Trial Period
kb-main-renew = ⚡️ Extend Subscription
kb-main-renew-left = ⚡️ Extend Subscription ({ $days ->
    [one] { $days } day left
   *[other] { $days } days left
})
kb-main-wallet = 💰 Wallet ({ $balance } USDT)
kb-main-profile = 👤 Profile
kb-main-settings = ⚙️ Settings and Filters
kb-main-support = 👨‍💻 Technical Support

kb-status-refresh = 🔄 Refresh Status
