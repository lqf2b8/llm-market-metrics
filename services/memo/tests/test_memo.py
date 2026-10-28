from __future__ import annotations

import json
from pathlib import Path

import pytest

from memo import formatting as fmt
from memo.check_numbers import check, numbers_in
from memo.draft import render_prompt, write_memo
from memo.facts import assemble

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / f"api_{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def facts():
    return assemble(
        load("as-of"), load("kpis"), load("kpis_history"), load("providers"), load("bridge")
    )


def test_formatting():
    assert fmt.money(176_891_185.3) == "$176.9M"
    assert fmt.money(-7_126_943.5) == "-$7.1M"
    assert fmt.signed_money(17_809_072) == "+$17.8M"
    assert fmt.money(1.25e9) == "$1.2B"
    assert fmt.tokens(188_039_304_051_712) == "188.0T"
    assert fmt.pct(0.13317) == "13.3%"
    assert fmt.signed_pct(0.112) == "+11.2%"
    assert fmt.signed_pct(-0.05) == "-5.0%"
    assert fmt.points(0.396) == "+39.6 pp"
    assert fmt.pct(None) is None


def test_facts_from_real_api_responses(facts):
    assert facts["week_start"] == "2026-10-19"
    assert facts["headline"]["implied_spend"] == "$176.9M"
    assert facts["spend_bridge"]["change"] == "+$17.8M"
    assert facts["spend_bridge"]["volume_effect"] == "+$24.9M"
    assert facts["spend_bridge"]["mix_effect"] == "-$7.1M"
    assert facts["providers_by_spend"][0]["provider"] == "anthropic"
    assert all(p["provider"] != "other" for p in facts["providers_by_spend"])
    assert len(facts["recent_weeks"]) == 8
    assert facts["recent_weeks"][-1]["week_start"] == "2026-10-19"


def test_numbers_in_extracts_units_and_signs():
    assert numbers_in("Spend rose +$17.8M (+11.2%) to $176.9M on 188.0T tokens; gap +39.6 pp") == [
        "$17.8M",
        "11.2%",
        "$176.9M",
        "188.0T",
        "39.6pp",
    ]


def test_check_accepts_numbers_copied_from_facts(facts):
    draft = (
        "Implied spend rose +$17.8M to $176.9M in the week of 2026-10-19. Volume added +$24.9M "
        "and mix took away $7.1M. Anthropic held 49.2% of spend on 9.6% of paid tokens. "
        "Models in the top 50 are tracked daily."
    )
    assert check(draft, facts) == []


def test_check_rejects_invented_rounded_or_derived_numbers(facts):
    draft = "Spend rose about $18M, roughly 11%, and Anthropic grew 3x. Volume was +$24.9M."
    problems = check(draft, facts)
    assert "number not in facts: $18M" in problems
    assert "number not in facts: 11%" in problems
    assert "number not in facts: 3" in problems
    assert not any("24.9" in p for p in problems)


def test_check_rejects_dates_not_in_facts(facts):
    assert check("Compared with 2026-09-01, spend rose.", facts) == [
        "date not in facts: 2026-09-01"
    ]


def test_check_ignores_list_markers(facts):
    assert check("1. Spend rose +$17.8M.\n2. Volume added +$24.9M.", facts) == []


def test_prompt_embeds_the_facts(facts):
    prompt = render_prompt(facts)
    assert '"implied_spend": "$176.9M"' in prompt
    assert "{facts}" not in prompt


class FakeDrafter:
    model = "fake-model"

    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    def draft(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.text


def test_write_memo_saves_a_checked_draft(tmp_path, facts):
    path, problems = write_memo(facts, FakeDrafter("## Headline\nSpend rose +$17.8M."), tmp_path)
    assert problems == []
    assert path.name == "2026-10-19.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\nweek_start: 2026-10-19")
    assert "drafted_by: fake-model" in text
    assert (
        json.loads((tmp_path / "facts" / "2026-10-19.json").read_text())["week_start"]
        == "2026-10-19"
    )


def test_write_memo_quarantines_a_draft_that_fails_the_check(tmp_path, facts):
    path, problems = write_memo(facts, FakeDrafter("Spend rose about $18M."), tmp_path)
    assert problems == ["number not in facts: $18M"]
    assert path.name == "2026-10-19.REJECTED.md"
    assert not (tmp_path / "2026-10-19.md").exists()
    assert "Number check failed" in path.read_text(encoding="utf-8")
