# Project Summary for AI Assistants

## Purpose

This project is a Python service called **Stock Trend Radar**. It sends a daily email digest of US Google Trends searches that appear related to S&P 500 stocks. For each matched stock, it includes recent Yahoo Finance price and volume data.

The intended production path is a scheduled GitHub Actions workflow that runs every weekday morning and emails the digest through Gmail SMTP.

## Main Runtime Flow

Entry point: `trend_stock.py`

1. `build_lookup()` loads S&P 500 company names from Wikipedia and merges in curated aliases from `sp500.py`.
2. `fetch_trending_terms()` reads the US Google Trends RSS feed for the last 12 hours.
3. Each trending term is matched locally with `find_ticker()`.
4. Terms that do not match locally are sent to `classify_terms()` in `llm_classifier.py`, which uses an OpenAI GPT model with structured output to conservatively identify related US stock tickers.
5. For each unique ticker, `enrich_with_stock_data()` fetches 30 days of Yahoo Finance history with `yfinance`.
6. `build_email_html()` renders an HTML email with matched stocks and the full trending terms list.
7. `send_email()` sends the digest using Gmail SMTP credentials from environment variables.

## Key Files

- `trend_stock.py`: Main orchestration, Google Trends RSS fetch, Yahoo Finance enrichment, HTML email rendering, and Gmail SMTP sending.
- `sp500.py`: S&P 500 loading from Wikipedia, curated alternate-name mapping, and deterministic ticker matching.
- `llm_classifier.py`: OpenAI GPT-based fallback classifier for unmatched trending terms.
- `tests/`: Pytest coverage for matching, enrichment, email generation, sending behavior, and LLM classifier behavior.
- `.github/workflows/daily_trend.yml`: Scheduled production job that runs the digest.
- `.github/workflows/ci.yml`: CI test workflow.
- `pyproject.toml`: Python metadata, dependencies, and pytest configuration.
- `google_trend.ipynb`: Notebook artifact, likely used for exploration or earlier development.

## Dependencies

Runtime dependencies from `pyproject.toml`:

- `requests`: HTTP calls to Google Trends RSS and Wikipedia.
- `pandas`: Parses the S&P 500 Wikipedia table.
- `lxml`: HTML table parsing support for pandas.
- `yfinance`: Pulls recent stock history.
- `openai`: Runs the LLM fallback classifier.
- `pydantic`: Defines the structured output schema for the classifier.

Dev dependency:

- `pytest`

The project expects Python 3.11+ and appears to use `uv` for dependency management.

## Environment Variables

Required for full production run:

- `GMAIL_USER`: Gmail address used as sender.
- `GMAIL_APP_PASSWORD`: Gmail app password for SMTP authentication.
- `OPENAI_API_KEY`: OpenAI API key for LLM fallback classification.
- `OPENAI_MODEL`: Optional model override; defaults to `gpt-5.2`.

Without `OPENAI_API_KEY`, runs with unmatched terms will fail when `classify_terms()` is called. Unit tests mock this where needed.

## Matching Behavior

`sp500.find_ticker(term, lookup)` matches in this order:

1. Exact lowercase match against a company or alias name.
2. Whole-word substring match against company or alias names.
3. Exact ticker token match for tickers with at least 4 characters.

The 4+ character ticker rule avoids false positives from short tickers that are common words or letters, such as `F`, `T`, `A`, or `ALL`.

`ALTERNATE_NAMES` in `sp500.py` is important because many trend terms use brand names, short company names, or CEO names instead of formal S&P 500 security names.

## LLM Fallback

`llm_classifier.py` sends all unmatched terms in one batched OpenAI Responses API request. It uses structured output and expects a list of objects with:

- `term`
- `ticker`
- `reason`

The system prompt instructs the model to be conservative and return `null` when a term is not finance-related or cannot be tied confidently to a specific stock.

LLM-matched email rows show an `AI` badge.

## Tests

Run tests with:

```bash
uv run pytest
```

Pytest is configured to skip `integration` tests by default:

```toml
addopts = "-m 'not integration'"
```

Most network and SMTP behavior is mocked. The live S&P 500 test is marked `integration`.

## Production Automation

`.github/workflows/daily_trend.yml` runs:

```bash
uv sync
uv run python trend_stock.py
```

It passes these GitHub Actions secrets:

- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`
- `OPENAI_API_KEY`

The schedule is currently:

```yaml
cron: "0 15 * * 1-5"
```

The workflow comment says this is 7am PST on weekdays. GitHub cron uses UTC, so this is 7am during Pacific Standard Time and 8am during Pacific Daylight Time.

## Important Implementation Notes

- `RECIPIENT` is hard-coded in `trend_stock.py`.
- `load_sp500()` depends on Wikipedia table structure and network access.
- `enrich_with_stock_data()` returns `None` when Yahoo Finance history is empty or has fewer than two rows.
- Local deterministic matches are skipped if stock data is unavailable, causing no row to be shown for that term.
- LLM fallback matches are included even when stock data is unavailable, with placeholder dashes in the email.
- Duplicate tickers are suppressed with `seen_tickers`.
- HTML rendering is string-based and not escaped; if input sources contain unexpected HTML-like text, email output could render it.

## Current Development State

The repository has tests for the core behavior and appears designed as a small scheduled automation rather than a packaged library or web app. Future changes should preserve the narrow workflow:

1. Gather trend terms.
2. Match them to likely stocks.
3. Enrich with market data.
4. Send one concise digest email.

When modifying behavior, update or add focused pytest tests for matching, LLM fallback, email rendering, and orchestration.
