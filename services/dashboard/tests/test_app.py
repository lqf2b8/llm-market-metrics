from __future__ import annotations

import json

import plotly.io as pio
from conftest import synthetic_frames

from dashboard import app as dash_app
from dashboard import data


def find(component, cls_name=None, comp_id=None):
    """Every component in a Dash layout tree matching a type name or id."""
    found = []
    stack = [component]
    while stack:
        c = stack.pop()
        if (cls_name and type(c).__name__ == cls_name) or (
            comp_id and getattr(c, "id", None) == comp_id
        ):
            found.append(c)
        children = getattr(c, "children", None)
        if isinstance(children, list | tuple):
            stack.extend(children)
        elif children is not None and not isinstance(children, str):
            stack.append(children)
    return found


def use(monkeypatch, loader):
    data._cache.clear()
    monkeypatch.setattr(data, "load", loader)


def test_dashboard_page_renders_every_view(monkeypatch):
    use(monkeypatch, synthetic_frames)
    page = dash_app.dashboard_page()
    graphs = find(page, cls_name="Graph")
    assert len(graphs) == 7  # 3 sparklines, bridge, forecast, 2 provider charts
    for g in graphs:
        json.loads(pio.to_json(g.figure))  # serializable, as Dash will send it
    assert find(page, cls_name="Table")
    assert find(page, comp_id="providers")[0].value == ["anthropic", "openai", "deepseek"]


def test_callbacks_redraw_for_each_input(monkeypatch):
    use(monkeypatch, synthetic_frames)
    box = dash_app.update_forecast("Implied spend")
    assert box[0].children == "Implied spend: actual vs forecast"
    assert box[-1].figure.layout.title.text is None  # shown as HTML, not inside the chart
    title, tokens, spend = dash_app.update_share(["google"], "All tokens")
    assert title == "Share of all tokens"
    assert {t.name for t in tokens.data} == {"google", "All others"}
    assert dash_app.update_share([], "Paid tokens")[2].data  # nothing selected: "All others"


def test_a_warehouse_failure_is_shown_not_raised(monkeypatch):
    def broken():
        raise RuntimeError("no such view")

    use(monkeypatch, broken)
    page = dash_app.dashboard_page()
    assert "no such view" in str(page)


def test_frames_are_cached_between_requests(monkeypatch):
    calls = []

    def counting():
        calls.append(1)
        return synthetic_frames()

    use(monkeypatch, counting)
    data.load_cached(now=0)
    data.load_cached(now=100)
    data.load_cached(now=data.CACHE_SECONDS + 1)
    assert len(calls) == 2


def test_router_serves_each_view_and_marks_it_in_the_nav(monkeypatch):
    use(monkeypatch, synthetic_frames)
    nav, page = dash_app.route("/datastudio")
    iframe = find(page, cls_name="Iframe")[0]
    assert iframe.src.startswith("https://datastudio.google.com/embed/reporting/")
    active = [link for link in find(nav, cls_name="Link") if "active" in link.className]
    assert [link.children for link in active] == ["Data Studio"]
    nav, page = dash_app.route("/no-such-page")  # unknown paths fall back to the dashboard
    assert len(find(page, cls_name="Graph")) == 7
    assert {a.children for a in find(nav, cls_name="A")} == {"GitHub", "API docs", "Weekly memos"}


def test_shell_layout_needs_no_warehouse(monkeypatch):
    def broken():
        raise AssertionError("the shell must not query the warehouse")

    use(monkeypatch, broken)
    assert find(dash_app.layout(), comp_id="page")
