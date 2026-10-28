# LLM API Market Metrics

An automated weekly metrics review of the LLM API market, built the way a finance analytics team would run one: public usage data in, governed metric definitions in dbt, a weekly memo explaining what moved and why, and two dashboards (Hex and Tableau) that read the same numbers.

> **Status: in progress.** Days 1-4, 6 and 7 of 12: ingest, dbt (raw data to governed metrics and a price-volume-mix spend bridge, 73 tests on the full history), a read-only metrics API and a Claude-drafted weekly memo with a number check, all running locally in containers. Cloud deployment (day 5) is deferred until the local services are done; the forecast, dashboards and portal are not built yet.

## What it answers each week

- **Why did spend move?** A price-volume-mix bridge splits the week-over-week change in implied spend.
- **Are we on plan?** Each Monday's forecast is frozen, then compared with actuals and its prediction interval.
- **What is about to change?** Adoption curves for newly launched models, and providers whose spend share and token share diverge.

## Architecture

Seven containerized services on Google Cloud Run, sharing one BigQuery warehouse. They pass data only through BigQuery tables and one read-only HTTP API.

| Service | Runs as | Status |
| --- | --- | --- |
| `ingest`: OpenRouter rankings and model prices to the raw layer | Cloud Run job | Built, tested |
| `transform`: dbt staging, price history, marts, metrics | Cloud Run job | Built, tested; runs locally in Docker |
| `analysis`: frozen forecasts (the spend bridge lives in dbt) | Cloud Run job | Planned |
| `export`: metrics to a Google Sheet for Tableau Public | Cloud Run job | Planned |
| `metrics-api`: read-only FastAPI over the metrics | Cloud Run service | Built, tested; runs locally in Docker |
| `memo`: weekly memo drafted by Claude, checked against the data | Cloud Run job | Built, tested; runs locally in Docker |
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

```bash
docker compose up                                 # ingest, dbt build, then the API on :8080
```

The API's interactive docs are at http://localhost:8080/docs. Endpoints: `/as-of`, `/kpis`, `/kpis/history`, `/providers`, `/bridge`; each takes `week=` (a Monday) and defaults to the latest complete week. It reads only the `metrics` views, so it cannot disagree with the dashboards or the memo.

## Data quality, by design

- **Completeness:** every day has exactly 51 rows (top 50 + "other"), and no day is missing except two dates the source itself lacks, listed with evidence in `seeds/known_source_gaps.csv`.
- **Point-in-time prices:** list prices form a type-2 history built from daily snapshots of the model list, so a price cut never rewrites past spend. It is a model rebuilt from raw data, not a dbt snapshot, so it is reproducible from scratch.
- **Exact pricing joins only:** usage joins to prices on a key rebuilt in the rankings' own format (canonical slug plus `:variant`). No fuzzy matching: `ministral-8b` is not assumed to cost what `ministral-8b-2512` costs.
- **Zero-priced traffic is labeled, not hidden:** `:free` variants and stealth preview models are flagged in staging and priced at zero downstream.
- **Every price has a basis:** each day's tokens carry how they were priced: listed, retired-model list price (from a seed where every row cites its source), free, stealth preview, or unpriced.
- **Reconciliation:** weekly provider and market tables add back to the daily facts to the token, tested on every build.

## Governed metrics

Each metric is defined once, in dbt's semantic layer (`models/semantic/_semantic.yml`), and validated against the warehouse with MetricFlow. Consumers read two views in the `metrics` schema whose columns carry the metric names: `weekly_kpis` (headline) and `provider_weekly` (driver view). CI queries MetricFlow and fails if either disagrees with the view, so the definitions and what people see cannot drift apart.

| Metric | Definition |
| --- | --- |
| `tokens` | All tokens, top 50 plus the "other" bucket |
| `paid_tokens` | Top-50 tokens excluding free variants and stealth previews |
| `implied_spend_usd` | Tokens x blended list price; an index (see sensitivity below) |
| `effective_paid_usd_per_mtok` | Implied spend per million priced paid tokens |
| `priced_coverage` | Share of top-50 tokens with a known price |
| `zero_priced_share` | Share of top-50 tokens served free |
| `new_model_share` | Share of top-50 tokens from models within 56 days of entering the top 50 |

Provider token share and spend share are the same metrics for one provider divided by the market.

## The weekly memo

Claude drafts the memo from a facts file built from the metrics API; it is told to use only numbers that appear there, copied exactly. A checker then extracts every number and date from the draft and rejects the memo if any is missing from the facts, so a rounded, added-up or invented figure cannot reach a reader. An analyst edits each draft before it is merged into [`memos/`](memos/). See [`memos/README.md`](memos/README.md).

## Why spend moved: the bridge

Each week's change in implied spend splits into three parts, per model, that add up exactly (tested on every build):

- **Volume:** the market grew or shrank, at last week's prices and mix.
- **Mix:** a model gained or lost share, at its last-week price.
- **Price:** a model's own price changed.

For the week of 2026-10-19, implied spend rose $17.8M: +$24.9M from volume and -$7.1M from mix as traffic shifted toward cheaper models. Anthropic added $16.6M; StepFun lost $13.7M of share. Price effects are measured only from 2026-10-28, when daily price snapshots began; before that, prices are backfilled and constant.

## Pricing coverage

OpenRouter drops retired models from its price list, so older history has more unpriced volume. Retired paid models that carry most of it are priced from a cited seed (`seeds/retired_model_prices.csv`); the rest stays unpriced and is measured instead of hidden.

| Basis | Share of all tokens, Jan 2025 to Oct 2026 |
| --- | --- |
| Listed price | 75.5% |
| Free variants | 8.9% |
| Outside the top 50 ("other" row, no single price) | 6.6% |
| Stealth previews (free) | 4.0% |
| Retired model, sourced list price | 3.9% |
| Unpriced | 1.1% |

Priced coverage of top-50 tokens is reported every week. Spend trends use only complete weeks with at least 90% coverage (`is_spend_reliable`), which holds from July 2025 onward.

## How much the spend assumption matters

OpenRouter does not publish the split between prompt and completion tokens, so implied spend blends the two prices with a stated prompt share (default 75%, `var('prompt_token_share')`). For the week of 2026-10-19:

| Prompt share | Implied spend | Anthropic share of spend | DeepSeek share of spend |
| --- | --- | --- | --- |
| 50% | $265M | 49.2% | 7.8% |
| **75% (default)** | **$177M** | **49.2%** | **8.6%** |
| 90% | $124M | 49.3% | 9.5% |
| 95% | $106M | 49.3% | 10.0% |

The level moves by a factor of 2.5 across plausible splits; provider shares barely move. So the weekly review leads with shares and changes and treats the dollar level as an index.

## Data and caveats

- **One marketplace, not the market.** OpenRouter routes developer traffic; direct API traffic to any provider is not visible here.
- **Tokens are not comparable across providers**, which count with their own tokenizers.
- **Spend is implied**: tokens times list price, with a stated prompt/completion blend. It is an index, not anyone's revenue.
- **Price history starts when this project started**, from daily snapshots of the model list.

Source: OpenRouter ([openrouter.ai/rankings](https://openrouter.ai/rankings)), licensed CC BY 4.0. As-of dates are recorded with every row.
