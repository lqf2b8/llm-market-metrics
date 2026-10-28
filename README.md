# LLM API Market Metrics

An automated weekly metrics review of the LLM API market, built the way a finance analytics team would run one: public usage data in, governed metric definitions in dbt, a weekly memo explaining what moved and why, and two dashboards (Hex and Tableau) that read the same numbers.

> **Status: in progress.** Day 1 of 12: the ingest service is built and tested; nothing below it exists yet.

## What it answers each week

- **Why did spend move?** A price-volume-mix bridge splits the week-over-week change in implied spend.
- **Are we on plan?** Each Monday's forecast is frozen, then compared with actuals and its prediction interval.
- **What is about to change?** Adoption curves for newly launched models, and providers whose spend share and token share diverge.

## Architecture

Seven containerized services on Google Cloud Run, sharing one BigQuery warehouse. They pass data only through BigQuery tables and one read-only HTTP API.

| Service | Runs as | Status |
| --- | --- | --- |
| `ingest`: OpenRouter rankings and model prices to the raw layer | Cloud Run job | Built, tested |
| `transform`: dbt staging, price snapshot, marts, metrics | Cloud Run job | Planned |
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

## Data and caveats

- **One marketplace, not the market.** OpenRouter routes developer traffic; direct API traffic to any provider is not visible here.
- **Tokens are not comparable across providers**, which count with their own tokenizers.
- **Spend is implied**: tokens times list price, with a stated prompt/completion blend. It is an index, not anyone's revenue.
- **Price history starts when this project started**, from daily snapshots of the model list.

Source: OpenRouter ([openrouter.ai/rankings](https://openrouter.ai/rankings)), licensed CC BY 4.0. As-of dates are recorded with every row.
