# Settings menu, prompts, and explanatory texts.

settings-title =
    <b>📊 Liquidation Filters (Mode: { $threshold_mode }):</b>
    🔶 Volume threshold: <b>${ $threshold }</b>
    🔸 Cascade threshold: <b>${ $threshold_cascade }</b>
    🔷 MCAP volume threshold: <b>{ $threshold_mcap_pct }</b> (min. <b>${ $threshold_mcap_usd_min }</b>)
    🔹 MCAP cascade threshold: <b>{ $threshold_cascade_mcap_pct }</b> (min. <b>${ $threshold_cascade_mcap_usd_min }</b>)

    <b>📊 Analytics Filters (OI):</b>
    📈 Minimum OI growth: <b>{ $threshold_oi_percent }</b> and <b>${ $threshold_oi_value }</b>

    💡 <i>Tip: disable indicators you do not need below to keep alerts compact.</i>

    <i>Press the '❓ Help' buttons below for details.</i>

settings-profile-error = ❌ Failed to load profile. Press /start
settings-save-error = ❌ Failed to save settings.
settings-saved = Setting saved
settings-mode-changed = Mode changed to { $mode }

settings-enter-mcap-pct =
    Enter the volume threshold as a percentage of market cap (for example, 0.005).
    Recommended value: 0.005%
settings-enter-mcap-min-usd = Enter the minimum USD floor for percentage mode (for example, 1000).
settings-enter-mcap-cascade-pct =
    Enter the cascade threshold as a percentage of market cap (for example, 0.01).
    Recommended value: 0.01%
settings-enter-mcap-cascade-min-usd = Enter the minimum USD floor for the cascade threshold (for example, 5000).
settings-positive-number-required = ❌ Please enter a positive number.
settings-mcap-pct-updated = ✅ Volume threshold set to { $value }
settings-mcap-min-usd-updated = ✅ Minimum volume floor set to ${ $value }
settings-mcap-cascade-pct-updated = ✅ Cascade threshold set to { $value }
settings-mcap-cascade-min-usd-updated = ✅ Minimum cascade floor set to ${ $value }

help-liquidations =
    📊 <b>Help: LIQUIDATIONS</b>

    The bot tracks forced trader position closures (Margin Calls).

    ⚡️ <b>Cascades:</b> A domino effect where one liquidation triggers the stops of others within 1-2 minutes.
    <i>How to use it:</i> Use it to detect extremes. A cascade stalling often marks a local bottom or top.

    📊 <b>Volume:</b> The accumulated liquidation volume over one hour.
    <i>How to use it:</i> Shows which side of the market is being broadly wiped out.

    🔥 <b>Squeeze:</b> A sharp burst where 5-minute volume is almost equal to the hourly volume.
    <i>How to use it:</i> Helps catch local volatility expansions.

    <i>Still have questions about how the algorithms work? Contact our specialist.</i>

help-analytics =
    📈 <b>Help: ANALYTICS</b>

    The bot analyzes market metrics to provide context for price action.

    🟢 <b>Open Interest (OI):</b> The total volume of open futures positions.
    <i>How to use it:</i> If Price rises + OI rises, new money is entering longs, which signals a strong trend. If Price falls + OI falls, it is often just legacy longs closing.

    📊 <b>CVD (Delta):</b> The difference between market buys and market sells.
    <i>How to use it:</i> "More Buys" signals aggressive buyer flow in the moment. Ideal for refining entries.

    ⚠️ <b>RSI (5m):</b> An indicator of an overheated asset.
    <i>How to use it:</i> RSI > 70 means the asset is overbought. Combined with short liquidations, it becomes a strong bearish reversal signal.

    <i>Still have questions about how the algorithms work? Contact our specialist.</i>

settings-enter-threshold = Enter a new volume threshold in USD (for example: 5000):
settings-enter-cascade-threshold = Enter a new Liquidation Cascade threshold in USD (for example: 2000):
settings-invalid-amount = ❌ Please enter a valid numeric amount
settings-threshold-updated = ✅ Volume threshold changed to <b>${ $value }</b>!
settings-cascade-threshold-updated = ✅ Cascade threshold changed to <b>${ $value }</b>!

settings-oi-thresholds-prompt =
    📊 <b>Configure Open Interest (OI) thresholds</b>

    Enter 2 numbers separated by a space:
    1. <b>Percentage change</b> (for example, 5.0)
    2. <b>USD value</b> (for example, 500000)

    <i>Example:</i> <code>5 500000</code>
settings-oi-thresholds-updated =
    ✅ OI thresholds updated!
    Percentage: <b>{ $percent }</b>
    Value: <b>${ $value }</b>

kb-settings-mode = ⚙️ Mode: { $mode ->
    [PERCENT] % MCAP 💎
   *[USD] USD 💵
}
kb-settings-help-liq = -- ❓ Help: LIQUIDATIONS --
kb-settings-help-analytics = -- ❓ Help: ANALYTICS --
kb-settings-threshold-volume-percent = 💰 Volume Threshold (%)
kb-settings-threshold-cascade-percent = ⚡ Cascade Threshold (%)
kb-settings-threshold-min-usd = Minimum Threshold ($)
kb-settings-threshold-cascade-min-usd = Minimum Cascade Threshold ($)
kb-settings-threshold-volume-usd = 💰 Volume Threshold ($)
kb-settings-threshold-cascade-usd = ⚡ Cascade Threshold ($)
kb-settings-toggle-cascade = { $status } Cascade
kb-settings-toggle-volume = { $status } Volume
kb-settings-toggle-squeeze = { $status } Squeeze
kb-settings-toggle-longs = 🟢 LONG: { $status }
kb-settings-toggle-shorts = 🔴 SHORT: { $status }
kb-settings-toggle-oi = { $status } OI
kb-settings-toggle-rsi = { $status } RSI
kb-settings-toggle-cvd = { $status } CVD
kb-settings-oi-thresholds = ⚙️ OI Thresholds (% and $)
kb-settings-back-main = ⬅️ Back to Menu
kb-settings-ask-question = 💬 Ask a Question
kb-settings-back = ⬅️ Back to Settings
