# Hex Python cell 4: actual vs the forecast frozen a week earlier, last 12 weeks + next week.
# Input `forecast_metric` (dropdown): "Tokens" or "Implied spend".
metric = {"Tokens": "tokens", "Implied spend": "implied_spend_usd"}[forecast_metric]
fmt = tokens_fmt if metric == "tokens" else money
f = forecasts[forecasts.metric == metric].sort_values("target_week")
f = f[f.target_week > latest_week - pd.Timedelta(weeks=12)]
scored = f[f.actual.notna() & f.lower_bound.notna()]
inside = int(((scored.actual >= scored.lower_bound) & (scored.actual <= scored.upper_bound)).sum())

fig_forecast = go.Figure()
banded = f[f.lower_bound.notna()]
fig_forecast.add_trace(go.Scatter(
    x=list(banded.target_week) + list(banded.target_week[::-1]),
    y=list(banded.upper_bound) + list(banded.lower_bound[::-1]),
    fill="toself", fillcolor=BAND, line=dict(width=0), hoverinfo="skip",
    name=f"{banded.interval_level.iloc[0]:.0%} range" if len(banded) else "range",
))
fig_forecast.add_trace(go.Scatter(
    x=f.target_week, y=f.point, mode="lines+markers", name="Forecast, frozen a week earlier",
    line=dict(color=SERIES[0], width=2, dash="dash"), marker=dict(size=8, color=SERIES[0]),
    customdata=[[fmt(p), fmt(lo) if pd.notna(lo) else "n/a", fmt(hi) if pd.notna(hi) else "n/a"]
                for p, lo, hi in zip(f.point, f.lower_bound, f.upper_bound)],
    hovertemplate="Week of %{x|%Y-%m-%d}<br>Forecast %{customdata[0]}"
                  " (range %{customdata[1]} to %{customdata[2]})<extra></extra>",
))
actual = f[f.actual.notna()]
fig_forecast.add_trace(go.Scatter(
    x=actual.target_week, y=actual.actual, mode="lines+markers", name="Actual",
    line=dict(color=INK, width=2), marker=dict(size=8, color=INK, line=dict(color=SURFACE, width=2)),
    customdata=[fmt(v) for v in actual.actual],
    hovertemplate="Week of %{x|%Y-%m-%d}<br>Actual %{customdata}<extra></extra>",
))
nxt = f[f.actual.isna()]
if len(nxt):
    n = nxt.iloc[-1]
    fig_forecast.add_annotation(
        x=n.target_week, y=n.point, text=f"Next: {fmt(n.point)}", showarrow=False,
        xanchor="left", xshift=10, font=dict(color=INK_2),
    )
base_layout(
    fig_forecast, f"{forecast_metric}: actual vs forecast",
    f"Actuals landed inside the forecast range in {inside} of {len(scored)} weeks. "
    "Forecasts are frozen when made and never revised.",
)
fig_forecast.update_yaxes(tickformat="~s", tickprefix="$" if metric != "tokens" else "")
fig_forecast
