# Weekly memos

One file per ISO week, named by its Monday. Each memo is drafted by Claude from that
week's facts file (`facts/<week>.json`), built from the metrics API, and then edited by
a person before it is merged.

How a memo is made:

1. `facts`: the memo service calls the metrics API (`/as-of`, `/kpis`, `/kpis/history`,
   `/providers`, `/bridge`) and formats every number once ("$176.9M", "+11.2%").
2. `draft`: Claude writes the memo from the facts file only, in a fixed format: headline,
   what moved and why, providers, what to watch, data notes.
3. `check`: every number and date in the draft must appear in the facts file. A draft
   that fails is saved as `<week>.REJECTED.md` with the offending numbers listed, and
   nothing is published.
4. `review`: the analyst edits the draft. The front matter records the model, the time
   and a hash of the facts file, so any memo can be traced to the data it came from.

Run locally, with the API up (`docker compose up`) and `ANTHROPIC_API_KEY` in `.env`:

    docker compose run --rm memo                     # latest complete week
    docker compose run --rm memo --week 2026-10-19
