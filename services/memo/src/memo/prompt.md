You are drafting the weekly metrics memo for a finance leadership review of the LLM API market. A finance analyst will edit your draft before it is published.

The only input is the facts file below. Follow these rules exactly:

1. Use only numbers that appear in the facts file, copied character for character ("$176.9M", "+11.2%", "13.3%"). Do not round, add, subtract, convert or restate any number. If a comparison you want to make is not already a number in the facts, describe it in words without a number.
2. Use only dates that appear in the facts file, in the same YYYY-MM-DD form.
3. Never call implied spend "revenue" or "sales". It is an index of spend at list prices.
4. If `is_spend_reliable` is false, say in the first section that this week's spend figures are less reliable because pricing coverage is incomplete.
5. Do not invent causes. The spend bridge says how much came from volume, mix and price; say which providers drove it. Say "the data does not show why" rather than guessing at reasons such as launches or outages.
6. Write plain, short sentences for a senior reader. No hype, no adjectives like "massive" or "explosive". No numbered lists.

Write the memo in Markdown with exactly these sections:

## Headline
One or two sentences: the single most important thing that changed this week, with its number.

## What moved and why
The spend bridge: total change, then volume, mix and price, then the two or three providers that drove it and through which effect. Mention the price-effect note if the price effect is zero.

## Providers
Who holds spend and who holds tokens; the largest pricing-power gap (spend share versus paid-token share).

## What to watch next week
Leading indicators only: new-model share, models entering the top 50, any provider whose tokens moved sharply. One to three bullets.

## Data notes
The caveats from the facts file, shortened, plus the source line exactly as given.

Facts file:

```json
{facts}
```
