# Dashboards

Three front ends read the same governed `metrics` views, and the portal lets each visitor
choose one. None of them computes a metric of its own.

| Front end | Where it runs | Data path | Status |
| --- | --- | --- | --- |
| Plotly Dash (`services/dashboard`) | Container in this stack; Cloud Run later | DuckDB locally, BigQuery in production | Built, tested |
| Looker Studio | Google, shared publicly | BigQuery `metrics` views, live | Next |
| Tableau Public | Tableau Public | Google Sheet the export job rewrites daily | Day 10 |

![Dash dashboard](screenshots/dash.png)

The Dash app shows the four views from the plan: headline tiles, the spend bridge, actual vs
frozen forecast, and provider share with provider and paid/all filters. It follows Anthropic's
published brand guidelines ([anthropics/skills, brand-guidelines](https://github.com/anthropics/skills/tree/main/skills/brand-guidelines)):
Dark `#141413` on Light `#faf9f5`, orange / blue / green accents, Poppins headings and Lora
body text. The blue and green are a step darker for contrast; provider lines also differ by
dash pattern and are labeled at their ends, because the brand's orange and green are hard to
tell apart with red-green colorblindness. It works at phone width
([screenshot](screenshots/dash_mobile.png)).

Hex was the original plan, but its sign-up requires a work email address.
