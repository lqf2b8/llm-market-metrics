from __future__ import annotations

import os

import pytest

from dashboard import charts, data


def annotations(fig):
    return [a.text for a in fig.layout.annotations]


def test_formatting():
    assert charts.money(176_891_185) == "$176.9M"
    assert charts.money(-7_126_943) == "-$7.1M"
    assert charts.money(1e-9) == "$0"
    assert charts.tokens_fmt(188_039_304_051_712) == "188.0T"


def test_provider_styles_follow_spend_rank_and_stay_fixed(frames):
    d = charts.Data.from_frames(frames)
    assert d.top_providers[:3] == ["anthropic", "openai", "deepseek"]
    assert "other" not in d.top_providers
    assert d.provider_styles["anthropic"] == (charts.ORANGE, "solid")
    # Selecting a different set does not repaint a provider.
    fig, _ = charts.providers(d, ["openai"], "All tokens")
    openai = next(t for t in fig.data if t.name == "openai")
    assert openai.line.color == charts.BLUE


def test_headline_shows_value_and_change(frames):
    tiles, note = charts.headline(charts.Data.from_frames(frames))
    assert [t.name for t in tiles] == ["Tokens", "Implied spend", "Effective paid price"]
    assert all("vs prior week" in t.delta for t in tiles)
    assert note is None


def test_bridge_reads_left_to_right_and_hides_float_noise(frames):
    fig = charts.bridge(charts.Data.from_frames(frames))
    w = fig.data[0]
    assert list(w.x) == ["Prior week", "Volume", "Mix", "Price", "This week"]
    assert list(w.text) == ["$159.1M", "+$24.9M", "-$7.1M", "$0", "$176.9M"]
    assert "rose $17.8M" in fig.layout.title.text


def test_forecast_counts_only_weeks_with_an_interval_and_an_actual(frames):
    fig = charts.forecast(charts.Data.from_frames(frames), "Tokens")
    assert "inside the forecast range in" in fig.layout.title.text
    assert any(a.startswith("Next: ") for a in annotations(fig))


def test_providers_labels_line_ends_without_overlap_on_one_scale(frames):
    d = charts.Data.from_frames(frames)
    figs = charts.providers(d, d.default_providers, "Paid tokens")
    assert figs[0].layout.yaxis.range == figs[1].layout.yaxis.range
    for fig in figs:
        ys = sorted(a.y for a in fig.layout.annotations)
        assert len(ys) == 4  # 3 providers + All others
        assert all(b - a > 0.01 for a, b in zip(ys, ys[1:], strict=False))


@pytest.mark.skipif(not os.environ.get("DASHBOARD_DUCKDB_PATH"), reason="no warehouse")
def test_every_view_renders_from_a_real_warehouse():
    d = charts.Data.from_frames(data.load_duckdb(os.environ["DASHBOARD_DUCKDB_PATH"]))
    charts.headline(d)
    charts.bridge(d)
    for label in charts.FORECAST_METRICS:
        charts.forecast(d, label)
    for basis in charts.TOKEN_BASES:
        charts.providers(d, d.default_providers, basis)
