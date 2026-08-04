# Settings menu, prompts, and explanatory texts.

settings-title =
    <b>📊 Liquidation filters (Mode: { $threshold_mode }):</b>
    - Volume threshold: ${ $threshold }
    - Cascade threshold: ${ $threshold_cascade }

    - MCAP volume threshold: { $threshold_mcap_pct } (min. ${ $threshold_mcap_usd_min })
    - MCAP cascade threshold: { $threshold_cascade_mcap_pct } (min. ${ $threshold_cascade_mcap_usd_min })

    📈 Analytics filters:
    Min. OI growth: { $threshold_oi_percent } and ${ $threshold_oi_value }
    RSI-gate: { $rsi_min } / { $rsi_max }

settings-filters-screen =
    <b>📊 Liquidation filters (Mode: { $threshold_mode }):</b>
    - Volume threshold: ${ $threshold }
    - Cascade threshold: ${ $threshold_cascade }

    - MCAP volume threshold: { $threshold_mcap_pct } 
    (minimum ${ $threshold_mcap_usd_min })
    - MCAP cascade threshold: { $threshold_cascade_mcap_pct } 
    (minimum ${ $threshold_cascade_mcap_usd_min })

    📈 Analytics filters:
    Min. OI growth: { $threshold_oi_percent } and ${ $threshold_oi_value }
    RSI-gate: { $rsi_min } / { $rsi_max }

    These settings affect which events trigger an alert.
    You can change the mode, thresholds, and trigger composition below.

    <i>Press the '❓ Help' button to learn more.</i>

settings-display-screen =
    <b>👁 Message display</b>

    These settings only change the visual composition of alerts.
    They enable or hide extra data blocks inside the message text.

    <i>💡 Tip: disable indicators you do not need below to keep alerts compact.</i>
    
    <i>Press the '❓ Help' button to learn more.</i>
settings-display-state-on = On
settings-display-state-off = Off

settings-profile-error = ❌ Failed to load profile. Press /start
settings-save-error = ❌ Failed to save settings.
settings-saved = Setting saved
settings-mode-changed = Mode changed to { $mode }

settings-enter-mcap-pct =
    Enter the volume threshold as a % of market cap (for example, 0.005).
    Recommended value: 0.005%
settings-enter-mcap-min-usd = Enter the minimum USD floor for % mode (for example, 1000).
settings-enter-mcap-cascade-pct =
    Enter the cascade threshold as a % of market cap (for example, 0.01).
    Recommended value: 0.01%
settings-enter-mcap-cascade-min-usd = Enter the minimum USD floor for cascades (for example, 5000).
settings-positive-number-required = ❌ Please enter a positive number.
settings-mcap-pct-updated = ✅ Volume threshold set to { $value }
settings-mcap-min-usd-updated = ✅ Min. volume floor set to ${ $value }
settings-mcap-cascade-pct-updated = ✅ Cascade threshold set to { $value }
settings-mcap-cascade-min-usd-updated = ✅ Min. cascade floor set to ${ $value }

help-liquidations =
    📊 <b>Help: LIQUIDATIONS</b>

    The bot tracks forced position closures (Margin Calls).

    ⚡️ <b>Cascades:</b> A “domino” effect where one liquidation triggers the stops of others within 1-2 minutes.
    <i>How to use:</i> Finding extremes. A cascade stalling often marks a local bottom or top.

    📊 <b>Volume:</b> The total liquidation volume over 1 hour.
    <i>How to use:</i> Shows which side of the market is being broadly wiped out.

    🔥 <b>Squeeze:</b> A sharp burst where the 5-minute volume is almost equal to the hourly volume.
    <i>How to use:</i> Entry on local volatility spikes.

    <i>Still have questions about how the algorithms work? Contact our specialist.</i>

help-analytics =
    📈 <b>Help: ANALYTICS</b>

    The bot analyzes metrics to provide context for the price move.

    🟢 <b>Open Interest (OI):</b> The total volume of open futures positions.
    <i>How to use:</i> If Price rises + OI rises = new money enters longs (strong trend). If Price falls + OI falls = legacy longs closing.

    📊 <b>CVD (Delta):</b> The difference between market buys and market sells.
    <i>How to use:</i> “More Buys” means aggressive buyer flow in the moment. Ideal for entry timing.

    ⚠️ <b>RSI (5m):</b> An indicator of an overheated asset.
    <i>How to use:</i> RSI > 70 = asset is overbought. Combined with short liquidations, it becomes a strong bearish reversal signal.

    🚦 <b>RSI-Gate (extremes filter):</b> Extra gate a signal must pass through. Set it to 100/0 to disable. 30/70 is classic. 20/80 is strict.
    <i>How to use:</i> A signal is only sent if the current RSI ≤ lower bound (oversold) OR ≥ upper bound (overbought). If RSI data is not ready yet, the signal is blocked.

    <i>Still have questions about how the algorithms work? Contact our specialist.</i>

settings-enter-threshold = Enter a new volume threshold in USD (for example: 5000):
settings-enter-cascade-threshold = Enter the cascade threshold in USD (for example: 2000):
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

settings-rsi-thresholds-prompt =
    ⚠️ <b>Configure RSI Gate</b>

    Enter 2 numbers separated by a space:
    1. <b>Lower bound (oversold)</b> — e.g. 30
    2. <b>Upper bound (overbought)</b> — e.g. 70

    Or select a preset below. Set to 100/0 to disable the filter.
    Values must be in the 0–100 range.

    <i>Example:</i> <code>30 70</code>
settings-rsi-thresholds-updated =
    ✅ RSI Gate set: <b>{ $rsi_min } / { $rsi_max }</b>
    { $explain_text }
settings-rsi-thresholds-disabled =
    ✅ RSI filter <b>disabled</b> (100/0). All signals pass without RSI restrictions.
settings-rsi-gate-explain-disabled = Filter <b>disabled</b> — all signals pass.
settings-rsi-gate-explain-conservative = <i>Strict filter</i> — only clear extremes.
settings-rsi-gate-explain-balanced = <i>Classic bands</i> — the usual 30/70 setup.
settings-rsi-gate-explain-scalper = <i>Narrow band</i> — alert on any volatility peak.
settings-rsi-gate-explain-custom = <i>Custom profile</i>.
settings-rsi-thresholds-invalid = ❌ Enter 2 numbers between 0 and 100 separated by a space (example: <code>30 70</code>).

settings-preset-catalog-screen =
    🎯 <b>Strategy Profiles</b>

    A preset fully replaces your current filters: USD thresholds, MCAP thresholds, OI, RSI-Gate and all signal toggles.

    <b>⚡ Scalping</b>
    For active trading and frequent altcoin alerts.

    Default mode: <b>{ $scalper_mode }</b>
    Frequency: <b>high</b>
    
    • Volume: <b>${ $scalper_threshold }</b> | Cascade: <b>${ $scalper_cascade }</b>
    • OI: <b>{ $scalper_oi_percent }</b> / <b>${ $scalper_oi_value }</b>
    • RSI-gate: <b>{ $scalper_rsi_min } / { $scalper_rsi_max }</b>

    <b>⚖️ Balanced</b>
    For day-to-day trading with a moderate alert flow.

    Default mode: <b>{ $balanced_mode }</b>
    Frequency: <b>medium</b>

    • Volume: <b>${ $balanced_threshold }</b> | Cascade: <b>${ $balanced_cascade }</b>
    • OI: <b>{ $balanced_oi_percent }</b> / <b>${ $balanced_oi_value }</b>
    • RSI-gate: <b>{ $balanced_rsi_min } / { $balanced_rsi_max }</b>

    <b>🐋 Conservative</b>
    For focusing on larger moves and rarer but stronger events.

    Default mode: <b>{ $conservative_mode }</b>
    Frequency: <b>low</b>

    • Volume: <b>${ $conservative_threshold }</b> | Cascade: <b>${ $conservative_cascade }</b>
    • OI: <b>{ $conservative_oi_percent }</b> / <b>${ $conservative_oi_value }</b>
    • RSI-gate: <b>{ $conservative_rsi_min } / { $conservative_rsi_max }</b>

settings-preset-confirm-screen =
    ⚠️ <b>This will replace your current filters. Are you sure?</b>

    <b>{ $preset_name }</b>
    { $preset_description }

    Default mode: <b>{ $recommended_mode }</b>

    <b>USD:</b> volume <b>${ $threshold }</b>, cascade <b>${ $threshold_cascade }</b>
    <b>% MCAP:</b> volume <b>{ $threshold_mcap_pct }</b> (min. <b>${ $threshold_mcap_usd_min }</b>)
    <b>% MCAP Cascade:</b> <b>{ $threshold_cascade_mcap_pct }</b> (min. <b>${ $threshold_cascade_mcap_usd_min }</b>)
    <b>OI:</b> <b>{ $threshold_oi_percent }</b> and <b>${ $threshold_oi_value }</b>
    <b>RSI-gate:</b> <b>{ $rsi_min } / { $rsi_max }</b>

    You can fine-tune any parameter manually after applying it.
settings-preset-name-scalper = ⚡ Scalping
settings-preset-name-balanced = ⚖️ Balanced
settings-preset-name-conservative = 🐋 Conservative
settings-preset-description-scalper = Looks for anomalies and fast impulses on altcoins. Best for users who want a dense stream of signals.
settings-preset-description-balanced = A universal profile for most users. Reduces noise while keeping good sensitivity.
settings-preset-description-conservative = Filters the market more aggressively than the others. Best for users who only want the most significant moves.
settings-preset-applied-toast = Preset { $preset_name } applied

kb-settings-mode = ⚙️ Mode: { $mode ->
    [PERCENT] % MCAP 💎
   *[USD] USD 💵
}
kb-settings-help-liq = -- ❓ Help: LIQUIDATIONS --
kb-settings-help-analytics = -- ❓ Help: ANALYTICS --
kb-settings-threshold-volume-percent = 💰 Volume Threshold (%)
kb-settings-threshold-cascade-percent = ⚡ Cascade Threshold (%)
kb-settings-threshold-min-usd = Min. threshold ($)
kb-settings-threshold-cascade-min-usd = Min. cascade threshold ($)
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
kb-settings-rsi-thresholds = ⚙️ RSI Bounds: { $rsi_min } / { $rsi_max }
kb-settings-rsi-menu = -- 🚦 RSI-Gate: setup --
kb-settings-rsi-preset-conservative = [ 20 / 80 ] 🐋
kb-settings-rsi-preset-balanced = [ 30 / 70 ] ⚖️
kb-settings-rsi-preset-scalper = [ 35 / 65 ] ⚡️
kb-settings-rsi-disable = [ 🔓 Disable (100/0) ]
kb-settings-rsi-manual = ✏️ Enter manually
kb-settings-rsi-back = ⬅️ Back to filters
kb-settings-preset-profiles = 🎯 Choose Strategy Profile
kb-settings-preset-scalper = ⚡ Scalping
kb-settings-preset-balanced = ⚖️ Balanced
kb-settings-preset-conservative = 🐋 Conservative
kb-settings-preset-confirm-apply = ✅ Apply Profile
kb-settings-preset-confirm-cancel = ⬅️ Back to Profiles
kb-settings-open-filters = 📊 Configure trigger filters
kb-settings-open-display = 👁 Configure message display
kb-settings-back-root = ⬅️ Back to General Settings
kb-settings-back-main = ⬅️ Back to Menu
kb-settings-ask-question = 💬 Ask a Question
kb-settings-back = ⬅️ Back to Settings
