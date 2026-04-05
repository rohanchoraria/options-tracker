"""
Market data module.

Current implementation:
- Stock prices: yfinance (.NS suffix for NSE)
- Option chains: NSE public API (no auth required)

TODO: Replace with broker API calls once credentials are available.
Supported brokers: Upstox API v2, Angel One SmartAPI, Zerodha Kite Connect.
See optionstracker.md for broker integration details.
"""

import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# ── NSE Session ───────────────────────────────────────────

NSE_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate, br",
}

_nse_session = None
_session_created_at = None
SESSION_TTL_SECONDS = 300  # refresh session every 5 minutes


def _get_nse_session():
    global _nse_session, _session_created_at
    now = time.time()
    if _nse_session is None or (now - (_session_created_at or 0)) > SESSION_TTL_SECONDS:
        session = requests.Session()
        try:
            session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
            _nse_session = session
            _session_created_at = now
        except Exception:
            pass
    return _nse_session


# ── Stock Prices ─────────────────────────────────────────

def get_stock_price(symbol):
    """Get current price for a single NSE stock. Returns float or None."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        data = ticker.history(period="1d")
        if not data.empty:
            return round(float(data["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return None


def get_multiple_stock_prices(symbols):
    """
    Fetch current prices for multiple NSE symbols in one call.
    Returns dict: {symbol: price}
    """
    if not symbols:
        return {}
    tickers = [f"{s}.NS" for s in symbols]
    try:
        data = yf.download(tickers, period="1d", progress=False, auto_adjust=True)
        prices = {}
        if len(symbols) == 1:
            if not data.empty:
                prices[symbols[0]] = round(float(data["Close"].iloc[-1]), 2)
        else:
            close = data["Close"].iloc[-1] if not data.empty else pd.Series()
            for s in symbols:
                val = close.get(f"{s}.NS")
                prices[s] = round(float(val), 2) if val and not pd.isna(val) else None
        return prices
    except Exception:
        return {s: None for s in symbols}


# ── Option Chain ─────────────────────────────────────────

def get_option_chain(symbol):
    """
    Fetch full option chain from NSE for a given symbol.
    Returns the raw JSON dict from NSE, or None on failure.
    """
    session = _get_nse_session()
    if session is None:
        return None
    try:
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol.upper()}"
        resp = session.get(url, headers=NSE_HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def get_expiry_dates(symbol):
    """Return list of available expiry date strings for a symbol."""
    data = get_option_chain(symbol)
    if data and "records" in data:
        return data["records"].get("expiryDates", [])
    return []


def get_atm_premiums(symbol, expiry=None):
    """
    Returns dict with keys:
      spot_price, atm_strike, call_premium, put_premium,
      call_pct, put_pct, expiry_date
    Returns None on failure.
    """
    data = get_option_chain(symbol)
    if not data:
        return None

    records = data.get("records", {})
    spot_price = records.get("underlyingValue")
    expiry_dates = records.get("expiryDates", [])

    if not spot_price or not expiry_dates:
        return None

    # Use nearest expiry if none specified
    target_expiry = expiry or expiry_dates[0]

    options = [
        r for r in records.get("data", [])
        if r.get("expiryDate") == target_expiry
    ]

    if not options:
        return None

    # Find ATM strike (closest to spot)
    strikes = [r["strikePrice"] for r in options if "strikePrice" in r]
    if not strikes:
        return None

    atm_strike = min(strikes, key=lambda x: abs(x - spot_price))

    call_premium = None
    put_premium = None
    for r in options:
        if r.get("strikePrice") == atm_strike:
            if "CE" in r:
                call_premium = r["CE"].get("lastPrice")
            if "PE" in r:
                put_premium = r["PE"].get("lastPrice")

    call_pct = round(call_premium / spot_price * 100, 2) if call_premium else None
    put_pct = round(put_premium / spot_price * 100, 2) if put_premium else None

    return {
        "symbol": symbol.upper(),
        "spot_price": spot_price,
        "atm_strike": atm_strike,
        "call_premium": call_premium,
        "put_premium": put_premium,
        "call_pct": call_pct,
        "put_pct": put_pct,
        "expiry_date": target_expiry,
    }


def get_option_premium(symbol, strike, expiry, option_type):
    """
    Get last traded price for a specific option contract.
    option_type: 'call' or 'put'
    Returns float or None.
    """
    data = get_option_chain(symbol)
    if not data:
        return None

    records = data.get("records", {}).get("data", [])
    key = "CE" if option_type.lower() == "call" else "PE"

    for r in records:
        if r.get("strikePrice") == strike and r.get("expiryDate") == expiry:
            return r.get(key, {}).get("lastPrice")
    return None


# ── F&O Stock List ────────────────────────────────────────

def get_fo_stocks():
    """
    Fetch the list of all NSE F&O-eligible stocks.
    Returns list of symbol strings.
    Falls back to hardcoded list if API fails.
    """
    session = _get_nse_session()
    if session:
        try:
            url = "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"
            resp = session.get(url, headers=NSE_HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                symbols = [
                    item["symbol"] for item in data.get("data", [])
                    if item.get("symbol") not in ("NIFTY 50", "")
                ]
                if symbols:
                    return sorted(symbols)
        except Exception:
            pass

    # Fallback: hardcoded major F&O stocks
    return sorted([
        "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "WIPRO", "SBIN",
        "TATAMOTORS", "AXISBANK", "BAJFINANCE", "BAJAJFINSV", "KOTAKBANK",
        "HINDUNILVR", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO",
        "POWERGRID", "NTPC", "ONGC", "COALINDIA", "ADANIENT", "ADANIPORTS",
        "TATASTEEL", "JSWSTEEL", "HINDALCO", "BHARTIARTL", "TECHM", "HCLTECH",
        "LTIM", "DIVISLAB", "DRREDDY", "CIPLA", "APOLLOHOSP", "SBILIFE",
        "HDFCLIFE", "ICICIPRULI", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO",
        "M&M", "TATACONSUM", "ITC", "BRITANNIA", "PIDILITIND", "GRASIM",
        "SHREECEM", "ACC", "AMBUJACEM", "INDUSINDBK", "FEDERALBNK", "BANDHANBNK",
        "PNB", "BANKBARODA", "CANBK", "NAUKRI", "ZOMATO", "LT", "NESTLEIND",
        "VEDL", "SAIL", "NMDC", "BHEL", "HAL", "BEL", "IRCTC", "DMART",
        "BERGEPAINT", "MPHASIS", "COFORGE", "PERSISTENT",
    ])


# ── Lot Sizes ─────────────────────────────────────────────
# These change every 6 months (NSE revises in April and October).
# Last updated: April 2025. Update when NSE publishes new lot sizes.

LOT_SIZES = {
    "RELIANCE": 250, "TCS": 150, "INFY": 400, "HDFCBANK": 550,
    "ICICIBANK": 700, "WIPRO": 1500, "SBIN": 1500, "TATAMOTORS": 1425,
    "AXISBANK": 625, "BAJFINANCE": 125, "BAJAJFINSV": 125, "KOTAKBANK": 400,
    "HINDUNILVR": 300, "ASIANPAINT": 200, "MARUTI": 100, "SUNPHARMA": 700,
    "TITAN": 375, "ULTRACEMCO": 100, "POWERGRID": 2700, "NTPC": 2250,
    "ONGC": 1975, "COALINDIA": 4200, "ADANIENT": 625, "ADANIPORTS": 625,
    "TATASTEEL": 5500, "JSWSTEEL": 900, "HINDALCO": 1400, "BHARTIARTL": 475,
    "TECHM": 600, "HCLTECH": 700, "LTIM": 150, "DIVISLAB": 200,
    "DRREDDY": 125, "CIPLA": 650, "APOLLOHOSP": 125, "SBILIFE": 750,
    "HDFCLIFE": 1100, "ICICIPRULI": 1500, "BAJAJ-AUTO": 250, "EICHERMOT": 175,
    "HEROMOTOCO": 300, "M&M": 700, "TATACONSUM": 1100, "ITC": 3200,
    "BRITANNIA": 200, "PIDILITIND": 500, "GRASIM": 475, "SHREECEM": 25,
    "ACC": 500, "AMBUJACEM": 2300, "INDUSINDBK": 500, "FEDERALBNK": 5000,
    "BANDHANBNK": 5000, "PNB": 8000, "BANKBARODA": 5850, "CANBK": 3800,
    "NAUKRI": 125, "ZOMATO": 5625, "LT": 300, "NESTLEIND": 50,
    "VEDL": 2000, "SAIL": 7000, "NMDC": 4500, "BHEL": 4500, "HAL": 150,
    "BEL": 3650, "IRCTC": 875, "DMART": 75, "BERGEPAINT": 1100,
    "MPHASIS": 200, "COFORGE": 200, "PERSISTENT": 125,
}


def get_lot_size(symbol):
    """Return lot size for a symbol. Defaults to 1 if unknown."""
    return LOT_SIZES.get(symbol.upper(), 1)
