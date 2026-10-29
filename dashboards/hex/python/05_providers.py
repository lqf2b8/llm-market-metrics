# Hex Python cell 5: provider share over time - tokens and spend side by side.
# Inputs: `selected_providers` (multiselect, options = provider_options,
#         default = default_providers) and
#         `token_basis` (dropdown): "All tokens" or "Paid tokens".
token_col = "token_share" if token_basis == "All tokens" else "paid_token_share"
p = providers[providers.week_start > latest_week - pd.Timedelta(weeks=26)].copy()
p["group"] = p.provider.where(p.provider.isin(selected_providers), "All others")
p = p.groupby(["week_start", "group"], as_index=False)[[token_col, "spend_share"]].sum()

fig_providers = make_subplots(
    rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.12,
    subplot_titles=(f"Share of {token_basis.lower()}", "Share of implied spend"),
)
order = [g for g in top_providers if g in set(p.group)] + ["All others"]
for g in order:
    d = p[p.group == g]
    for col, value in ((1, token_col), (2, "spend_share")):
        fig_providers.add_trace(go.Scatter(
            x=d.week_start, y=d[value], mode="lines", name=g, legendgroup=g,
            showlegend=col == 1,
            line=dict(color=provider_styles[g][0], width=2, dash=provider_styles[g][1]),
            hovertemplate=f"{g}<br>%{{x|%Y-%m-%d}}: %{{y:.1%}}<extra></extra>",
        ), row=1, col=col)
# Direct labels at the line ends when there are few enough lines to label cleanly; labels
# that would overlap are nudged apart vertically.
if len(order) <= 4:
    last = p[p.week_start == p.week_start.max()]
    for col, value in ((1, token_col), (2, "spend_share")):
        ends = sorted(
            (float(last.loc[last.group == g, value].iloc[0]), g)
            for g in order if (last.group == g).any()
        )
        gap = 0.045 * max(p[token_col].max(), p.spend_share.max())
        placed = []
        for y, g in ends:
            y_label = max(y, placed[-1] + gap) if placed else y
            placed.append(y_label)
            fig_providers.add_annotation(
                x=f"{last.week_start.iloc[0]:%Y-%m-%d}", y=y_label, text=g,
                showarrow=False, xanchor="left", xshift=6, font=dict(size=11, color=INK_2),
                row=1, col=col,
            )
base_layout(
    fig_providers, "Who holds the tokens, and who holds the spend",
    "A provider whose spend share is above its token share sells pricier tokens. Last 26 weeks.",
    height=440,
)
fig_providers.update_layout(margin=dict(t=110, r=90))
fig_providers.update_yaxes(tickformat=".0%", rangemode="tozero")
for i, a in enumerate(fig_providers.layout.annotations[:2]):  # the two panel titles
    a.update(x=[0, 0.56][i], y=1.04, xanchor="left", yanchor="bottom",
             font=dict(color=INK_2, size=13))
fig_providers
