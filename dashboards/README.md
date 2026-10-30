# Dashboards

Two front ends read the same governed `metrics` views, and the Dash app's top bar lets each
visitor choose one (`/` for Dash, `/datastudio` for the embedded Data Studio report). None of them computes a metric of its own.

| Front end | Where it runs | Data path | Status |
| --- | --- | --- | --- |
| Plotly Dash (`services/dashboard`) | Container in this stack; Cloud Run later | DuckDB locally, BigQuery in production | Built, tested |
| [Google Data Studio](https://datastudio.google.com/reporting/9eaf6a67-8c9b-44df-bece-b5aaf7d1e203) (formerly Looker Studio) | Google, view-only link | BigQuery `metrics` views and the `dash_*` reporting views, live | Built |

![Dash dashboard](screenshots/dash.png)

The Dash app shows the four views from the plan: headline tiles, the spend bridge, actual vs
frozen forecast, and provider share with provider and paid/all filters. It follows Anthropic's
published brand guidelines ([anthropics/skills, brand-guidelines](https://github.com/anthropics/skills/tree/main/skills/brand-guidelines)):
Dark `#141413` on Light `#faf9f5`, orange / blue / green accents, Poppins headings and Lora
body text. The blue and green are a step darker for contrast; provider lines also differ by
dash pattern and are labeled at their ends, because the brand's orange and green are hard to
tell apart with red-green colorblindness. It works at phone width
([screenshot](screenshots/dash_mobile.png)).

## Data Studio

Six headline scorecards (`dash_headline`), the spend waterfall (`dash_bridge`), actual vs
frozen forecast with its 90% range and a Tokens / Implied spend control (`dash_forecast`), and
token share vs spend share for the top 5 providers over the last 182 days (`provider_weekly`).
Same brand theme: Light background, Lora body and Montserrat headings (Data Studio offers no
Poppins), and fixed colors per provider. The `dash_*` views only reshape governed metrics views
for a tool without a scripting layer; they compute nothing new. Data Studio reads them with the
report owner's credentials, so viewers need no Google Cloud access.

Hex was the original plan, but its sign-up requires a work email address. Tableau Public was
dropped as well: it cannot read BigQuery, so it would need a spreadsheet export and a sync
job to show the same views a third time.

The embed needs embedding enabled on the report (Data Studio: File → Embed report → Enable
embedding) and link sharing set to Unlisted; otherwise the page offers a link instead.
