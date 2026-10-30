"""The project's front door: the weekly metrics review as a Plotly Dash app, with a toggle to
the same views in Google Data Studio and links to the code, the API and the latest memo.

    python -m dashboard.app                      # local, http://localhost:8050
    gunicorn dashboard.app:server                # what the container runs

    /             the Dash dashboard
    /datastudio   the Data Studio report, embedded

Reads only the governed `metrics` views (DuckDB locally, BigQuery in production), so every
number matches the API, the memo and the Data Studio report.
"""

from __future__ import annotations

import os

from dash import Dash, Input, Output, callback, dcc, html

from dashboard import charts, data

REPO = "https://github.com/lqf2b8/llm-market-metrics"
MEMOS = f"{REPO}/tree/main/memos"
API_DOCS = os.environ.get("API_DOCS_URL", "http://localhost:8080/docs")
DATASTUDIO_REPORT = os.environ.get("DATASTUDIO_REPORT_ID", "9eaf6a67-8c9b-44df-bece-b5aaf7d1e203")
DATASTUDIO_PAGE = os.environ.get("DATASTUDIO_PAGE_ID", "tEnnC")
DATASTUDIO_URL = f"https://datastudio.google.com/reporting/{DATASTUDIO_REPORT}"
DATASTUDIO_EMBED = (
    f"https://datastudio.google.com/embed/reporting/{DATASTUDIO_REPORT}/page/{DATASTUDIO_PAGE}"
)
VIEWS = {"/": "Dash", "/datastudio": "Data Studio"}
SOURCE = "Source: OpenRouter (openrouter.ai/rankings), CC BY 4.0"
FONTS = (
    "https://fonts.googleapis.com/css2?family=Lora:wght@400;600"
    "&family=Poppins:wght@500;600;700&display=swap"
)
GRAPH = {"displayModeBar": False, "responsive": True}

app = Dash(
    __name__,
    title="LLM API Market Metrics",
    external_stylesheets=[FONTS],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    # Page bodies are swapped in by the router, so their controls are not in the first layout.
    suppress_callback_exceptions=True,
)
server = app.server


def current() -> charts.Data:
    return charts.Data.from_frames(data.load_cached())


def graph(fig, graph_id: str | None = None) -> dcc.Graph:
    kwargs = {"id": graph_id} if graph_id else {}
    height = fig.layout.height or 380
    return dcc.Graph(
        figure=fig, config=GRAPH, className="chart", style={"height": f"{height}px"}, **kwargs
    )


def untitled(fig):
    """The figure without its Plotly title: the page shows it as an HTML heading instead."""
    top = 16 if fig.layout.meta and fig.layout.meta.get("title") else fig.layout.margin.t
    return fig.update_layout(title=None, margin=dict(t=top))


def titled(fig, graph_id: str | None = None, level=html.H2) -> list:
    meta = fig.layout.meta or {}
    parts = []
    if meta.get("title"):
        ids = {"id": f"{graph_id}-title"} if graph_id else {}
        parts.append(level(meta["title"], **ids))
    if meta.get("subtitle"):
        parts.append(html.P(meta["subtitle"], className="note"))
    return parts + [graph(untitled(fig), graph_id)]


def money_cell(v: float) -> html.Td:
    text = charts.money(v)
    if v > 0 and text != "$0":
        text = "+" + text
    return html.Td(text, className="num")


def moves_table(d: charts.Data) -> html.Table:
    head = ["Provider", "Change", "Volume", "Mix", "Price"]
    rows = [
        html.Tr(
            [html.Td(r.provider)]
            + [
                money_cell(getattr(r, c))
                for c in (
                    "spend_change_usd",
                    "volume_effect_usd",
                    "mix_effect_usd",
                    "price_effect_usd",
                )
            ]
        )
        for r in d.bridge_providers.head(8).itertuples()
    ]
    return html.Table(
        [html.Thead(html.Tr([html.Th(h) for h in head])), html.Tbody(rows)], className="moves"
    )


def headline_section(d: charts.Data) -> html.Section:
    tiles, note = charts.headline(d)
    cards = [
        html.Div(
            [
                html.P(t.name, className="tile-name"),
                html.P(t.value, className="tile-value"),
                html.P(t.delta, className="tile-delta"),
                graph(t.sparkline),
            ],
            className="tile",
        )
        for t in tiles
    ]
    children = [html.Div(cards, className="tiles")]
    if note:
        children.append(html.P(note, className="note"))
    return html.Section(children, className="card")


def nav(pathname: str) -> html.Nav:
    """View toggle on the left, links on the right; the current view is marked."""
    toggle = [
        dcc.Link(
            label,
            href=path,
            className="view active" if path == pathname else "view",
            title=f"Show the {label} view",
        )
        for path, label in VIEWS.items()
    ]
    links = [
        html.A("GitHub", href=REPO, target="_blank", rel="noopener"),
        html.A("API docs", href=API_DOCS, target="_blank", rel="noopener"),
        html.A("Weekly memos", href=MEMOS, target="_blank", rel="noopener"),
    ]
    return html.Nav(
        [
            html.Span("LLM API Market Metrics", className="brand"),
            html.Div(toggle, className="views", role="group", **{"aria-label": "Dashboard"}),
            html.Div(links, className="links"),
        ],
        className="topnav",
    )


def datastudio_page() -> html.Main:
    return html.Main(
        [
            html.Header(
                [
                    html.H1("LLM API Market: Weekly Metrics Review"),
                    html.P(
                        [
                            "The same governed views in Google Data Studio, read live from "
                            "BigQuery. ",
                            html.A(
                                "Open in Data Studio",
                                href=DATASTUDIO_URL,
                                target="_blank",
                                rel="noopener",
                            ),
                            " if the embed does not load.",
                        ],
                        className="meta",
                    ),
                ]
            ),
            html.Iframe(
                src=DATASTUDIO_EMBED,
                title="LLM API Market Metrics in Google Data Studio",
                className="embed",
                allow="fullscreen",
            ),
        ],
        className="page",
    )


def layout() -> html.Div:
    return html.Div(
        [
            dcc.Location(id="url"),
            html.Div(nav("/"), id="nav"),
            html.Div(id="page"),
        ]
    )


@callback(Output("nav", "children"), Output("page", "children"), Input("url", "pathname"))
def route(pathname: str | None):
    path = pathname if pathname in VIEWS else "/"
    page = datastudio_page() if path == "/datastudio" else dashboard_page()
    return nav(path), page


def dashboard_page() -> html.Main:
    """Built on every page load, so a new pipeline run shows without a restart."""
    try:
        d = current()
    except Exception as err:  # noqa: BLE001 - show any warehouse failure plainly
        return html.Main(
            [
                html.H1("LLM API Market: Weekly Metrics Review"),
                html.P(f"Could not read the metrics views: {err}", className="error"),
            ],
            className="page",
        )
    share_tokens, share_spend = charts.providers(d, d.default_providers, "Paid tokens")
    return html.Main(
        [
            html.Header(
                [
                    html.H1("LLM API Market: Weekly Metrics Review"),
                    html.P(
                        [
                            f"Week of {d.latest_week:%Y-%m-%d} · data through "
                            f"{d.data_through:%Y-%m-%d} · ",
                            html.A("code on GitHub", href=REPO),
                        ],
                        className="meta",
                    ),
                    html.P(
                        [
                            "Usage across the top 50 models on OpenRouter, priced at list prices. ",
                            html.Strong("Implied spend is an index, not anyone's revenue"),
                            ": tokens × list price, with an assumed 75% prompt / 25% "
                            "completion split.",
                        ],
                        className="intro",
                    ),
                ]
            ),
            headline_section(d),
            html.Section(
                [
                    html.Div(titled(charts.bridge(d)), className="wide"),
                    html.Div(
                        [
                            html.H2("Largest provider moves"),
                            html.Div(moves_table(d), className="table-wrap"),
                        ],
                        className="narrow",
                    ),
                ],
                className="card row",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Label("Forecast for", htmlFor="metric"),
                            dcc.RadioItems(
                                id="metric",
                                options=list(charts.FORECAST_METRICS),
                                value="Tokens",
                                className="segmented",
                                inline=True,
                            ),
                        ],
                        className="controls",
                    ),
                    html.Div(titled(charts.forecast(d, "Tokens"), "forecast"), id="forecast-box"),
                ],
                className="card",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Providers", htmlFor="providers"),
                                    dcc.Dropdown(
                                        id="providers",
                                        options=d.top_providers,
                                        value=d.default_providers,
                                        multi=True,
                                        clearable=False,
                                    ),
                                ],
                                className="grow",
                            ),
                            html.Div(
                                [
                                    html.Label("Token basis", htmlFor="basis"),
                                    dcc.RadioItems(
                                        id="basis",
                                        options=list(charts.TOKEN_BASES),
                                        value="Paid tokens",
                                        className="segmented",
                                        inline=True,
                                    ),
                                ]
                            ),
                        ],
                        className="controls",
                    ),
                    html.H2("Who holds the tokens, and who holds the spend"),
                    html.P(
                        "A provider whose spend share is above its token share sells pricier "
                        "tokens. Last 26 weeks.",
                        className="note",
                    ),
                    html.Div(
                        [
                            html.Div(titled(share_tokens, "share-tokens", html.H3)),
                            html.Div(titled(share_spend, "share-spend", html.H3)),
                        ],
                        className="pair",
                    ),
                ],
                className="card",
            ),
            html.Footer(
                [
                    html.P(
                        "OpenRouter is one marketplace, not the whole market. Token counts "
                        "use each provider's tokenizer and are not strictly comparable. Spend "
                        "trends use only weeks where at least 90% of top-50 tokens are priced. "
                        "Every number is read from the governed metrics views, the same ones "
                        "the API and the weekly memo use."
                    ),
                    html.P(
                        f"{SOURCE}. An independent project, not affiliated with Anthropic or "
                        "OpenRouter."
                    ),
                ]
            ),
        ],
        className="page",
    )


app.layout = layout


@callback(Output("forecast-box", "children"), Input("metric", "value"))
def update_forecast(metric: str):
    return titled(charts.forecast(current(), metric or "Tokens"), "forecast")


@callback(
    Output("share-tokens-title", "children"),
    Output("share-tokens", "figure"),
    Output("share-spend", "figure"),
    Input("providers", "value"),
    Input("basis", "value"),
)
def update_share(selected: list[str], basis: str):
    tokens, spend = charts.providers(current(), selected or [], basis or "Paid tokens")
    return tokens.layout.meta["title"], untitled(tokens), untitled(spend)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8050")), debug=False)
