from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from memo import formatting as fmt
from memo.check_numbers import REQUIRED_SECTIONS, check, numbers_in
from memo.draft import ClaudeDrafter, IncompleteDraftError, render_prompt, write_memo
from memo.facts import assemble

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / f"api_{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def facts():
    return assemble(
        load("as-of"), load("kpis"), load("kpis_history"), load("providers"), load("bridge")
    )


def complete(body: str, facts) -> str:
    """Wrap a body in every required section plus the source line."""
    sections = "\n\n".join(f"{s}\nText." for s in REQUIRED_SECTIONS[1:])
    return f"{REQUIRED_SECTIONS[0]}\n{body}\n\n{sections}\n\n{facts['source']}"


def number_problems(draft: str, facts) -> list[str]:
    return check(complete(draft, facts), facts)


# --- formatting -------------------------------------------------------------------


def test_formatting():
    assert fmt.money(176_891_185.3) == "$176.9M"
    assert fmt.money(-7_126_943.5) == "-$7.1M"
    assert fmt.signed_money(17_809_072) == "+$17.8M"
    assert fmt.signed_money(-7_126_943.5) == "-$7.1M"
    assert fmt.money(1.25e9) == "$1.2B"
    assert fmt.tokens(188_039_304_051_712) == "188.0T"
    assert fmt.pct(0.13317) == "13.3%"
    assert fmt.signed_pct(0.112) == "+11.2%"
    assert fmt.signed_pct(-0.05) == "-5.0%"
    assert fmt.points(0.396) == "+39.6 pp"
    assert fmt.pct(None) is None


def test_rounding_noise_is_zero_without_a_sign():
    # The first real memo showed "+$0" and "-$0" for float noise in price effects.
    assert fmt.signed_money(1.6e-9) == "$0"
    assert fmt.signed_money(-2e-9) == "$0"
    assert fmt.money(0.3) == "$0"


# --- facts ------------------------------------------------------------------------


def test_facts_from_real_api_responses(facts):
    assert facts["week_start"] == "2026-10-19"
    assert facts["headline"]["implied_spend"] == "$176.9M"
    assert facts["spend_bridge"]["change"] == "+$17.8M"
    assert facts["spend_bridge"]["volume_effect"] == "+$24.9M"
    assert facts["spend_bridge"]["mix_effect"] == "-$7.1M"
    assert facts["spend_bridge"]["price_effect"] == "$0"
    assert facts["providers_by_spend"][0]["provider"] == "anthropic"
    assert all(p["provider"] != "other" for p in facts["providers_by_spend"])
    assert len(facts["recent_weeks"]) == 8
    assert facts["recent_weeks"][-1]["week_start"] == "2026-10-19"


def test_prompt_embeds_the_facts(facts):
    prompt = render_prompt(facts)
    assert '"implied_spend": "$176.9M"' in prompt
    assert "{facts}" not in prompt


# --- number check -----------------------------------------------------------------


def test_numbers_in_extracts_units_and_signs():
    text = "Spend rose +$17.8M (+11.2%) to $176.9M on 188.0T tokens; gap +39.6 pp"
    assert numbers_in(text) == ["$17.8M", "11.2%", "$176.9M", "188.0T", "39.6pp"]


def test_check_accepts_numbers_copied_from_facts(facts):
    draft = (
        "Implied spend rose +$17.8M to $176.9M in the week of 2026-10-19. Volume contributed "
        "+$24.9M and mix contributed -$7.1M. Anthropic held 49.2% of spend on 9.6% of paid "
        "tokens. Models in the top 50 are tracked daily."
    )
    assert number_problems(draft, facts) == []


def test_check_rejects_invented_rounded_or_derived_numbers(facts):
    draft = "Spend rose about $18M, roughly 11%, and Anthropic grew 3x. Volume was +$24.9M."
    problems = number_problems(draft, facts)
    assert "number not in facts: $18M" in problems
    assert "number not in facts: 11%" in problems
    assert "number not in facts: 3" in problems
    assert not any("24.9" in p for p in problems)


def test_check_rejects_dates_not_in_facts(facts):
    assert number_problems("Compared with 2026-09-01, spend rose.", facts) == [
        "date not in facts: 2026-09-01"
    ]


def test_check_rejects_numbers_written_as_words(facts):
    problems = number_problems("Four models entered the top 50, and spend doubled.", facts)
    assert problems == ["number written as a word: Four"]


def test_check_ignores_list_markers(facts):
    assert number_problems("1. Spend rose +$17.8M.\n2. Volume added +$24.9M.", facts) == []


def test_check_requires_every_section_and_the_source_line(facts):
    problems = check("## Headline\nSpend rose +$17.8M.", facts)
    assert "missing section: ## Data notes" in problems
    assert "missing the source line" in problems


def test_first_real_memo_is_rejected_for_the_right_reasons():
    """Regression: the first memo drafted by the live model, 2026-10-28. It was cut off
    mid-sentence and spelled out a count, and the old check passed it anyway."""
    memo = (FIXTURES / "first_real_memo_2026-10-19.md").read_text(encoding="utf-8")
    body = memo.split("---", 2)[2]  # the checker sees only the model's text
    facts = json.loads(
        (FIXTURES / "first_real_memo_facts_2026-10-19.json").read_text(encoding="utf-8")
    )
    problems = check(body, facts)
    assert "missing the source line" in problems
    assert "number written as a word: Four" in problems
    assert not any(p.startswith("number not in facts") for p in problems)


# --- drafting ---------------------------------------------------------------------


class FakeDrafter:
    model = "fake-model"

    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    def draft(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.text


def fake_client(stop_reason: str, text: str = "## Headline\nok"):
    message = SimpleNamespace(
        stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)]
    )
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **_: message))


def test_drafter_returns_text_when_the_model_finishes():
    assert ClaudeDrafter(client=fake_client("end_turn")).draft("p") == "## Headline\nok"


def test_drafter_refuses_a_truncated_response():
    with pytest.raises(IncompleteDraftError, match="max_tokens"):
        ClaudeDrafter(client=fake_client("max_tokens")).draft("p")


def test_write_memo_saves_a_checked_draft(tmp_path, facts):
    draft = complete("Spend rose +$17.8M.", facts)
    path, problems = write_memo(facts, FakeDrafter(draft), tmp_path)
    assert problems == []
    assert path.name == "2026-10-19.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\nweek_start: 2026-10-19")
    assert "drafted_by: fake-model" in text
    saved_facts = json.loads((tmp_path / "facts" / "2026-10-19.json").read_text())
    assert saved_facts["week_start"] == "2026-10-19"


def test_write_memo_quarantines_a_draft_that_fails_the_check(tmp_path, facts):
    draft = complete("Spend rose about $18M.", facts)
    path, problems = write_memo(facts, FakeDrafter(draft), tmp_path)
    assert problems == ["number not in facts: $18M"]
    assert path.name == "2026-10-19.REJECTED.md"
    assert not (tmp_path / "2026-10-19.md").exists()
    assert "Number check failed" in path.read_text(encoding="utf-8")
