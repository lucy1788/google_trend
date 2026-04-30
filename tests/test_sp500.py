from unittest.mock import patch
import pandas as pd
import pytest

from sp500 import ALTERNATE_NAMES, build_lookup, find_ticker, load_sp500


MOCK_SP500 = pd.DataFrame({
    "Symbol": ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "BRK-B"],
    "Security": ["Apple Inc.", "Microsoft Corporation", "NVIDIA Corporation",
                 "Amazon.com Inc.", "Meta Platforms Inc.", "Alphabet Inc.",
                 "Tesla Inc.", "Berkshire Hathaway"],
})


def mock_read_html(_url):
    return [MOCK_SP500]


# --- load_sp500 ---

def test_load_sp500_returns_dict(monkeypatch):
    monkeypatch.setattr(pd, "read_html", mock_read_html)
    result = load_sp500()
    assert isinstance(result, dict)
    assert len(result) == len(MOCK_SP500)


def test_load_sp500_keys_are_lowercase(monkeypatch):
    monkeypatch.setattr(pd, "read_html", mock_read_html)
    result = load_sp500()
    assert all(k == k.lower() for k in result)


def test_load_sp500_known_companies(monkeypatch):
    monkeypatch.setattr(pd, "read_html", mock_read_html)
    result = load_sp500()
    assert result["apple inc."] == "AAPL"
    assert result["microsoft corporation"] == "MSFT"
    assert result["nvidia corporation"] == "NVDA"


def test_load_sp500_dot_replaced_with_dash(monkeypatch):
    monkeypatch.setattr(pd, "read_html", mock_read_html)
    result = load_sp500()
    # BRK.B → BRK-B (yfinance format)
    assert result["berkshire hathaway"] == "BRK-B"


# --- build_lookup ---

def test_build_lookup_includes_alternates(monkeypatch):
    monkeypatch.setattr(pd, "read_html", mock_read_html)
    result = build_lookup()
    assert result["elon musk"] == "TSLA"
    assert result["facebook"] == "META"
    assert result["google"] == "GOOGL"


def test_build_lookup_alternate_names_complete():
    for name, ticker in ALTERNATE_NAMES.items():
        assert isinstance(name, str) and name == name.lower(), f"Key not lowercase: {name}"
        assert isinstance(ticker, str) and len(ticker) <= 5, f"Suspicious ticker: {ticker}"


# --- find_ticker ---

@pytest.fixture
def lookup(monkeypatch):
    monkeypatch.setattr(pd, "read_html", mock_read_html)
    return build_lookup()


def test_find_ticker_exact_match(lookup):
    result = find_ticker("apple inc.", lookup)
    assert result == ("apple inc.", "AAPL")


def test_find_ticker_partial_match(lookup):
    result = find_ticker("Apple earnings beat expectations", lookup)
    assert result is not None
    assert result[1] == "AAPL"


def test_find_ticker_alternate_name(lookup):
    result = find_ticker("Elon Musk tweet causes controversy", lookup)
    assert result is not None
    assert result[1] == "TSLA"


def test_find_ticker_ticker_symbol_in_term(lookup):
    result = find_ticker("NVDA hits all time high", lookup)
    assert result is not None
    assert result[1] == "NVDA"


def test_find_ticker_case_insensitive(lookup):
    result = find_ticker("APPLE STOCK SURGES", lookup)
    assert result is not None
    assert result[1] == "AAPL"


def test_find_ticker_no_match(lookup):
    result = find_ticker("weather forecast this weekend", lookup)
    assert result is None


def test_find_ticker_empty_string(lookup):
    result = find_ticker("", lookup)
    assert result is None


def test_find_ticker_ceo_name(lookup):
    result = find_ticker("Jensen Huang speaks at CES", lookup)
    assert result is not None
    assert result[1] == "NVDA"


# --- integration (live network, skipped in CI unless explicitly enabled) ---

@pytest.mark.integration
def test_load_sp500_live():
    result = load_sp500()
    assert len(result) >= 490
    assert "apple inc." in result or any("apple" in k for k in result)
