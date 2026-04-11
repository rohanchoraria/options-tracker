"""
Upstox API v2 integration.
- OAuth 2.0 login flow
- Option chain data (replaces NSE scraping)
- All functions take access_token as parameter — stored in st.session_state by app.py
"""

import requests
from modules.config import get

UPSTOX_BASE = "https://api.upstox.com/v2"
REDIRECT_URI = "http://127.0.0.1:8501"

# ── Instrument Keys ───────────────────────────────────────
# NSE F&O symbol → Upstox instrument key (NSE_EQ|ISIN format)
# ISINs are permanent and don't change.

INSTRUMENT_KEYS = {
    "RELIANCE":   "NSE_EQ|INE002A01018",
    "TCS":        "NSE_EQ|INE467B01029",
    "INFY":       "NSE_EQ|INE009A01021",
    "HDFCBANK":   "NSE_EQ|INE040A01034",
    "ICICIBANK":  "NSE_EQ|INE090A01021",
    "WIPRO":      "NSE_EQ|INE075A01022",
    "SBIN":       "NSE_EQ|INE062A01020",
    "TATAMOTORS": "NSE_EQ|INE155A01022",
    "AXISBANK":   "NSE_EQ|INE238A01034",
    "BAJFINANCE": "NSE_EQ|INE296A01024",
    "BAJAJFINSV": "NSE_EQ|INE918I01026",
    "KOTAKBANK":  "NSE_EQ|INE237A01028",
    "HINDUNILVR": "NSE_EQ|INE030A01027",
    "ASIANPAINT": "NSE_EQ|INE021A01026",
    "MARUTI":     "NSE_EQ|INE585B01010",
    "SUNPHARMA":  "NSE_EQ|INE044A01036",
    "TITAN":      "NSE_EQ|INE280A01028",
    "ULTRACEMCO": "NSE_EQ|INE481G01011",
    "POWERGRID":  "NSE_EQ|INE752E01010",
    "NTPC":       "NSE_EQ|INE733E01010",
    "ONGC":       "NSE_EQ|INE213A01029",
    "COALINDIA":  "NSE_EQ|INE522F01014",
    "ADANIENT":   "NSE_EQ|INE423A01024",
    "ADANIPORTS": "NSE_EQ|INE742F01042",
    "TATASTEEL":  "NSE_EQ|INE081A01020",
    "JSWSTEEL":   "NSE_EQ|INE019A01038",
    "HINDALCO":   "NSE_EQ|INE038A01020",
    "BHARTIARTL": "NSE_EQ|INE397D01024",
    "TECHM":      "NSE_EQ|INE669C01036",
    "HCLTECH":    "NSE_EQ|INE860A01027",
    "LTIM":       "NSE_EQ|INE214T01019",
    "DIVISLAB":   "NSE_EQ|INE361B01024",
    "DRREDDY":    "NSE_EQ|INE089A01031",
    "CIPLA":      "NSE_EQ|INE059A01026",
    "APOLLOHOSP": "NSE_EQ|INE437A01024",
    "SBILIFE":    "NSE_EQ|INE123W01016",
    "HDFCLIFE":   "NSE_EQ|INE795G01014",
    "ICICIPRULI": "NSE_EQ|INE726G01019",
    "BAJAJ-AUTO": "NSE_EQ|INE917I01010",
    "EICHERMOT":  "NSE_EQ|INE066A01021",
    "HEROMOTOCO": "NSE_EQ|INE158A01026",
    "M&M":        "NSE_EQ|INE101A01026",
    "TATACONSUM": "NSE_EQ|INE192A01025",
    "ITC":        "NSE_EQ|INE154A01025",
    "BRITANNIA":  "NSE_EQ|INE216A01030",
    "PIDILITIND": "NSE_EQ|INE318A01026",
    "GRASIM":     "NSE_EQ|INE047A01021",
    "SHREECEM":   "NSE_EQ|INE070A01015",
    "ACC":        "NSE_EQ|INE012A01025",
    "AMBUJACEM":  "NSE_EQ|INE079A01024",
    "INDUSINDBK": "NSE_EQ|INE095A01012",
    "FEDERALBNK": "NSE_EQ|INE171A01029",
    "BANDHANBNK": "NSE_EQ|INE545U01014",
    "PNB":        "NSE_EQ|INE160A01022",
    "BANKBARODA": "NSE_EQ|INE028A01039",
    "CANBK":      "NSE_EQ|INE476A01014",
    "NAUKRI":     "NSE_EQ|INE663F01024",
    "ZOMATO":     "NSE_EQ|INE758T01015",
    "LT":         "NSE_EQ|INE018A01030",
    "NESTLEIND":  "NSE_EQ|INE239A01016",
    "VEDL":       "NSE_EQ|INE205A01025",
    "SAIL":       "NSE_EQ|INE114A01011",
    "NMDC":       "NSE_EQ|INE584A01023",
    "BHEL":       "NSE_EQ|INE257A01026",
    "HAL":        "NSE_EQ|INE066F01020",
    "BEL":        "NSE_EQ|INE263A01024",
    "IRCTC":      "NSE_EQ|INE335Y01020",
    "DMART":      "NSE_EQ|INE192R01011",
    "BERGEPAINT": "NSE_EQ|INE463A01038",
    "MPHASIS":    "NSE_EQ|INE356A01018",
    "COFORGE":    "NSE_EQ|INE591G01017",
    "PERSISTENT": "NSE_EQ|INE262H01021",

    # Banking & Finance
    "IDFCFIRSTB": "NSE_EQ|INE818H01020",
    "SBICARD":    "NSE_EQ|INE018E01016",
    "HDFCAMC":    "NSE_EQ|INE127D01025",
    "MUTHOOTFIN": "NSE_EQ|INE414G01012",
    "CHOLAFIN":   "NSE_EQ|INE121A01024",
    "LICHSGFIN":  "NSE_EQ|INE115A01026",
    "MANAPPURAM": "NSE_EQ|INE522D01027",
    "SHRIRAMFIN": "NSE_EQ|INE721A01013",
    "ABCAPITAL":  "NSE_EQ|INE674K01013",
    "PFC":        "NSE_EQ|INE134E01011",
    "RECLTD":     "NSE_EQ|INE020B01018",
    "MCX":        "NSE_EQ|INE745G01035",
    "MFSL":       "NSE_EQ|INE583A01010",
    "NAM-INDIA":  "NSE_EQ|INE136B01020",
    "UJJIVANSFB": "NSE_EQ|INE334L01012",
    "CAMS":       "NSE_EQ|INE596I01012",

    # IT
    "LTTS":       "NSE_EQ|INE010V01017",
    "OFSS":       "NSE_EQ|INE881D01027",

    # Energy & Utilities
    "BPCL":       "NSE_EQ|INE029A01011",
    "IOC":        "NSE_EQ|INE242A01010",
    "GAIL":       "NSE_EQ|INE129A01019",
    "PETRONET":   "NSE_EQ|INE347G01014",
    "IGL":        "NSE_EQ|INE203G01027",
    "MGL":        "NSE_EQ|INE558L01010",
    "TATAPOWER":  "NSE_EQ|INE245A01021",
    "TORNTPOWER": "NSE_EQ|INE813H01021",
    "OIL":        "NSE_EQ|INE274J01014",
    "ADANIGREEN": "NSE_EQ|INE364U01010",
    "NHPC":       "NSE_EQ|INE848E01016",

    # Pharma & Healthcare
    "LUPIN":      "NSE_EQ|INE326A01037",
    "AUROPHARMA": "NSE_EQ|INE406A01037",
    "BIOCON":     "NSE_EQ|INE376G01013",
    "GLENMARK":   "NSE_EQ|INE935A01035",
    "TORNTPHARM": "NSE_EQ|INE685A01028",
    "ZYDUSLIFE":  "NSE_EQ|INE010B01027",
    "LALPATHLAB": "NSE_EQ|INE600L01024",
    "SYNGENE":    "NSE_EQ|INE398R01022",
    "GRANULES":   "NSE_EQ|INE101D01020",
    "NAVINFLUOR": "NSE_EQ|INE048G01026",

    # Auto & Auto Ancillaries
    "TVSMOTOR":   "NSE_EQ|INE494B01023",
    "BALKRISIND": "NSE_EQ|INE787D01026",
    "ESCORTS":    "NSE_EQ|INE042A01014",
    "MOTHERSON":  "NSE_EQ|INE775A01035",
    "EXIDEIND":   "NSE_EQ|INE302A01020",
    "BOSCHLTD":   "NSE_EQ|INE323A01026",
    "SONACOMS":   "NSE_EQ|INE073K01018",

    # Consumer & FMCG
    "DABUR":      "NSE_EQ|INE016A01026",
    "MARICO":     "NSE_EQ|INE196A01026",
    "GODREJCP":   "NSE_EQ|INE102D01028",
    "UBL":        "NSE_EQ|INE686F01025",
    "BATAINDIA":  "NSE_EQ|INE176A01028",
    "COLPAL":     "NSE_EQ|INE259A01022",
    "PAGEIND":    "NSE_EQ|INE761H01022",
    "ABFRL":      "NSE_EQ|INE647O01011",
    "TRENT":      "NSE_EQ|INE849A01020",

    # Real Estate
    "DLF":        "NSE_EQ|INE271C01023",
    "GODREJPROP": "NSE_EQ|INE484J01027",
    "OBEROIRLTY": "NSE_EQ|INE093I01010",
    "PHOENIXLTD": "NSE_EQ|INE484A01027",
    "PRESTIGE":   "NSE_EQ|INE811K01011",

    # Industrials & Capital Goods
    "SIEMENS":    "NSE_EQ|INE003A01024",
    "HAVELLS":    "NSE_EQ|INE176B01034",
    "VOLTAS":     "NSE_EQ|INE226A01021",
    "CROMPTON":   "NSE_EQ|INE074I01028",
    "POLYCAB":    "NSE_EQ|INE455K01017",
    "CONCOR":     "NSE_EQ|INE111A01025",
    "CUMMINSIND": "NSE_EQ|INE298A01020",
    "ABB":        "NSE_EQ|INE117A01022",

    # Chemicals & Specialty
    "DEEPAKNTR":  "NSE_EQ|INE288B01029",
    "SRF":        "NSE_EQ|INE647A01010",
    "UPL":        "NSE_EQ|INE628A01036",
    "PIIND":      "NSE_EQ|INE603J01030",
    "TATACHEM":   "NSE_EQ|INE092A01019",
    "ATUL":       "NSE_EQ|INE100A01010",

    # Telecom & Media
    "ZEEL":       "NSE_EQ|INE256A01028",
    "TATACOMM":   "NSE_EQ|INE151B01033",

    # Travel & Hospitality
    "INDIGO":     "NSE_EQ|INE646L01027",
    "INDHOTEL":   "NSE_EQ|INE053A01029",
    "PVRINOX":    "NSE_EQ|INE191H01014",

    # Metals & Mining
    "JINDALSTEL": "NSE_EQ|INE749A01030",
    "NATIONALUM": "NSE_EQ|INE139A01034",

    # Cement
    "RAMCOCEM":   "NSE_EQ|INE331A01037",

    # Diversified / Others
    "TATAELXSI":  "NSE_EQ|INE670A01012",
    "IRFC":       "NSE_EQ|INE053F01010",
    "SUPREMEIND": "NSE_EQ|INE195A01028",
    "KANSAINER":  "NSE_EQ|INE613A01014",
    "JUBLFOOD":   "NSE_EQ|INE797F01020",
    "GMRAIRPORT": "NSE_EQ|INE776C01039",

    # Indices (for option chain lookups)
    "NIFTY":      "NSE_INDEX|Nifty 50",
    "BANKNIFTY":  "NSE_INDEX|Nifty Bank",
    "FINNIFTY":   "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|Nifty Midcap Select",
}


# ── OAuth ─────────────────────────────────────────────────

def get_auth_url():
    """Return the Upstox OAuth authorization URL to redirect the user to."""
    api_key = get("UPSTOX_API_KEY")
    return (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?client_id={api_key}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
    )


def exchange_code(auth_code):
    """
    Exchange the OAuth authorization code for an access token.
    Returns access_token string or None on failure.
    """
    try:
        r = requests.post(
            f"{UPSTOX_BASE}/login/authorization/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "code": auth_code,
                "client_id": get("UPSTOX_API_KEY"),
                "client_secret": get("UPSTOX_API_SECRET"),
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception:
        pass
    return None


# ── API Helpers ───────────────────────────────────────────

def _headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


def get_instrument_key(symbol):
    return INSTRUMENT_KEYS.get(symbol.upper())


# ── Option Chain ──────────────────────────────────────────

def get_expiry_dates(symbol, access_token):
    """Return sorted list of expiry date strings (YYYY-MM-DD) for a symbol."""
    key = get_instrument_key(symbol)
    if not key:
        return []
    try:
        r = requests.get(
            f"{UPSTOX_BASE}/option/contract",
            headers=_headers(access_token),
            params={"instrument_key": key},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            return sorted(set(item["expiry"] for item in data))
    except Exception:
        pass
    return []


def get_option_chain(symbol, access_token, expiry_date=None):
    """
    Fetch raw option chain data for a symbol.
    Returns list of strike-level dicts or None.
    Each item has: strike_price, underlying_spot_price,
                   call_options.market_data.ltp, put_options.market_data.ltp
    """
    key = get_instrument_key(symbol)
    if not key:
        return None

    if not expiry_date:
        expiries = get_expiry_dates(symbol, access_token)
        if not expiries:
            return None
        expiry_date = expiries[0]

    try:
        r = requests.get(
            f"{UPSTOX_BASE}/option/chain",
            headers=_headers(access_token),
            params={"instrument_key": key, "expiry_date": expiry_date},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception:
        pass
    return None


def get_atm_premiums(symbol, access_token, expiry_date=None):
    """
    Returns dict with keys matching market_data.get_atm_premiums():
      symbol, spot_price, atm_strike, call_premium, put_premium,
      call_pct, put_pct, expiry_date
    Returns None on failure.
    """
    if not expiry_date:
        expiries = get_expiry_dates(symbol, access_token)
        if not expiries:
            return None
        expiry_date = expiries[0]

    chain = get_option_chain(symbol, access_token, expiry_date)
    if not chain:
        return None

    # Get spot price
    spot_price = next(
        (item["underlying_spot_price"] for item in chain if item.get("underlying_spot_price")),
        None
    )
    if not spot_price:
        return None

    # Find ATM strike
    strikes = [item["strike_price"] for item in chain]
    atm_strike = min(strikes, key=lambda x: abs(x - spot_price))

    call_premium = None
    put_premium = None
    for item in chain:
        if item.get("strike_price") == atm_strike:
            call_premium = item.get("call_options", {}).get("market_data", {}).get("ltp")
            put_premium = item.get("put_options", {}).get("market_data", {}).get("ltp")
            break

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
        "expiry_date": expiry_date,
    }


def get_option_premium(symbol, strike, expiry_date, option_type, access_token):
    """Get LTP for a specific option contract. Returns float or None."""
    chain = get_option_chain(symbol, access_token, expiry_date)
    if not chain:
        return None
    key = "call_options" if option_type.lower() == "call" else "put_options"
    for item in chain:
        if item.get("strike_price") == strike:
            return item.get(key, {}).get("market_data", {}).get("ltp")
    return None
