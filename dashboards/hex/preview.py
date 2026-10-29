"""Run the Hex notebook's cells against a local DuckDB warehouse and save the charts.

    python dashboards/hex/preview.py --duckdb data/warehouse.duckdb --out build/hex

The SQL in sql/ is the same text pasted into Hex's SQL cells (it runs unchanged on BigQuery
and DuckDB), and the code in python/ is the same text pasted into its Python cells. This
script stands in for Hex: it names each dataframe as Hex would, sets the inputs to their
defaults, runs the cells in order and writes each figure as a standalone HTML file.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

HERE = Path(__file__).parent
DEFAULT_INPUTS = {
    "forecast_metric": "Tokens",
    "token_basis": "Paid tokens",
}


def run(db_path: str, inputs: dict | None = None) -> dict:
    con = duckdb.connect(db_path, read_only=True)
    ns: dict = {}
    for sql in sorted((HERE / "sql").glob("*.sql")):
        name = sql.stem.split("_", 1)[1]
        ns[name] = con.execute(sql.read_text()).df()
    ns.update(DEFAULT_INPUTS | (inputs or {}))
    for cell in sorted((HERE / "python").glob("*.py")):
        if cell.name.startswith("05") and "selected_providers" not in ns:
            ns["selected_providers"] = ns["default_providers"]  # the input's default
        exec(compile(cell.read_text(), str(cell), "exec"), ns)  # noqa: S102 - stands in for Hex
    return {k: v for k, v in ns.items() if k.startswith("fig_")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duckdb", default="data/warehouse.duckdb")
    parser.add_argument("--out", default="build/hex")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for metric in ("Tokens", "Implied spend"):
        figs = run(args.duckdb, {"forecast_metric": metric})
        suffix = "" if metric == "Tokens" else "_spend"
        for name, fig in figs.items():
            if suffix and name != "fig_forecast":
                continue
            stem = f"{name.removeprefix('fig_')}{suffix}"
            fig.write_html(out / f"{stem}.html", include_plotlyjs=True)
            print("wrote", out / f"{stem}.html")


if __name__ == "__main__":
    main()
