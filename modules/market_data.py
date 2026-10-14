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


# ── Lot Sizes (static fallback — auto-refreshed live by _fetch_live_lot_sizes) ─
LOT_SIZES = {
    "360ONE": 500, "ABB": 125, "ABCAPITAL": 3100, "ADANIENSOL": 675,
    "ADANIENT": 309, "ADANIGREEN": 600, "ADANIPORTS": 475, "ADANIPOWER": 3550,
    "ALKEM": 125, "AMBER": 100, "AMBUJACEM": 1200, "ANANDRATHI": 250,
    "ANGELONE": 2500, "APLAPOLLO": 350, "APOLLOHOSP": 125, "ASHOKLEY": 5000,
    "ASIANPAINT": 250, "ASTRAL": 425, "ATHERENERG": 375, "AUBANK": 1000,
    "AUROPHARMA": 550, "AXISBANK": 625, "BAJAJ-AUTO": 75, "BAJAJFINSV": 300,
    "BAJAJHLDNG": 75, "BAJFINANCE": 750, "BANDHANBNK": 3600, "BANKBARODA": 2925,
    "BANKINDIA": 5200, "BDL": 425, "BEL": 1425, "BHARATFORG": 500,
    "BHARTIARTL": 475, "BHEL": 2625, "BIOCON": 2500, "BLUESTARCO": 325,
    "BOSCHLTD": 25, "BPCL": 1975, "BRITANNIA": 125, "BSE": 200,
    "CAMS": 825, "CANBK": 6750, "CDSL": 475, "CGPOWER": 850,
    "CHOLAFIN": 625, "CIPLA": 425, "COALINDIA": 1350, "COCHINSHIP": 400,
    "COFORGE": 475, "COLPAL": 275, "CONCOR": 1250, "CROMPTON": 2150,
    "CUMMINSIND": 200, "DABUR": 1250, "DELHIVERY": 2075, "DIVISLAB": 100,
    "DIXON": 50, "DLF": 950, "DMART": 150, "DRREDDY": 625,
    "EICHERMOT": 100, "ENRIN": 175, "ETERNAL": 2425, "FEDERALBNK": 2500,
    "FORCEMOT": 25, "FORTIS": 775, "GAIL": 3550, "GLENMARK": 375,
    "GMRAIRPORT": 6975, "GODFRYPHLP": 275, "GODREJCP": 500, "GODREJPROP": 325,
    "GRASIM": 250, "GVT&D": 125, "HAL": 150, "HAVELLS": 500,
    "HCLTECH": 400, "HDFCAMC": 300, "HDFCBANK": 650, "HDFCLIFE": 1100,
    "HEROMOTOCO": 150, "HINDALCO": 700, "HINDPETRO": 2025, "HINDUNILVR": 300,
    "HINDZINC": 1225, "HYUNDAI": 275, "ICICIBANK": 700, "ICICIGI": 325,
    "ICICIPRULI": 925, "IDEA": 71475, "IDFCFIRSTB": 9275, "IEX": 4350,
    "INDHOTEL": 1000, "INDIANB": 1000, "INDIGO": 150, "INDUSINDBK": 700,
    "INDUSTOWER": 1700, "INFY": 400, "INOXWIND": 6400, "IOC": 4875,
    "IREDA": 4525, "IRFC": 5425, "ITC": 1725, "JINDALSTEL": 625,
    "JIOFIN": 2350, "JSWENERGY": 1075, "JSWSTEEL": 675, "JUBLFOOD": 1250,
    "KALYANKJIL": 1350, "KAYNES": 150, "KEI": 175, "KFINTECH": 575,
    "KOTAKBANK": 2000, "KPITTECH": 775, "LAURUSLABS": 850, "LICHSGFIN": 1000,
    "LICI": 1400, "LODHA": 625, "LT": 175, "LTF": 2250,
    "LTM": 150, "LUPIN": 425, "M&M": 200, "MAHABANK": 6500,
    "MANAPPURAM": 3000, "MANKIND": 250, "MARICO": 1200, "MARUTI": 50,
    "MAXHEALTH": 525, "MAZDOCK": 225, "MCX": 225, "MFSL": 400,
    "MOTHERSON": 6150, "MOTILALOFS": 775, "MPHASIS": 275, "MUTHOOTFIN": 275,
    "NAM-INDIA": 625, "NATIONALUM": 1875, "NAUKRI": 550, "NBCC": 6500,
    "NESTLEIND": 500, "NHPC": 6950, "NMDC": 6750, "NTPC": 1500,
    "NYKAA": 3125, "OBEROIRLTY": 350, "OFSS": 100, "OIL": 1400,
    "ONGC": 2250, "PAGEIND": 20, "PATANJALI": 1075, "PAYTM": 725,
    "PERSISTENT": 125, "PETRONET": 1900, "PFC": 1300, "PGEL": 950,
    "PHOENIXLTD": 350, "PIDILITIND": 500, "PIIND": 175, "PNB": 8000,
    "PNBHOUSING": 650, "POLICYBZR": 350, "POLYCAB": 125, "POWERGRID": 1900,
    "POWERINDIA": 25, "PREMIERENE": 650, "PRESTIGE": 450, "RADICO": 150,
    "RBLBANK": 3175, "RECLTD": 1575, "RELIANCE": 500, "RVNL": 1925,
    "SAGILITY": 12000, "SAIL": 4700, "SBICARD": 800, "SBILIFE": 375,
    "SBIN": 750, "SHREECEM": 25, "SHRIRAMFIN": 825, "SIEMENS": 175,
    "SOLARINDS": 50, "SONACOMS": 1225, "SRF": 200, "SUNPHARMA": 350,
    "SUPREMEIND": 175, "SUZLON": 12700, "SWIGGY": 1825, "TATACONSUM": 550,
    "TATAELXSI": 125, "TATAPOWER": 1450, "TATASTEEL": 2750, "TCS": 225,
    "TECHM": 600, "TIINDIA": 200, "TITAN": 175, "TMPV": 1600,
    "TORNTPHARM": 125, "TRENT": 225, "TVSMOTOR": 175, "UJJIVANSFB": 8000,
    "ULTRACEMCO": 50, "UNIONBANK": 4425, "UNITDSPR": 400, "UNOMINDA": 550,
    "UPL": 1355, "VBL": 1275, "VEDL": 1150, "VMM": 4850,
    "VOLTAS": 375, "WAAREEENER": 175, "WIPRO": 3000, "YESBANK": 31100,
    "ZYDUSLIFE": 900,
    # historical — kept for trade P&L
    "DALBHARAT": 325, "EXIDEIND": 1800, "HUDCO": 2775, "LTIM": 150,
    "NUVAMA": 500, "TATATECH": 800, "TORNTPOWER": 425,
}


# ── Live lot-size fetch (auto-refreshes daily from NSE) ───────────────────────

_live_lot_sizes: dict = {}
_live_lot_sizes_ts: float = 0.0
_LIVE_LOT_TTL = 86400  # 24 hours


def _fetch_live_lot_sizes() -> dict:
    """
    Fetch current lot sizes from NSE fo_mktlots.csv.
    Returns {symbol: lot_size}. Falls back to hardcoded LOT_SIZES on failure.
    """
    global _live_lot_sizes, _live_lot_sizes_ts
    now = time.time()
    if _live_lot_sizes and (now - _live_lot_sizes_ts) < _LIVE_LOT_TTL:
        return _live_lot_sizes

    try:
        import io, csv as _csv
        session = _get_nse_session()
        if not session:
            raise RuntimeError("no session")
        r = session.get(
            "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv",
            headers=NSE_HEADERS, timeout=15,
        )
        r.raise_for_status()
        sizes = {}
        in_stocks = False
        for row in _csv.reader(io.StringIO(r.text)):
            if not row:
                continue
            if row[0].strip() == "Derivatives on Individual Securities":
                in_stocks = True
                continue
            sym = row[1].strip() if len(row) > 1 else ""
            lot = row[2].strip() if len(row) > 2 else ""
            if in_stocks and sym and lot.isdigit() and sym != "Symbol":
                sizes[sym] = int(lot)
        if sizes:
            _live_lot_sizes = sizes
            _live_lot_sizes_ts = now
            return sizes
    except Exception:
        pass

    return LOT_SIZES  # fallback


_HISTORICAL_SYMBOLS = frozenset(
    {"DALBHARAT", "EXIDEIND", "HUDCO", "LTIM", "NUVAMA", "TATATECH", "TORNTPOWER"}
)


def get_lot_size(symbol: str) -> int:
    """Return current lot size for a symbol. Defaults to 1 if unknown."""
    sym = symbol.upper()
    return _fetch_live_lot_sizes().get(sym) or LOT_SIZES.get(sym, 1)


def get_fo_stocks() -> list:
    """
    Return list of all active NSE F&O stock symbols.
    Uses live NSE master-quote API; falls back to live lot sizes keys.
    """
    session = _get_nse_session()
    if session:
        try:
            resp = session.get(
                "https://www.nseindia.com/api/master-quote",
                headers=NSE_HEADERS, timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return sorted(data)
        except Exception:
            pass
    sizes = _fetch_live_lot_sizes()
    return sorted(s for s in sizes if s not in _HISTORICAL_SYMBOLS)
