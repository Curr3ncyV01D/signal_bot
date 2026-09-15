# Main menu, onboarding, and entry flow.

main-menu-status-active = ✅ Active until { $subscription_end }
main-menu-status-inactive = ❌ Inactive

main-menu =
    👋 Welcome, <b>{ $full_name }</b>!

    I am a professional liquidation monitoring terminal.
    You will receive notifications when strong market moves begin.

    💎 Subscription: <b>{ $subscription_status }</b>
    💰 Balance: <b>{ $balance }</b> USDT

    👇 Select an action below:

trial-button-news-channel = 📢 News Channel
trial-button-check-subscription = 🎁 Activate Access

onboarding-language-screen =
    🌐 <b>Добро пожаловать / Welcome!</b>

    Выберите язык интерфейса, чтобы завершить настройку.
    Choose your interface language to complete setup.
onboarding-language-selected = Language saved

onboarding-presets-screen =
    🎯 <b>Choose Your Strategy Profile</b>

    This is a quick start for CSL filters. One tap applies ready-made filter settings and enables all core signal types.

    <b>⚡ Scalping</b>
    Uses our tools to find anomalies on altcoins.
    • Signal frequency: <b>High</b>
    • Approx. liquidation volume: <b>{ $scalper_threshold }</b> $

    <b>⚖️ Balanced</b>
    A hybrid profile for day-to-day trading.
    • Signal frequency: <b>Medium</b>
    • Approx. liquidation volume: <b>{ $balanced_threshold }</b> $

    <b>🛡 Conservative</b>
    Focuses on larger moves with a higher noise filter.
    • Signal frequency: <b>Low</b>
    • Approx. liquidation volume: <b>{ $conservative_threshold }</b> $
onboarding-preset-button-scalper = ⚡ Scalping
onboarding-preset-button-balanced = ⚖️ Balanced
onboarding-preset-button-conservative = 🛡 Conservative
onboarding-preset-button-skip = Skip
onboarding-preset-applied-scalper = "Scalping" profile applied
onboarding-preset-applied-balanced = "Balanced" profile applied
onboarding-preset-applied-conservative = "Conservative" profile applied
onboarding-preset-skipped = Onboarding completed with default settings

community-bonus-screen =
    🎁 <b>Your welcome bonus: +{ $hours } hours of VIP access!</b>

    We are building not just a tool, but a closed community of traders. Join our chat to:

    🔹 Discuss Bybit signals in real time.
    🔹 Share working strategies and settings.
    🔹 Get help from experienced members

    <b>Join the group and press the button below to instantly claim extra 2 days of subscription</b>
community-bonus-button-join = 🎁 Join the chat
community-bonus-button-verify = ✅ Claim Bonus
community-bonus-button-later = Join Later
community-bonus-unavailable = The community bonus is currently unavailable.
community-bonus-already-used = The community join bonus has already been claimed.
community-bonus-verification-error = Failed to verify your community membership. Please try again later.
community-bonus-join-required = Join the community first, then run the verification again.
community-bonus-activation-failed = Failed to grant bonus access. Please try again later.
community-bonus-granted-toast = +{ $hours }h of access granted
community-bonus-later-toast = You can activate the bonus later from the main menu

trial-unavailable-news-channel = Channel-based trial is unavailable: NEWS_CHANNEL_ID is not configured.
trial-screen =
    🎁 <b>24-hour trial period</b>

    We provide you with 24 hours of trial access.
    We also invite you to our news channel so you can follow updates and important announcements.
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

kb-main-trial = 🎁 Trial period
kb-main-community-bonus = 🎁 Join the chat and get a gift
kb-main-renew = ⚡️ Extend subscription
kb-main-renew-left = ⚡️ Extend subscription (left { $days ->
    [one] { $days } day
    [few] { $days } days
   *[other] { $days } days
})
kb-main-wallet = 💰 Wallet ({ $balance } USDT)
kb-main-profile = 👤 Profile
kb-main-settings = ⚙️ Settings and Filters
kb-main-support = 👨‍💻 Technical Support
kb-main-chat = 📥 Community Chat

kb-status-refresh = 🔄 Refresh Status

gate-subscription-verified = ✅ Subscription confirmed! Free signal stream has been resumed.
gate-subscription-not-found = ❌ You have not yet joined our channel and chat. Please join both resources and try again.
gate-unsubscribed-warning = ⚠️ Signal delivery is paused. Subscribe to our channel and chat to receive signals.
gate-verify-button = 🔄 Verify Subscription

# ===== Clean State Model (Main Menu 4-state / Gate Screen) =====
main-menu-status-vip-active = 💎 Subscription: ✅ Active until { $subscription_end }. You receive a clean personal signal stream.
main-menu-status-free-active = 💎 Subscription: 🆓 Free tier (noisy stream). Delivery is active.
main-menu-status-free-paused = 💎 Subscription: ❌ Not active.

⚠️ Signal delivery is paused. Press the unlock button below to start receiving signals.
main-menu-status-trial-available = 💎 Subscription: ❌ Not active.

🎁 You have a free 3-day VIP trial available.
kb-main-unlock-signals = 🔓 Enable Free Signals
kb-main-upgrade-vip = 💎 Upgrade to VIP (Remove Noise)
gate-unlock-screen = ⚠️ Activate Free Signal Stream

To receive the free Bybit liquidation stream in real time:
1. Subscribe to our News Channel
2. Join the Community Chat

After joining, press the confirmation button below:
gate-button-verify-action = ✅ Verify and Enable Signals
