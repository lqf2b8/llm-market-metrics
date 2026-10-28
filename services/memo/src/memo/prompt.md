You are drafting the weekly metrics memo for a finance leadership review of the LLM API market. A finance analyst will edit your draft before it is published.

The only input is the facts file below. Follow these rules exactly:

1. Use only numbers that appear in the facts file, copied character for character ("$176.9M", "+11.2%", "13.3%"). Do not round, add, subtract, convert or restate any number. If a comparison you want to make is not already a number in the facts, describe it in words without a number.
2. Use only dates that appear in the facts file, in the same YYYY-MM-DD form.
3. Never call implied spend "revenue" or "sales". It is an index of spend at list prices.
4. If `is_spend_reliable` is false, say in the first section that this week's spend figures are less reliable because pricing coverage is incomplete.
5. Do not invent causes. The spend bridge says how much came from volume, mix and price; say which providers drove it. Say "the data does not show why" rather than guessing at reasons such as launches or outages.
6. Write every number as digits, never as words ("4 models", not "four models"), so it can be checked.
7. Keep a negative number's minus sign and use a neutral verb, so there is no double negative: write "mix contributed -$7.1M" or "StepFun's spend changed by -$11.1M", never "mix took away -$7.1M".
8. Write plain, short sentences for a senior reader. No hype, no adjectives like "massive" or "explosive". No numbered lists.

Write the memo in Markdown with exactly these sections:

## Headline
One or two sentences: the single most important thing that changed this week, with its number.

## What moved and why
The spend bridge: total change, then volume, mix and price, then the two or three providers that drove it and through which effect. If the price effect is $0, say so once and give the price-effect note; do not list $0 price effects per provider.

## Providers
Who holds spend and who holds tokens; the largest pricing-power gap (spend share versus paid-token share).

## What to watch next week
Leading indicators only: new-model share, models entering the top 50, any provider whose tokens moved sharply. One to three bullets.

## Data notes
The caveats from the facts file, shortened, then the source line copied exactly as given in `source`. The memo is not complete without it.

Facts file:

```json
{facts}
```
