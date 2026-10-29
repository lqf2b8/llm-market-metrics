# Hex Python cell 5: provider share over time - tokens and spend side by side.
# Inputs: `selected_providers` (multiselect, options = provider_options) and
#         `token_basis` (dropdown): "All tokens" or "Paid tokens".
token_col = "token_share" if token_basis == "All tokens" else "paid_token_share"
p = providers[providers.week_start > latest_week - pd.Timedelta(weeks=26)].copy()
p["group"] = p.provider.where(p.provider.isin(selected_providers), "All others")
p = p.groupby(["week_start", "group"], as_index=False)[[token_col, "spend_share"]].sum()

fig_providers = make_subplots(
    rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
    subplot_titles=(f"Share of {token_basis.lower()}", "Share of implied spend"),
)
order = [g for g in top_providers if g in set(p.group)] + ["All others"]
for g in order:
    d = p[p.group == g]
    for col, value in ((1, token_col), (2, "spend_share")):
        fig_providers.add_trace(go.Scatter(
            x=d.week_start, y=d[value], mode="lines", name=g, legendgroup=g,
            showlegend=col == 1, line=dict(color=provider_colors[g], width=2),
            hovertemplate=f"{g}<br>%{{x|%Y-%m-%d}}: %{{y:.1%}}<extra></extra>",
        ), row=1, col=col)
base_layout(
    fig_providers, "Who holds the tokens, and who holds the spend",
    "A provider whose spend share is above its token share sells pricier tokens. Last 26 weeks.",
    height=440,
)
fig_providers.update_layout(margin=dict(t=110))
fig_providers.update_yaxes(tickformat=".0%", rangemode="tozero")
fig_providers.update_annotations(font=dict(color=INK_2, size=13), xanchor="left", x=None)
for i, a in enumerate(fig_providers.layout.annotations[:2]):
    a.update(x=[0, 0.52][i], y=1.04, yanchor="bottom")
fig_providers
