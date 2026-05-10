import os
import smtplib
import ssl
import xml.etree.ElementTree as ET
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
import yfinance as yf

from llm_classifier import classify_terms
from sp500 import build_lookup, find_ticker

RECIPIENT = "luciee.yin@gmail.com"
_TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=US&hours=12"


def fetch_trending_terms() -> list[str]:
    """Return today's top US trending search terms via Google Trends RSS feed."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; trend-stock-bot/1.0)"}
    response = requests.get(_TRENDS_RSS_URL, headers=headers, timeout=10)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    return [
        title for item in root.findall(".//item")
        if (title := item.findtext("title"))
    ]


def enrich_with_stock_data(ticker: str) -> dict | None:
    """
    Fetch 30 days of history for ticker.
    Returns price, pct_change, vol_ratio, 5-day trend — or None if data unavailable.
    """
    stock = yf.Ticker(ticker)
    hist = stock.history(period="30d")
    if hist.empty or len(hist) < 2:
        return None

    today_close = hist["Close"].iloc[-1]
    prev_close = hist["Close"].iloc[-2]
    pct_change = (today_close - prev_close) / prev_close * 100

    today_volume = hist["Volume"].iloc[-1]
    avg_volume = hist["Volume"].mean()
    vol_ratio = today_volume / avg_volume if avg_volume > 0 else 0

    return {
        "ticker": ticker,
        "price": round(float(today_close), 2),
        "pct_change": round(float(pct_change), 2),
        "vol_ratio": round(float(vol_ratio), 2),
        "trend": [round(float(p), 2) for p in hist["Close"].iloc[-5:].tolist()],
    }


def build_email_html(matches: list[dict], all_terms: list[str]) -> str:
    """Build HTML email body from stock matches and the full trending terms list."""
    today = date.today().strftime("%B %d, %Y")

    if matches:
        stock_section = f"""
  <p style="color:#64748b">{len(matches)} trending search(es) matched to stocks.</p>
  <table style="border-collapse:collapse;width:100%">
    <thead>
      <tr style="background:#f1f5f9;text-align:left">
        <th style="padding:8px 12px">Trending Search</th>
        <th style="padding:8px 12px">Ticker</th>
        <th style="padding:8px 12px">Price</th>
        <th style="padding:8px 12px">Today's Change</th>
        <th style="padding:8px 12px">Volume</th>
      </tr>
    </thead>
    <tbody>{"".join(_stock_row(m) for m in matches)}
    </tbody>
  </table>"""
    else:
        stock_section = "<p style=\"color:#64748b\">No S&amp;P 500 stocks found in today's trending searches.</p>"

    terms_list = "".join(
        f'<li style="padding:3px 0;color:#334155">{t}</li>' for t in all_terms
    )
    trending_section = f"""
  <h3 style="color:#1e293b;margin-top:32px">All Trending Searches Today</h3>
  <ol style="color:#334155;padding-left:20px">{terms_list}</ol>"""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto">
  <h2 style="color:#1e293b">Stock Trend Radar &mdash; {today}</h2>
  {stock_section}
  {trending_section}
  <p style="color:#94a3b8;font-size:12px;margin-top:24px">
    Source: Google Trends + Yahoo Finance &bull; US markets only
  </p>
</body>
</html>"""


def _stock_row(m: dict) -> str:
    ticker_cell = m["ticker"]
    if m.get("llm_matched"):
        ticker_cell += ' <span style="font-size:10px;background:#e0f2fe;color:#0369a1;padding:1px 4px;border-radius:3px">AI</span>'

    if m.get("price") is None:
        price_cell = "&mdash;"
        change_cell = "&mdash;"
        vol_cell = "&mdash;"
    else:
        color = "#16a34a" if m["pct_change"] >= 0 else "#dc2626"
        sign = "+" if m["pct_change"] >= 0 else ""
        price_cell = f"${m['price']:.2f}"
        change_cell = f'<span style="color:{color};font-weight:bold">{sign}{m["pct_change"]:.2f}%</span>'
        vol_cell = f"{m['vol_ratio']:.1f}x avg"

    return f"""
      <tr style="border-bottom:1px solid #e2e8f0">
        <td style="padding:8px 12px">{m["term"]}</td>
        <td style="padding:8px 12px;font-weight:bold">{ticker_cell}</td>
        <td style="padding:8px 12px">{price_cell}</td>
        <td style="padding:8px 12px">{change_cell}</td>
        <td style="padding:8px 12px">{vol_cell}</td>
      </tr>"""


def send_email(subject: str, html_body: str) -> None:
    """Send HTML email via Gmail SMTP. Reads GMAIL_USER and GMAIL_APP_PASSWORD from env."""
    sender = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, RECIPIENT, msg.as_string())


def run() -> None:
    """Fetch trending terms, match to stocks, enrich with price data, email the digest."""
    lookup = build_lookup()
    terms = fetch_trending_terms()

    matches = []
    seen_tickers: set[str] = set()
    unmatched_terms: list[str] = []

    for term in terms:
        result = find_ticker(term, lookup)
        if result is None:
            unmatched_terms.append(term)
            continue
        name, ticker = result
        if ticker in seen_tickers:
            continue
        stock_data = enrich_with_stock_data(ticker)
        if stock_data:
            matches.append({"term": term, "matched_name": name, **stock_data})
            seen_tickers.add(ticker)

    for classification in classify_terms(unmatched_terms):
        ticker = classification.get("ticker")
        if not ticker or ticker in seen_tickers:
            continue
        stock_data = enrich_with_stock_data(ticker)
        entry = {
            "term": classification["term"],
            "matched_name": ticker.lower(),
            "ticker": ticker,
            "llm_matched": True,
            "llm_reason": classification.get("reason", ""),
        }
        if stock_data:
            entry.update(stock_data)
        else:
            entry.update({"price": None, "pct_change": None, "vol_ratio": None, "trend": []})
        matches.append(entry)
        seen_tickers.add(ticker)

    today = date.today().strftime("%B %d, %Y")
    send_email(f"Stock Trend Radar - {today}", build_email_html(matches, terms))


if __name__ == "__main__":
    run()
