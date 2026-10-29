<!-- Text for the two Markdown cells in the Hex app. Hex fills {{ ... }} from Python variables. -->

<!-- Top of the app -->
# LLM API Market: Weekly Metrics Review

Week of {{ latest_week_label }} · data through {{ data_through_label }}

Usage across the top 50 models on OpenRouter, priced at list prices. **Implied spend is an index, not anyone's revenue**: tokens × list price, with an assumed 75% prompt / 25% completion split.

<!-- Bottom of the app -->
---
**Caveats.** OpenRouter is one marketplace, not the whole market. Token counts use each provider's tokenizer and are not strictly comparable. Spend trends use only weeks where at least 90% of top-50 tokens are priced.

Every number here is read from the governed `metrics` views in BigQuery, the same ones the API and the weekly memo use. Code: [github.com/lqf2b8/llm-market-metrics](https://github.com/lqf2b8/llm-market-metrics)

Source: OpenRouter (openrouter.ai/rankings), CC BY 4.0. An independent project, not affiliated with Anthropic or OpenRouter.
