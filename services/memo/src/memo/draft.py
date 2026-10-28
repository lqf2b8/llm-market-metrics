"""Draft the weekly memo with Claude, check every number against the facts, and save both.

    python -m memo.draft                    # latest complete week
    python -m memo.draft --week 2026-10-19

Writes memos/<week>.md (draft, with front matter) and memos/facts/<week>.json. Exits
non-zero, and writes the draft as memos/<week>.REJECTED.md instead, if the number check
finds anything the facts do not contain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Protocol

from .check_numbers import check
from .facts import MetricsApi, build_facts

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 2000


class Drafter(Protocol):
    model: str

    def draft(self, prompt: str) -> str: ...


class ClaudeDrafter:
    def __init__(self, model: str = DEFAULT_MODEL, client: Any = None) -> None:
        if client is None:
            from anthropic import Anthropic

            client = Anthropic()  # reads ANTHROPIC_API_KEY
        self.client = client
        self.model = model

    def draft(self, prompt: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in message.content if block.type == "text").strip()


def render_prompt(facts: dict[str, Any]) -> str:
    template = resources.files("memo").joinpath("prompt.md").read_text(encoding="utf-8")
    return template.replace("{facts}", json.dumps(facts, indent=2, default=str))


def front_matter(facts: dict[str, Any], model: str, facts_sha: str) -> str:
    return (
        "---\n"
        f"week_start: {facts['week_start']}\n"
        f"data_through: {facts['data_through_date']}\n"
        f"drafted_by: {model}\n"
        f"drafted_at: {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"facts_sha256: {facts_sha}\n"
        "status: draft, awaiting analyst review\n"
        "---\n\n"
    )


def write_memo(facts: dict[str, Any], drafter: Drafter, out_dir: Path) -> tuple[Path, list[str]]:
    week = facts["week_start"]
    facts_json = json.dumps(facts, indent=2, sort_keys=True, default=str)
    facts_sha = hashlib.sha256(facts_json.encode()).hexdigest()[:16]
    (out_dir / "facts").mkdir(parents=True, exist_ok=True)
    (out_dir / "facts" / f"{week}.json").write_text(facts_json + "\n", encoding="utf-8")

    body = drafter.draft(render_prompt(facts))
    problems = check(body, facts)
    name = f"{week}.md" if not problems else f"{week}.REJECTED.md"
    path = out_dir / name
    text = (
        front_matter(facts, drafter.model, facts_sha)
        + f"# Weekly metrics review: week of {week}\n\n"
        + body
        + "\n"
    )
    if problems:
        text += "\n<!-- Number check failed:\n" + "\n".join(problems) + "\n-->\n"
    path.write_text(text, encoding="utf-8")
    return path, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memo")
    parser.add_argument("--week", help="Monday of the week (default: latest complete week)")
    parser.add_argument(
        "--api-url", default=os.environ.get("METRICS_API_URL", "http://localhost:8080")
    )
    parser.add_argument("--out-dir", default=os.environ.get("MEMO_DIR", "memos"))
    parser.add_argument("--model", default=os.environ.get("MEMO_MODEL", DEFAULT_MODEL))
    args = parser.parse_args(argv)

    facts = build_facts(MetricsApi(args.api_url), args.week)
    path, problems = write_memo(facts, ClaudeDrafter(args.model), Path(args.out_dir))
    if problems:
        print(f"Number check failed ({len(problems)}); draft saved to {path}", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    print(f"Memo drafted and checked: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
