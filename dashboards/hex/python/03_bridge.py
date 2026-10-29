# Hex Python cell 3: why spend moved - the price-volume-mix bridge for the latest week.
b = bridge.iloc[0]
steps = [
    ("Prior week", b.prior_spend_usd, "absolute"),
    ("Volume", b.volume_effect_usd, "relative"),
    ("Mix", b.mix_effect_usd, "relative"),
    ("Price", b.price_effect_usd, "relative"),
    ("This week", b.spend_usd, "total"),
]
fig_bridge = go.Figure(
    go.Waterfall(
        x=[s[0] for s in steps], y=[s[1] for s in steps], measure=[s[2] for s in steps],
        text=[money(s[1]) if s[2] != "relative" or money(s[1]) == "$0"
              else ("+" if s[1] > 0 else "") + money(s[1]) for s in steps],
        textposition="outside", textfont=dict(color=INK),
        increasing=dict(marker=dict(color=UP)), decreasing=dict(marker=dict(color=DOWN)),
        totals=dict(marker=dict(color=AXIS)),
        connector=dict(line=dict(color=AXIS, width=1, dash="dot")),
        hovertemplate="%{x}: %{text}<extra></extra>",
    )
)
spend_change = b.spend_usd - b.prior_spend_usd
base_layout(
    fig_bridge, f"Implied spend {'rose' if spend_change >= 0 else 'fell'} "
    f"{money(abs(spend_change))} in the week of {latest_week:%Y-%m-%d}",
    "Volume: the market grew. Mix: traffic moved between models with different prices. "
    "Price: list prices changed.<br>Price effects start 2026-10-28, when daily price "
    "snapshots began; earlier weeks show $0 by construction.",
)
fig_bridge.update_layout(waterfallgap=0.5)
fig_bridge.update_yaxes(tickprefix="$", tickformat="~s", rangemode="tozero")
fig_bridge.update_layout(showlegend=False, height=400)
fig_bridge
