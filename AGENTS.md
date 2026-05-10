# Stock Trend Radar

This repository contains a Python automation that emails a daily digest of US Google Trends matched to S&P 500 stocks, with price and volume data. It runs from GitHub Actions on weekdays.

## Architecture

```text
trend_stock.py   orchestrates the full pipeline
sp500.py         S&P 500 data loading and deterministic ticker matching
llm_classifier.py OpenAI GPT fallback classification for unmatched trend terms
tests/           pytest unit tests
.github/
  workflows/
    daily_trend.yml   scheduled email job
    ci.yml            test runner on push/PR
```

## Pipeline

1. Fetch top US trending searches from the past 12 hours via Google Trends RSS.
2. Match each term against the S&P 500 lookup using `find_ticker()`.
3. Send locally unmatched terms to `classify_terms()` for conservative LLM ticker classification.
4. Enrich unique matched tickers with 30 days of price and volume history via `yfinance`.
5. Build an HTML email with a stock table and full trending terms list.
6. Send via Gmail SMTP to the configured recipient.

## Key Functions

| Function | File | Purpose |
|---|---|---|
| `fetch_trending_terms()` | `trend_stock.py` | Fetches Google Trends RSS and returns a list of strings |
| `enrich_with_stock_data(ticker)` | `trend_stock.py` | Returns price, pct_change, vol_ratio, and 5-day trend |
| `build_email_html(matches, all_terms)` | `trend_stock.py` | Builds the HTML email body |
| `send_email(subject, html)` | `trend_stock.py` | Sends via Gmail SMTP using env vars |
| `run()` | `trend_stock.py` | End-to-end orchestration |
| `load_sp500()` | `sp500.py` | Scrapes the S&P 500 table from Wikipedia |
| `build_lookup()` | `sp500.py` | Merges S&P 500 names with alternate names and CEO names |
| `find_ticker(term, lookup)` | `sp500.py` | Matches a trending term to a ticker in three passes |
| `classify_terms(terms)` | `llm_classifier.py` | Uses an OpenAI GPT model to classify unmatched terms |

## Ticker Matching Logic

`find_ticker()` checks in order:

1. Exact match on the full normalized term.
2. Word-boundary regex match where any company name or alias appears as whole words in the term.
3. Ticker symbol match where any ticker of 4+ characters appears as a standalone word.

Short tickers are excluded from ticker-token matching to avoid false positives like `ALL` matching "all time high".

`build_lookup()` covers the S&P 500 plus aliases in `ALTERNATE_NAMES`, including brand names, CEO names, and common abbreviations.

## Environment Variables

| Variable | Purpose |
|---|---|
| `GMAIL_USER` | Gmail address to send from |
| `GMAIL_APP_PASSWORD` | Gmail app password |
| `OPENAI_API_KEY` | OpenAI API key for LLM fallback classification |
| `OPENAI_MODEL` | Optional model override; defaults to `gpt-5.2` |

Store these as GitHub Actions secrets for production. Use a local `.env` file for local runs.

## Running Locally

```bash
uv sync
uv run --env-file .env python trend_stock.py
```

## Running Tests

```bash
uv run pytest
uv run pytest -m integration
```

The default pytest configuration excludes tests marked `integration`.

## Dependencies

- `requests`: HTTP calls for Google Trends RSS and Wikipedia.
- `pandas`: Data handling and Wikipedia table parsing.
- `lxml`: HTML parsing support for `pandas.read_html`.
- `yfinance`: Stock price and volume history.
- `openai`: LLM fallback classification.
- `pydantic`: Structured output schema models for the classifier.
- `pytest`: Test runner.

## Agent Notes

- Keep changes focused on the scheduled digest workflow.
- Preserve mocked unit tests for network, SMTP, and LLM behavior.
- Add or update tests when changing matching, classification, enrichment, or email rendering.
- `RECIPIENT` is currently hard-coded in `trend_stock.py`.
- GitHub cron is UTC. The current schedule comment says 7am PST; during PDT, the same cron runs at 8am Pacific.
