"""Reject a memo that contains any number not present in its facts file.

Every numeric token in the draft (money, percentages, token counts, dates, plain counts)
must match a number that appears somewhere in the facts. Signs are ignored, so "fell
$7.1M" is accepted for a fact of "-$7.1M". This is deliberately strict: rounding, adding
two facts together or restating a percentage differently all fail, and a person fixes it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

NUMBER = re.compile(
    r"""
    (?<![\w.])                     # not inside a word or another number
    [-+−]?\$?                      # optional sign and dollar sign
    \d[\d,]*(?:\.\d+)?             # digits, thousands separators, decimals
    (?:\s?(?:%|pp|[KMBT])\b|%)?    # optional unit
    """,
    re.VERBOSE,
)
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

# Numbers that are part of the vocabulary rather than data.
ALLOWED_WORDS = {"50"}  # "top 50"


def normalize(token: str) -> str:
    token = token.strip().replace("−", "-").replace(",", "").replace(" ", "")
    return token.lstrip("+-")


def numbers_in(text: str) -> list[str]:
    without_dates = DATE.sub(" ", text)
    return [normalize(m.group(0)) for m in NUMBER.finditer(without_dates)]


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)
    elif value is not None and not isinstance(value, bool):
        yield str(value)


def allowed_numbers(facts: dict[str, Any]) -> set[str]:
    allowed = set(ALLOWED_WORDS)
    for text in _strings(facts):
        allowed.update(numbers_in(text))
        # "$0.26 per million tokens" also allows "0.26" and "$0.26".
        for n in numbers_in(text):
            allowed.add(n.lstrip("$"))
    return allowed


def dates_in(text: str) -> set[str]:
    return set(DATE.findall(text))


def check(draft: str, facts: dict[str, Any]) -> list[str]:
    """Return one problem per number or date in the draft that the facts do not contain."""
    # Markdown list markers ("1. ") are structure, not data.
    draft = re.sub(r"(?m)^\s*\d+[.)]\s", "", draft)
    allowed = allowed_numbers(facts)
    fact_dates = set().union(*(dates_in(s) for s in _strings(facts)))
    problems = []
    for n in numbers_in(draft):
        if n not in allowed and n.lstrip("$") not in allowed:
            problems.append(f"number not in facts: {n}")
    for d in sorted(dates_in(draft) - fact_dates):
        problems.append(f"date not in facts: {d}")
    return problems


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft")
    parser.add_argument("facts")
    args = parser.parse_args()
    with open(args.draft, encoding="utf-8") as fh:
        draft = fh.read()
    with open(args.facts, encoding="utf-8") as fh:
        facts = json.load(fh)
    problems = check(draft, facts)
    for p in problems:
        print(p)
    print("ok" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
