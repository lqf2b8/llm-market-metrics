"""The four views, as Plotly figures built from the dataframes in data.py.

Styled with Anthropic's published brand guidelines (github.com/anthropics/skills,
brand-guidelines). The blue and green accents are used one step darker so lines clear 3:1
contrast on the light surface. Orange and green are hard to tell apart with red-green
colorblindness, so provider lines also differ by dash pattern and carry direct labels.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

SURFACE = "#faf9f5"  # brand Light
INK, INK_2, MUTED = "#141413", "#5e5d58", "#87867f"  # brand Dark, then grays toward Mid Gray
GRID, AXIS = "#e8e6dc", "#b0aea5"  # brand Light Gray, Mid Gray
ORANGE, BLUE, GREEN = "#d97757", "#4f7fae", "#5f7a3f"
UP, DOWN = BLUE, ORANGE  # bridge: increase / decrease
BAND = "#dbe6f1"  # blue tint for the forecast interval
HEADING_FONT = "Poppins, Arial, sans-serif"
BODY_FONT = "Lora, Georgia, serif"
STYLES = [(c, d) for d in ("solid", "dash", "dot") for c in (ORANGE, BLUE, GREEN)]
FORECAST_METRICS = {"Tokens": "tokens", "Implied spend": "implied_spend_usd"}
TOKEN_BASES = {"Paid tokens": "paid_token_share", "All tokens": "token_share"}


def money(v: float) -> str:
    if abs(v) < 0.5:
        return "$0"
    for t, s in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= t:
            return f"{'-' if v < 0 else ''}${abs(v) / t:.1f}{s}"
    return f"${v:,.0f}"


def tokens_fmt(v: float) -> str:
    for t, s in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(v) >= t:
            return f"{v / t:.1f}{s}"
    return f"{v:,.0f}"


def _dates(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        df[c] = pd.to_datetime(df[c])
    return df


@dataclass
class Data:
    """The loaded frames, normalized, plus the fixed provider styling."""

    kpis: pd.DataFrame
    bridge: pd.DataFrame
    bridge_providers: pd.DataFrame
    forecasts: pd.DataFrame
    providers: pd.DataFrame
    latest_week: pd.Timestamp
    data_through: pd.Timestamp
    top_providers: list[str]
    provider_styles: dict[str, tuple[str, str]]

    @classmethod
    def from_frames(cls, f: dict[str, pd.DataFrame]) -> Data:
        providers = _dates(f["providers"], "week_start")
        latest_week = pd.to_datetime(f["as_of"]["latest_week"].iloc[0])
        # Styles follow the provider, not its rank in a filtered view: fixed once from the
        # latest week's spend. The top 7 get a color and dash; the rest fold into "All others".
        latest = providers[providers.week_start == latest_week].sort_values(
            "implied_spend_usd", ascending=False
        )
        top = [p for p in latest.provider if p != "other"][:7]
        styles = {p: STYLES[i] for i, p in enumerate(top)} | {"All others": (AXIS, "dot")}
        return cls(
            kpis=_dates(f["kpis"], "week_start"),
            bridge=f["bridge"],
            bridge_providers=f["bridge_providers"],
            forecasts=_dates(f["forecasts"], "origin_week", "target_week"),
            providers=providers,
            latest_week=latest_week,
            data_through=pd.to_datetime(f["as_of"]["data_through_date"].iloc[0]),
            top_providers=top,
            provider_styles=styles,
        )

    @property
    def default_providers(self) -> list[str]:
        return self.top_providers[:3]


def _layout(fig: go.Figure, title: str, subtitle: str | None = None, height: int = 380):
    text = f"<b>{title}</b>" if title else ""
    if subtitle:
        text += (
            f"<br><span style='font-size:12px;color:{INK_2};font-family:{BODY_FONT}'>"
            f"{subtitle}</span>"
        )
    fig.update_layout(
        # The plain title and subtitle also travel in meta, so a web page can show them as
        # HTML headings that wrap on narrow screens (see dashboard.app.titled).
        meta={"title": title, "subtitle": (subtitle or "").replace("<br>", " ")},
        title=dict(text=text, x=0, xanchor="left", font=dict(size=16)) if text else None,
        font=dict(family=HEADING_FONT, color=INK, size=13),
        height=height,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        margin=dict(l=8, r=16, t=72 if subtitle else 48, b=8),
        hoverlabel=dict(bgcolor="white", font=dict(color=INK, family=HEADING_FONT)),
        legend=dict(orientation="h", y=-0.12, x=0, font=dict(color=INK_2)),
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickfont=dict(color=MUTED), tickformat="%b %d")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED))
    return fig


@dataclass
class Tile:
    name: str
    value: str
    delta: str
    sparkline: go.Figure


def headline(d: Data) -> tuple[list[Tile], str | None]:
    """Tokens, implied spend and effective paid price: value, change and a 26-week sparkline.

    Returns the tiles and, when this week's spend is not reliable, a note to show with them.
    """
    recent = d.kpis[d.kpis.week_start > d.latest_week - pd.Timedelta(weeks=26)]
    now = d.kpis[d.kpis.week_start == d.latest_week].iloc[0]
    reliable = recent[recent.is_spend_reliable.astype(bool)]
    specs = [
        ("Tokens", tokens_fmt(now.tokens), now.tokens_wow_change, recent, "tokens", tokens_fmt),
        (
            "Implied spend",
            money(now.implied_spend_usd),
            now.implied_spend_wow_change,
            reliable,
            "implied_spend_usd",
            money,
        ),
        (
            "Effective paid price",
            f"${now.effective_paid_usd_per_mtok:.2f} / M tokens",
            now.effective_paid_price_wow_change,
            reliable,
            "effective_paid_usd_per_mtok",
            lambda v: f"${v:.2f}",
        ),
    ]
    tiles = []
    for name, value, change, data, col, fmt in specs:
        fig = go.Figure(
            [
                go.Scatter(
                    x=data.week_start,
                    y=data[col],
                    mode="lines",
                    line=dict(color=ORANGE, width=2),
                    customdata=[fmt(v) for v in data[col]],
                    hovertemplate="%{x|%b %d, %Y}: %{customdata}<extra></extra>",
                ),
                go.Scatter(
                    x=[data.week_start.iloc[-1]],
                    y=[data[col].iloc[-1]],
                    mode="markers",
                    marker=dict(color=ORANGE, size=8, line=dict(color=SURFACE, width=2)),
                    hoverinfo="skip",
                ),
            ]
        )
        _layout(fig, "", height=110)
        fig.update_layout(margin=dict(l=4, r=8, t=8, b=4), showlegend=False)
        fig.update_xaxes(showticklabels=False, linecolor=GRID)
        fig.update_yaxes(showticklabels=False, showgrid=False)
        if pd.isna(change):
            delta = "n/a"
        else:
            arrow = "▲" if change > 0 else "▼" if change < 0 else ""
            delta = f"{arrow} {change:+.1%} vs prior week"
        tiles.append(Tile(name, value, delta, fig))
    note = (
        None
        if now.is_spend_reliable
        else "Spend for this week is less reliable: under 90% of tokens are priced."
    )
    return tiles, note


def bridge(d: Data) -> go.Figure:
    """Why spend moved: volume, mix and price for the latest week, adding up exactly."""
    b = d.bridge.iloc[0]
    steps = [
        ("Prior week", b.prior_spend_usd, "absolute"),
        ("Volume", b.volume_effect_usd, "relative"),
        ("Mix", b.mix_effect_usd, "relative"),
        ("Price", b.price_effect_usd, "relative"),
        ("This week", b.spend_usd, "total"),
    ]

    def label(value: float, measure: str) -> str:
        text = money(value)
        return "+" + text if measure == "relative" and value > 0 and text != "$0" else text

    fig = go.Figure(
        go.Waterfall(
            x=[s[0] for s in steps],
            y=[s[1] for s in steps],
            measure=[s[2] for s in steps],
            text=[label(v, m) for _, v, m in steps],
            textposition="outside",
            textfont=dict(color=INK),
            increasing=dict(marker=dict(color=UP)),
            decreasing=dict(marker=dict(color=DOWN)),
            totals=dict(marker=dict(color=AXIS)),
            connector=dict(line=dict(color=AXIS, width=1, dash="dot")),
            hovertemplate="%{x}: %{text}<extra></extra>",
        )
    )
    change = b.spend_usd - b.prior_spend_usd
    _layout(
        fig,
        f"Implied spend {'rose' if change >= 0 else 'fell'} {money(abs(change))} "
        f"in the week of {d.latest_week:%Y-%m-%d}",
        "Volume: the market grew. Mix: traffic moved between models with different prices. "
        "Price: list prices changed.<br>Price effects start 2026-10-28, when daily price "
        "snapshots began; earlier weeks show $0 by construction.",
        height=400,
    )
    fig.update_layout(waterfallgap=0.5, showlegend=False, margin=dict(t=96))
    fig.update_yaxes(tickprefix="$", tickformat="~s", rangemode="tozero")
    return fig


def forecast(d: Data, metric_label: str) -> go.Figure:
    """Each week against the forecast frozen a week earlier: last 12 weeks plus next week."""
    metric = FORECAST_METRICS[metric_label]
    fmt = tokens_fmt if metric == "tokens" else money
    f = d.forecasts[d.forecasts.metric == metric].sort_values("target_week")
    f = f[f.target_week > d.latest_week - pd.Timedelta(weeks=12)]
    scored = f[f.actual.notna() & f.lower_bound.notna()]
    inside = int(
        ((scored.actual >= scored.lower_bound) & (scored.actual <= scored.upper_bound)).sum()
    )
    fig = go.Figure()
    banded = f[f.lower_bound.notna()]
    level = f"{banded.interval_level.iloc[0]:.0%}" if len(banded) else "90%"
    fig.add_trace(
        go.Scatter(
            x=list(banded.target_week) + list(banded.target_week[::-1]),
            y=list(banded.upper_bound) + list(banded.lower_bound[::-1]),
            fill="toself",
            fillcolor=BAND,
            line=dict(width=0),
            hoverinfo="skip",
            name=f"{level} range",
        )
    )

    def rng(lo, hi):
        return "n/a" if pd.isna(lo) else f"{fmt(lo)} to {fmt(hi)}"

    fig.add_trace(
        go.Scatter(
            x=f.target_week,
            y=f.point,
            mode="lines+markers",
            name="Forecast, frozen a week earlier",
            line=dict(color=BLUE, width=2, dash="dash"),
            marker=dict(size=8, color=BLUE),
            customdata=[
                [fmt(p), rng(lo, hi)]
                for p, lo, hi in zip(f.point, f.lower_bound, f.upper_bound, strict=True)
            ],
            hovertemplate="Week of %{x|%Y-%m-%d}<br>Forecast %{customdata[0]}"
            " (range %{customdata[1]})<extra></extra>",
        )
    )
    actual = f[f.actual.notna()]
    fig.add_trace(
        go.Scatter(
            x=actual.target_week,
            y=actual.actual,
            mode="lines+markers",
            name="Actual",
            line=dict(color=INK, width=2),
            marker=dict(size=8, color=INK, line=dict(color=SURFACE, width=2)),
            customdata=[fmt(v) for v in actual.actual],
            hovertemplate="Week of %{x|%Y-%m-%d}<br>Actual %{customdata}<extra></extra>",
        )
    )
    upcoming = f[f.actual.isna()]
    if len(upcoming):
        n = upcoming.iloc[-1]
        fig.add_annotation(
            x=n.target_week,
            y=n.point,
            text=f"Next: {fmt(n.point)}",
            showarrow=False,
            xanchor="left",
            xshift=10,
            font=dict(color=INK_2),
        )
    _layout(
        fig,
        f"{metric_label}: actual vs forecast",
        f"Actuals landed inside the forecast range in {inside} of {len(scored)} weeks. "
        "Forecasts are frozen when made and never revised.",
    )
    fig.update_yaxes(tickformat="~s", tickprefix="" if metric == "tokens" else "$")
    return fig


def providers(d: Data, selected: list[str], basis_label: str) -> tuple[go.Figure, go.Figure]:
    """Share of tokens and share of spend over the last 26 weeks, as two charts on one scale."""
    token_col = TOKEN_BASES[basis_label]
    p = d.providers[d.providers.week_start > d.latest_week - pd.Timedelta(weeks=26)].copy()
    p["group"] = p.provider.where(p.provider.isin(selected), "All others")
    p = p.groupby(["week_start", "group"], as_index=False)[[token_col, "spend_share"]].sum()
    order = [g for g in d.top_providers if g in set(p.group)] + ["All others"]
    top = 1.08 * max(p[token_col].max(), p.spend_share.max(), 0.01)
    last = p[p.week_start == p.week_start.max()]
    figs = []
    for value, title in (
        (token_col, f"Share of {basis_label.lower()}"),
        ("spend_share", "Share of implied spend"),
    ):
        fig = go.Figure()
        for g in order:
            rows = p[p.group == g]
            color, dash = d.provider_styles.get(g, (INK_2, "dashdot"))
            fig.add_trace(
                go.Scatter(
                    x=rows.week_start,
                    y=rows[value],
                    mode="lines",
                    name=g,
                    line=dict(color=color, width=2, dash=dash),
                    hovertemplate=f"{g}<br>%{{x|%Y-%m-%d}}: %{{y:.1%}}<extra></extra>",
                )
            )
        # Direct labels at the line ends when there are few enough lines to label cleanly;
        # labels that would overlap are nudged apart vertically.
        if len(order) <= 4:
            ends = sorted(
                (float(last.loc[last.group == g, value].iloc[0]), g)
                for g in order
                if (last.group == g).any()
            )
            placed: list[float] = []
            for y, g in ends:
                y_label = max(y, placed[-1] + 0.045 * top) if placed else y
                placed.append(y_label)
                fig.add_annotation(
                    x=f"{last.week_start.iloc[0]:%Y-%m-%d}",
                    y=y_label,
                    text=g,
                    showarrow=False,
                    xanchor="left",
                    xshift=6,
                    font=dict(size=11, color=INK_2),
                )
        _layout(fig, title, height=380)
        fig.update_layout(margin=dict(t=48, r=90))
        fig.update_yaxes(tickformat=".0%", range=[0, top])
        figs.append(fig)
    return figs[0], figs[1]
