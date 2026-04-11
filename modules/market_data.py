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
            # Step 1: hit homepage to get initial cookies
            session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
            time.sleep(1)
            # Step 2: hit the option chain page to set remaining cookies
            session.get(
                "https://www.nseindia.com/option-chain",
                headers={**NSE_HEADERS, "Referer": "https://www.nseindia.com"},
                timeout=10,
            )
            time.sleep(0.5)
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
        headers = {**NSE_HEADERS, "Referer": "https://www.nseindia.com/option-chain"}
        resp = session.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data:  # NSE sometimes returns empty {} — treat as failure
                return data
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
    # Last updated: April 2026 (source: NSE via optionperks.com)
    "360ONE": 500, "ABB": 125, "ABCAPITAL": 3100, "ADANIENSOL": 675,
    "ADANIENT": 309, "ADANIGREEN": 600, "ADANIPORTS": 475, "ADANIPOWER": 3550,
    "ALKEM": 125, "AMBER": 100, "AMBUJACEM": 1050, "ANGELONE": 2500,
    "APLAPOLLO": 350, "APOLLOHOSP": 125, "ASHOKLEY": 5000, "ASIANPAINT": 250,
    "ASTRAL": 425, "AUBANK": 1000, "AUROPHARMA": 550, "AXISBANK": 625,
    "BAJAJ-AUTO": 75, "BAJAJFINSV": 250, "BAJAJHLDNG": 50, "BAJFINANCE": 750,
    "BANDHANBNK": 3600, "BANKBARODA": 2925, "BANKINDIA": 5200, "BDL": 350,
    "BEL": 1425, "BHARATFORG": 500, "BHARTIARTL": 475, "BHEL": 2625,
    "BIOCON": 2500, "BLUESTARCO": 325, "BOSCHLTD": 25, "BPCL": 1975,
    "BRITANNIA": 125, "BSE": 375, "CAMS": 750, "CANBK": 6750,
    "CDSL": 475, "CGPOWER": 850, "CHOLAFIN": 625, "CIPLA": 375,
    "COALINDIA": 1350, "COCHINSHIP": 400, "COFORGE": 375, "COLPAL": 225,
    "CONCOR": 1250, "CROMPTON": 1800, "CUMMINSIND": 200, "DABUR": 1250,
    "DALBHARAT": 325, "DELHIVERY": 2075, "DIVISLAB": 100, "DIXON": 50,
    "DLF": 825, "DMART": 150, "DRREDDY": 625, "EICHERMOT": 100,
    "ETERNAL": 2425, "EXIDEIND": 1800, "FEDERALBNK": 5000, "FORCEMOT": 25,
    "FORTIS": 775, "GAIL": 3150, "GLENMARK": 375, "GMRAIRPORT": 6975,
    "GODREJCP": 500, "GODREJPROP": 275, "GRASIM": 250, "HAL": 150,
    "HAVELLS": 500, "HCLTECH": 350, "HDFCAMC": 300, "HDFCBANK": 550,
    "HDFCLIFE": 1100, "HEROMOTOCO": 150, "HINDALCO": 700, "HINDPETRO": 2025,
    "HINDUNILVR": 300, "HINDZINC": 1225, "HUDCO": 2775, "HYUNDAI": 275,
    "ICICIBANK": 700, "ICICIGI": 325, "ICICIPRULI": 925, "IDFCFIRSTB": 9275,
    "IEX": 3750, "INDHOTEL": 1000, "INDIANB": 1000, "INDIGO": 150,
    "INDUSINDBK": 700, "INDUSTOWER": 1700, "INFY": 400, "INOXWIND": 3575,
    "IOC": 4875, "IREDA": 3450, "IRFC": 4250, "ITC": 1600,
    "JINDALSTEL": 625, "JIOFIN": 2350, "JSWENERGY": 1000, "JSWSTEEL": 675,
    "JUBLFOOD": 1250, "KALYANKJIL": 1175, "KAYNES": 100, "KEI": 175,
    "KFINTECH": 500, "KOTAKBANK": 2000, "KPITTECH": 425, "LAURUSLABS": 850,
    "LICHSGFIN": 1000, "LICI": 700, "LODHA": 450, "LT": 175, "LTF": 2250,
    "LTM": 150, "LTIM": 150, "LUPIN": 425, "M&M": 200, "MANAPPURAM": 3000,
    "MANKIND": 225, "MARICO": 1200, "MARUTI": 50, "MAXHEALTH": 525,
    "MAZDOCK": 200, "MCX": 625, "MFSL": 400, "MOTHERSON": 6150,
    "MOTILALOFS": 775, "MPHASIS": 275, "MUTHOOTFIN": 275, "NAUKRI": 375,
    "NBCC": 6500, "NESTLEIND": 500, "NHPC": 6400, "NMDC": 6750,
    "NTPC": 1500, "NUVAMA": 500, "NYKAA": 3125, "OBEROIRLTY": 350,
    "OFSS": 75, "OIL": 1400, "ONGC": 2250, "PAGEIND": 15,
    "PATANJALI": 900, "PAYTM": 725, "PERSISTENT": 100, "PETRONET": 1900,
    "PFC": 1300, "PHOENIXLTD": 350, "PIDILITIND": 500, "PIIND": 175,
    "PNB": 8000, "PNBHOUSING": 650, "POLICYBZR": 350, "POLYCAB": 125,
    "POWERGRID": 1900, "PRESTIGE": 450, "RBLBANK": 3175, "RECLTD": 1400,
    "RELIANCE": 500, "RVNL": 1525, "SAIL": 4700, "SBICARD": 800,
    "SBILIFE": 375, "SBIN": 750, "SHREECEM": 25, "SHRIRAMFIN": 825,
    "SIEMENS": 175, "SOLARINDS": 50, "SONACOMS": 1225, "SRF": 200,
    "SUNPHARMA": 350, "SUPREMEIND": 175, "SUZLON": 9025, "SWIGGY": 1300,
    "TATACONSUM": 550, "TATAELXSI": 100, "TATAPOWER": 1450, "TATASTEEL": 5500,
    "TATATECH": 800, "TCS": 175, "TECHM": 600, "TIINDIA": 200,
    "TITAN": 175, "TORNTPHARM": 250, "TORNTPOWER": 425, "TRENT": 100,
    "TVSMOTOR": 175, "ULTRACEMCO": 50, "UNIONBANK": 4425, "UNITDSPR": 400,
    "UNOMINDA": 550, "UPL": 1355, "VBL": 1125, "VEDL": 1150,
    "VOLTAS": 375, "WAAREEENER": 175, "WIPRO": 3000, "ZYDUSLIFE": 900,
    "TATAMOTORS": 1000,
}


def get_lot_size(symbol):
    """Return lot size for a symbol. Defaults to 1 if unknown."""
    return LOT_SIZES.get(symbol.upper(), 1)
