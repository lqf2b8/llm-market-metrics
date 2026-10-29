# Hex Python cell 2: headline tiles - value, week-over-week change, 26-week sparkline.
recent = kpis[kpis.week_start > latest_week - pd.Timedelta(weeks=26)]
now = kpis[kpis.week_start == latest_week].iloc[0]
reliable = recent[recent.is_spend_reliable]

tiles = [
    ("Tokens", tokens_fmt(now.tokens), now.tokens_wow_change, recent, "tokens", tokens_fmt),
    ("Implied spend", money(now.implied_spend_usd), now.implied_spend_wow_change,
     reliable, "implied_spend_usd", money),
    ("Effective paid price", f"${now.effective_paid_usd_per_mtok:.2f} / M tokens",
     now.effective_paid_price_wow_change, reliable, "effective_paid_usd_per_mtok",
     lambda v: f"${v:.2f}"),
]
fig_headline = make_subplots(rows=1, cols=3, horizontal_spacing=0.06)
for i, (name, value, change, data, col, fmt) in enumerate(tiles, start=1):
    fig_headline.add_trace(
        go.Scatter(
            x=data.week_start, y=data[col], mode="lines", line=dict(color=ORANGE, width=2),
            hovertemplate="%{x|%b %d, %Y}: %{customdata}<extra></extra>",
            customdata=[fmt(v) for v in data[col]], showlegend=False,
        ),
        row=1, col=i,
    )
    fig_headline.add_trace(
        go.Scatter(x=[data.week_start.iloc[-1]], y=[data[col].iloc[-1]], mode="markers",
                   marker=dict(color=ORANGE, size=8, line=dict(color=SURFACE, width=2)),
                   hoverinfo="skip", showlegend=False),
        row=1, col=i,
    )
    arrow = "" if pd.isna(change) else ("▲" if change > 0 else "▼" if change < 0 else "")
    delta = "n/a" if pd.isna(change) else f"{arrow} {change:+.1%} vs prior week"
    domain = fig_headline.layout[f"xaxis{'' if i == 1 else i}"].domain
    for y, text, size, color, family in (
        (1.78, name, 13, INK_2, BODY_FONT),
        (1.40, f"<b>{value}</b>", 26, INK, HEADING_FONT),
        (1.14, delta, 13, INK_2, BODY_FONT),
    ):
        fig_headline.add_annotation(
            x=domain[0], y=y, xref="paper", yref="paper", xanchor="left", yanchor="bottom",
            showarrow=False, text=text, font=dict(size=size, color=color, family=family),
        )
base_layout(fig_headline, "", height=280)
fig_headline.update_layout(title=None, margin=dict(l=8, r=16, t=150, b=24))
fig_headline.update_xaxes(showticklabels=False, linecolor=GRID)
fig_headline.update_yaxes(showticklabels=False, showgrid=False)
if not now.is_spend_reliable:
    fig_headline.add_annotation(
        x=1, y=-0.12, xref="paper", yref="paper", xanchor="right", showarrow=False,
        text="Spend for this week is less reliable: under 90% of tokens are priced.",
        font=dict(color=INK_2, size=11),
    )
fig_headline
