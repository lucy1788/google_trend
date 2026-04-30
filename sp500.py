import io
import re

import pandas as pd
import requests


ALTERNATE_NAMES: dict[str, str] = {
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "facebook": "META",
    "meta": "META",
    "amazon": "AMZN",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "tesla": "TSLA",
    "nvidia": "NVDA",
    "netflix": "NFLX",
    "exxon": "XOM",
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "walmart": "WMT",
    "disney": "DIS",
    "boeing": "BA",
    "ford": "F",
    "general motors": "GM",
    "gm": "GM",
    "att": "T",
    "at&t": "T",
    "uber": "UBER",
    "airbnb": "ABNB",
    "paypal": "PYPL",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "amd": "AMD",
    "intel": "INTC",
    "qualcomm": "QCOM",
    "pfizer": "PFE",
    "johnson & johnson": "JNJ",
    "johnson and johnson": "JNJ",
    "elon musk": "TSLA",
    "sam altman": "MSFT",  # OpenAI / Microsoft partnership
    "mark zuckerberg": "META",
    "tim cook": "AAPL",
    "jensen huang": "NVDA",
    "jeff bezos": "AMZN",
}


def load_sp500() -> dict[str, str]:
    """Fetch S&P 500 table from Wikipedia. Returns {lowercase company name: ticker}."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; trend-stock-bot/1.0)"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    df = tables[0]
    df.columns = df.columns.str.strip()
    return {
        row["Security"].strip().lower(): row["Symbol"].strip().replace(".", "-")
        for _, row in df.iterrows()
    }


def build_lookup() -> dict[str, str]:
    """Combine S&P 500 names + alternate names into one {name: ticker} lookup."""
    lookup = load_sp500()
    lookup.update(ALTERNATE_NAMES)
    return lookup


def find_ticker(term: str, lookup: dict[str, str]) -> tuple[str, str] | None:
    """
    Given a trending search term, return (matched_name, ticker) or None.

    Checks in order:
    1. Exact match on the full term
    2. Any lookup key appears as whole words in the term (word-boundary match)
    3. Any word in the term is an exact ticker symbol
    """
    normalized = term.lower().strip()

    if normalized in lookup:
        return (normalized, lookup[normalized])

    for name, ticker in lookup.items():
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, normalized):
            return (name, ticker)

    # Only match ticker symbols that are 4+ chars to avoid common English words
    # (e.g. ALL=Allstate, F=Ford, T=AT&T, A=Agilent colliding with "all", "for", "the", "a")
    words = set(normalized.upper().split())
    for name, ticker in lookup.items():
        if len(ticker) >= 4 and ticker in words:
            return (name, ticker)

    return None


if __name__ == "__main__":
    print("Loading S&P 500 from Wikipedia...")
    sp500 = load_sp500()
    print(f"  {len(sp500)} companies loaded")
    print(f"  Sample: {dict(list(sp500.items())[:5])}\n")

    print("Building full lookup (S&P 500 + alternate names)...")
    lookup = build_lookup()
    print(f"  {len(lookup)} total entries\n")

    test_terms = [
        "Apple earnings beat expectations",
        "Elon Musk tweet causes market chaos",
        "NVDA hits all time high",
        "Jensen Huang speaks at CES",
        "weather forecast this weekend",
        "Boeing recall announced",
        "Meta layoffs 2024",
    ]

    print("Testing find_ticker on sample terms:")
    for term in test_terms:
        result = find_ticker(term, lookup)
        if result:
            name, ticker = result
            print(f"  '{term}'  ->  {ticker}  (matched: '{name}')")
        else:
            print(f"  '{term}'  ->  no match")
