# LLM API Market Metrics

An automated weekly metrics review of the LLM API market, built the way a finance analytics team would run one: public usage data in, governed metric definitions in dbt, a weekly memo explaining what moved and why, and two dashboards (Hex and Tableau) that read the same numbers.

> **Status: in progress.** Day 2 of 12: ingest is built, and the dbt project has staging models, a type-2 price history and data-quality tests passing on the full history (Jan 2025 onward). Marts, metrics and everything downstream are not built yet.

## What it answers each week

- **Why did spend move?** A price-volume-mix bridge splits the week-over-week change in implied spend.
- **Are we on plan?** Each Monday's forecast is frozen, then compared with actuals and its prediction interval.
- **What is about to change?** Adoption curves for newly launched models, and providers whose spend share and token share diverge.

## Architecture

Seven containerized services on Google Cloud Run, sharing one BigQuery warehouse. They pass data only through BigQuery tables and one read-only HTTP API.

| Service | Runs as | Status |
| --- | --- | --- |
| `ingest`: OpenRouter rankings and model prices to the raw layer | Cloud Run job | Built, tested |
| `transform`: dbt staging, price history, marts, metrics | Cloud Run job | Staging and price history built, tested |
| `analysis`: spend bridge, frozen forecasts | Cloud Run job | Planned |
| `export`: metrics to a Google Sheet for Tableau Public | Cloud Run job | Planned |
| `metrics-api`: read-only FastAPI over the metrics | Cloud Run service | Planned |
| `memo`: weekly memo drafted by Claude, checked against the data | Cloud Run job | Planned |
| `portal`: one page with a Hex / Tableau toggle and links | Cloud Run service | Planned |

## Run it locally

Requires Docker and an [OpenRouter API key](https://openrouter.ai/settings/keys).

```bash
cp .env.example .env                              # add OPENROUTER_API_KEY
docker compose run --rm ingest probe              # day-1 checks: shape, prices, slug join
docker compose run --rm ingest rankings --backfill
docker compose run --rm ingest prices
```

With `SINK=local`, raw data lands as JSON Lines under `data/raw/`, one file per date. Reruns replace a date's file rather than duplicating it; the BigQuery sink does the same with a transactional partition swap.

```bash
docker compose run --rm transform build           # dbt build into data/warehouse.duckdb
```

The same dbt project runs on DuckDB locally and in CI (`--target local`) and on BigQuery in production (`--target bigquery`).

## Data quality, by design

- **Completeness:** every day has exactly 51 rows (top 50 + "other"), and no day is missing except two dates the source itself lacks, listed with evidence in `seeds/known_source_gaps.csv`.
- **Point-in-time prices:** list prices form a type-2 history built from daily snapshots of the model list, so a price cut never rewrites past spend. It is a model rebuilt from raw data, not a dbt snapshot, so it is reproducible from scratch.
- **Exact pricing joins only:** usage joins to prices on a key rebuilt in the rankings' own format (canonical slug plus `:variant`). No fuzzy matching: `ministral-8b` is not assumed to cost what `ministral-8b-2512` costs.
- **Zero-priced traffic is labeled, not hidden:** `:free` variants and stealth preview models are flagged in staging and priced at zero downstream.

## Data and caveats

- **One marketplace, not the market.** OpenRouter routes developer traffic; direct API traffic to any provider is not visible here.
- **Tokens are not comparable across providers**, which count with their own tokenizers.
- **Spend is implied**: tokens times list price, with a stated prompt/completion blend. It is an index, not anyone's revenue.
- **Price history starts when this project started**, from daily snapshots of the model list.

Source: OpenRouter ([openrouter.ai/rankings](https://openrouter.ai/rankings)), licensed CC BY 4.0. As-of dates are recorded with every row.
