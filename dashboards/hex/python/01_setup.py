# Hex Python cell 1: shared style, formatting and provider options. Runs after the SQL cells.
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Anthropic brand palette (github.com/anthropics/skills, brand-guidelines). The blue and
# green accents are used one step darker so lines clear 3:1 contrast on the light surface;
# orange and green are hard to tell apart for red-green colorblind readers, so series also
# differ by dash pattern and carry direct labels.
SURFACE = "#faf9f5"  # brand Light
INK, INK_2, MUTED = "#141413", "#5e5d58", "#87867f"  # brand Dark, then two grays toward Mid Gray
GRID, AXIS = "#e8e6dc", "#b0aea5"  # brand Light Gray, Mid Gray
ORANGE, BLUE, GREEN = "#d97757", "#4f7fae", "#5f7a3f"
UP, DOWN = BLUE, ORANGE  # bridge: increase / decrease
BAND = "#dbe6f1"  # blue tint for the forecast interval
HEADING_FONT = "Poppins, Arial, sans-serif"
BODY_FONT = "Lora, Georgia, serif"
FONT = dict(family=HEADING_FONT, color=INK, size=13)
SOURCE = "Source: OpenRouter (openrouter.ai/rankings), CC BY 4.0"


def base_layout(fig, title, subtitle=None, height=380):
    text = f"<b>{title}</b>"
    if subtitle:
        text += (f"<br><span style='font-size:12px;color:{INK_2};font-family:{BODY_FONT}'>"
                 f"{subtitle}</span>")
    fig.update_layout(
        title=dict(text=text, x=0, xanchor="left", font=dict(size=16)),
        font=FONT, height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        margin=dict(l=8, r=16, t=72 if subtitle else 48, b=8),
        hoverlabel=dict(bgcolor="white", font=dict(color=INK)),
        legend=dict(orientation="h", y=-0.12, x=0, font=dict(color=INK_2)),
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickfont=dict(color=MUTED),
                     tickformat="%b %d")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED))
    return fig


def money(v):
    if abs(v) < 0.5:
        return "$0"
    for t, s in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= t:
            return f"{'-' if v < 0 else ''}${abs(v) / t:.1f}{s}"
    return f"${v:,.0f}"


def tokens_fmt(v):
    for t, s in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(v) >= t:
            return f"{v / t:.1f}{s}"
    return f"{v:,.0f}"


def as_dates(df, *cols):
    df = df.copy()
    for c in cols:
        df[c] = pd.to_datetime(df[c])
    return df


kpis = as_dates(kpis, "week_start")
forecasts = as_dates(forecasts, "origin_week", "target_week")
providers = as_dates(providers, "week_start")
latest_week = pd.to_datetime(as_of["latest_week"].iloc[0])
data_through = pd.to_datetime(as_of["data_through_date"].iloc[0])

# Provider styles follow the provider, not its rank in a filtered view: fixed once from the
# latest week's spend. The top 7 get a color and dash; the rest fold into "All others".
latest_spend = providers[providers.week_start == latest_week].sort_values(
    "implied_spend_usd", ascending=False
)
top_providers = [p for p in latest_spend.provider if p != "other"][:7]
STYLES = [(c, d) for d in ("solid", "dash", "dot") for c in (ORANGE, BLUE, GREEN)]
provider_styles = {p: STYLES[i] for i, p in enumerate(top_providers)} | {
    "All others": (AXIS, "dot")
}
provider_options = top_providers  # options for the provider multiselect input
default_providers = top_providers[:3]  # the multiselect's default

# For the app's markdown cells: {{ data_through_label }} and {{ latest_week_label }}
data_through_label = f"{data_through:%Y-%m-%d}"
latest_week_label = f"{latest_week:%Y-%m-%d}"
