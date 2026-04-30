# Stock Trend Radar

Sends a daily email digest of US Google Trends that match S&P 500 stocks, with price and volume data for each match.

## What it does

Every weekday morning at 7am PST, a GitHub Actions job:

1. Fetches the top trending US searches from Google Trends
2. Matches each term against S&P 500 company names, tickers, CEO names, and common brand aliases
3. Pulls 30 days of price and volume history from Yahoo Finance for each match
4. Emails an HTML digest with the matched stocks and a full list of the day's trending terms

**Example email:**

| Trending Search | Ticker | Price | Today's Change | Volume |
|---|---|---|---|---|
| Apple earnings | AAPL | $189.40 | +2.30% | 2.1x avg |
| Boeing recall | BA | $175.20 | -1.50% | 1.3x avg |

Followed by a numbered list of all trending searches that day.

## Project structure

```
trend_stock.py      # main script — fetch, match, enrich, send
sp500.py            # S&P 500 loader and ticker matching logic
tests/
  test_trend_stock.py
  test_sp500.py
.github/workflows/
  daily_trend.yml   # scheduled email job (7am PST weekdays)
  ci.yml            # runs tests on every push and PR
```

## Local setup

**Requirements:** Python 3.11+, [uv](https://docs.astral.sh/uv/)

```bash
uv sync
```

Create a `.env` file:

```
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

> To generate an app password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)

Run the script:

```bash
uv run --env-file .env python trend_stock.py
```

Run the tests:

```bash
uv run pytest
```

## GitHub Actions setup

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions** and add two secrets:
   - `GMAIL_USER` — your Gmail address
   - `GMAIL_APP_PASSWORD` — your 16-character app password
3. The workflow runs automatically at 7am PST on weekdays

To trigger a manual run: **Actions → Daily Stock Trend Radar → Run workflow**

## How matching works

A trending term is matched to a stock in three passes:

1. **Exact match** — the full term matches a company name in the lookup
2. **Substring match** — any company name or alias appears as whole words in the term (e.g. `"Apple earnings"` → `AAPL`)
3. **Ticker match** — a 4+ character ticker appears as a word in the term (e.g. `"NVDA surge"` → `NVDA`)

The lookup covers all ~500 S&P 500 companies plus common aliases like brand names (`"Google"`, `"Facebook"`) and CEO names (`"Elon Musk"`, `"Jensen Huang"`).
