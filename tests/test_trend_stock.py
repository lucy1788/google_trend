import smtplib
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from trend_stock import (
    RECIPIENT,
    build_email_html,
    enrich_with_stock_data,
    fetch_trending_terms,
    run,
    send_email,
)


def make_mock_history(n=30, base_price=100.0, base_volume=1_000_000):
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "Close": [base_price + i for i in range(n)],
            "Volume": [base_volume + i * 10_000 for i in range(n)],
        },
        index=dates,
    )


def make_mock_rss(titles: list[str]) -> bytes:
    items = "".join(f"<item><title>{t}</title></item>" for t in titles)
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'.encode()


def mock_requests_get(content: bytes):
    mock_resp = MagicMock()
    mock_resp.content = content
    return mock_resp


# --- fetch_trending_terms ---

def test_fetch_trending_terms_returns_list(monkeypatch):
    monkeypatch.setattr(
        "trend_stock.requests.get",
        lambda *a, **kw: mock_requests_get(make_mock_rss(["Apple earnings", "Tesla recall", "weather"])),
    )
    result = fetch_trending_terms()
    assert result == ["Apple earnings", "Tesla recall", "weather"]


def test_fetch_trending_terms_empty(monkeypatch):
    monkeypatch.setattr(
        "trend_stock.requests.get",
        lambda *a, **kw: mock_requests_get(make_mock_rss([])),
    )
    result = fetch_trending_terms()
    assert result == []


def test_fetch_trending_terms_uses_us_geo(monkeypatch):
    captured = {}

    def capture(url, **kwargs):
        captured["url"] = url
        return mock_requests_get(make_mock_rss(["test"]))

    monkeypatch.setattr("trend_stock.requests.get", capture)
    fetch_trending_terms()
    assert "geo=US" in captured["url"]
    assert "hours=12" in captured["url"]


# --- enrich_with_stock_data ---

def test_enrich_returns_expected_keys(monkeypatch):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = make_mock_history()
    monkeypatch.setattr("trend_stock.yf.Ticker", lambda t: mock_ticker)
    result = enrich_with_stock_data("AAPL")
    assert result is not None
    assert set(result.keys()) == {"ticker", "price", "pct_change", "vol_ratio", "trend"}


def test_enrich_ticker_preserved(monkeypatch):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = make_mock_history()
    monkeypatch.setattr("trend_stock.yf.Ticker", lambda t: mock_ticker)
    result = enrich_with_stock_data("MSFT")
    assert result["ticker"] == "MSFT"


def test_enrich_correct_pct_change(monkeypatch):
    # n=5: closes [100, 101, 102, 103, 104] — prev=103, today=104
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = make_mock_history(n=5, base_price=100.0)
    monkeypatch.setattr("trend_stock.yf.Ticker", lambda t: mock_ticker)
    result = enrich_with_stock_data("AAPL")
    assert result is not None
    expected = round((104.0 - 103.0) / 103.0 * 100, 2)
    assert result["pct_change"] == expected


def test_enrich_trend_has_5_points(monkeypatch):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = make_mock_history(n=30)
    monkeypatch.setattr("trend_stock.yf.Ticker", lambda t: mock_ticker)
    result = enrich_with_stock_data("AAPL")
    assert result is not None
    assert len(result["trend"]) == 5


def test_enrich_trend_fewer_than_5_days(monkeypatch):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = make_mock_history(n=3)
    monkeypatch.setattr("trend_stock.yf.Ticker", lambda t: mock_ticker)
    result = enrich_with_stock_data("AAPL")
    assert result is not None
    assert len(result["trend"]) == 3


def test_enrich_returns_none_on_empty_history(monkeypatch):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()
    monkeypatch.setattr("trend_stock.yf.Ticker", lambda t: mock_ticker)
    assert enrich_with_stock_data("AAPL") is None


def test_enrich_returns_none_on_single_row(monkeypatch):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = make_mock_history(n=1)
    monkeypatch.setattr("trend_stock.yf.Ticker", lambda t: mock_ticker)
    assert enrich_with_stock_data("AAPL") is None


def test_enrich_vol_ratio_calculated(monkeypatch):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = make_mock_history(n=5, base_volume=1_000_000)
    monkeypatch.setattr("trend_stock.yf.Ticker", lambda t: mock_ticker)
    result = enrich_with_stock_data("AAPL")
    assert result is not None
    assert result["vol_ratio"] > 0


# --- build_email_html ---

SAMPLE_MATCHES = [
    {
        "term": "Apple earnings",
        "matched_name": "apple",
        "ticker": "AAPL",
        "price": 189.40,
        "pct_change": 2.30,
        "vol_ratio": 2.1,
        "trend": [185.0, 186.0, 187.0, 188.0, 189.40],
    },
    {
        "term": "Boeing recall",
        "matched_name": "boeing",
        "ticker": "BA",
        "price": 175.20,
        "pct_change": -1.50,
        "vol_ratio": 1.3,
        "trend": [178.0, 177.0, 176.0, 175.5, 175.20],
    },
]

SAMPLE_TERMS = ["Apple earnings", "Boeing recall", "weather forecast", "NBA finals"]


def test_build_email_html_contains_tickers():
    html = build_email_html(SAMPLE_MATCHES, SAMPLE_TERMS)
    assert "AAPL" in html
    assert "BA" in html


def test_build_email_html_contains_terms():
    html = build_email_html(SAMPLE_MATCHES, SAMPLE_TERMS)
    assert "Apple earnings" in html
    assert "Boeing recall" in html


def test_build_email_html_contains_price():
    html = build_email_html(SAMPLE_MATCHES, SAMPLE_TERMS)
    assert "189.40" in html


def test_build_email_html_positive_change_green():
    html = build_email_html(SAMPLE_MATCHES, SAMPLE_TERMS)
    assert "#16a34a" in html


def test_build_email_html_negative_change_red():
    html = build_email_html(SAMPLE_MATCHES, SAMPLE_TERMS)
    assert "#dc2626" in html


def test_build_email_html_shows_match_count():
    html = build_email_html(SAMPLE_MATCHES, SAMPLE_TERMS)
    assert "2 trending" in html


def test_build_email_html_no_matches_fallback():
    html = build_email_html([], SAMPLE_TERMS)
    assert "No S" in html


def test_build_email_html_positive_has_plus_sign():
    html = build_email_html(SAMPLE_MATCHES, SAMPLE_TERMS)
    assert "+2.30%" in html


def test_build_email_html_negative_no_plus_sign():
    html = build_email_html(SAMPLE_MATCHES, SAMPLE_TERMS)
    assert "-1.50%" in html


def test_build_email_html_shows_all_trending_terms():
    html = build_email_html(SAMPLE_MATCHES, SAMPLE_TERMS)
    assert "weather forecast" in html
    assert "NBA finals" in html


def test_build_email_html_trending_section_present():
    html = build_email_html([], SAMPLE_TERMS)
    assert "All Trending Searches Today" in html


# --- send_email ---

def test_send_email_calls_login_and_sendmail(monkeypatch):
    monkeypatch.setenv("GMAIL_USER", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

    with patch("smtplib.SMTP_SSL") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server
        mock_smtp_cls.return_value.__exit__.return_value = False

        send_email("Test Subject", "<html>body</html>")

        mock_server.login.assert_called_once_with("test@gmail.com", "secret")
        mock_server.sendmail.assert_called_once()


def test_send_email_sends_to_recipient(monkeypatch):
    monkeypatch.setenv("GMAIL_USER", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

    with patch("smtplib.SMTP_SSL") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server
        mock_smtp_cls.return_value.__exit__.return_value = False

        send_email("Subject", "<html></html>")

        _, args, _ = mock_server.sendmail.mock_calls[0]
        assert args[1] == RECIPIENT


def test_send_email_missing_env_raises(monkeypatch):
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    with pytest.raises(KeyError):
        send_email("Subject", "<html></html>")


def test_send_email_uses_gmail_smtp(monkeypatch):
    monkeypatch.setenv("GMAIL_USER", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")

    with patch("smtplib.SMTP_SSL") as mock_smtp_cls:
        mock_smtp_cls.return_value.__enter__.return_value = MagicMock()
        mock_smtp_cls.return_value.__exit__.return_value = False
        send_email("Subject", "<html></html>")
        args = mock_smtp_cls.call_args[0]
        assert args[0] == "smtp.gmail.com"
        assert args[1] == 465


# --- run ---

@pytest.fixture
def mock_run_deps(monkeypatch):
    monkeypatch.setattr("trend_stock.build_lookup", lambda: {"apple": "AAPL", "nvidia": "NVDA"})
    monkeypatch.setattr("trend_stock.fetch_trending_terms", lambda: ["Apple earnings", "NVDA surge", "weather"])
    monkeypatch.setattr(
        "trend_stock.enrich_with_stock_data",
        lambda ticker: {"ticker": ticker, "price": 150.0, "pct_change": 1.5, "vol_ratio": 1.2, "trend": [145, 146, 147, 148, 150]},
    )


def test_run_sends_email(mock_run_deps, monkeypatch):
    sent = {}
    monkeypatch.setattr("trend_stock.send_email", lambda s, h: sent.update({"subject": s, "html": h}))
    run()
    assert "subject" in sent
    assert "Stock Trend Radar" in sent["subject"]


def test_run_email_contains_matched_tickers(mock_run_deps, monkeypatch):
    sent = {}
    monkeypatch.setattr("trend_stock.send_email", lambda s, h: sent.update({"html": h}))
    run()
    assert "AAPL" in sent["html"]
    assert "NVDA" in sent["html"]


def test_run_deduplicates_tickers(monkeypatch):
    monkeypatch.setattr("trend_stock.build_lookup", lambda: {"apple": "AAPL"})
    monkeypatch.setattr("trend_stock.fetch_trending_terms", lambda: ["Apple news", "Apple stock surge"])

    enrich_calls = []

    def mock_enrich(ticker):
        enrich_calls.append(ticker)
        return {"ticker": ticker, "price": 150.0, "pct_change": 1.5, "vol_ratio": 1.2, "trend": [145, 146, 147, 148, 150]}

    monkeypatch.setattr("trend_stock.enrich_with_stock_data", mock_enrich)
    monkeypatch.setattr("trend_stock.send_email", lambda s, h: None)
    run()
    assert enrich_calls.count("AAPL") == 1


def test_run_skips_ticker_with_no_stock_data(monkeypatch):
    monkeypatch.setattr("trend_stock.build_lookup", lambda: {"apple": "AAPL"})
    monkeypatch.setattr("trend_stock.fetch_trending_terms", lambda: ["Apple earnings"])
    monkeypatch.setattr("trend_stock.enrich_with_stock_data", lambda ticker: None)

    sent = {}
    monkeypatch.setattr("trend_stock.send_email", lambda s, h: sent.update({"html": h}))
    run()
    assert "No S" in sent["html"]


def test_run_no_matches_still_sends(monkeypatch):
    monkeypatch.setattr("trend_stock.build_lookup", lambda: {})
    monkeypatch.setattr("trend_stock.fetch_trending_terms", lambda: ["weather forecast"])
    monkeypatch.setattr("trend_stock.find_ticker", lambda term, lookup: None)

    sent = {}
    monkeypatch.setattr("trend_stock.send_email", lambda s, h: sent.update({"called": True, "html": h}))
    run()
    assert sent.get("called")
    assert "No S" in sent["html"]
