from datetime import date, datetime


def holding_pnl(cost_price, current_price, quantity):
    """Returns (pnl_amount, pnl_pct)"""
    invested = cost_price * quantity
    current = current_price * quantity
    pnl = current - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
    return round(pnl, 2), round(pnl_pct, 2)


def trade_pnl(premium, close_or_current_premium, quantity, lot_size, direction="sell"):
    """
    Calculate P&L for an options trade.

    Sell (short): profit = premium received - current/close premium
      - Expires worthless (close=0) → max profit = full premium
      - Bought back at close price → profit = received - buyback cost

    Buy (long): profit = current/close premium - premium paid
      - Rises in value → profit
      - Falls to zero → full loss

    Returns (pnl_amount, pnl_pct).
    """
    total_premium = premium * quantity * lot_size
    close_total = (close_or_current_premium or 0) * quantity * lot_size

    if direction == "buy":
        pnl = close_total - total_premium
        pnl_pct = (pnl / total_premium * 100) if total_premium > 0 else 0.0
    else:  # sell (default)
        pnl = total_premium - close_total
        pnl_pct = (pnl / total_premium * 100) if total_premium > 0 else 0.0

    return round(pnl, 2), round(pnl_pct, 2)


def is_call_sold_this_month(symbol, open_trades):
    """Check if a call has been sold for this symbol in the current month."""
    today = date.today()
    for t in open_trades:
        if (t["symbol"] == symbol.upper()
                and t["trade_type"] == "call"
                and t["status"] == "open"):
            expiry = datetime.strptime(t["expiry_date"], "%Y-%m-%d").date()
            if expiry.year == today.year and expiry.month == today.month:
                return True
    return False


def get_open_opportunities(holdings, open_trades):
    """Return holdings that have no call sold for the current month."""
    return [h for h in holdings if not is_call_sold_this_month(h["symbol"], open_trades)]


def is_at_risk(trade, current_spot_price, threshold_pct=2.0):
    """
    A short option is 'at risk' when spot is within threshold_pct of strike.
    - Call: at risk when spot >= strike * (1 - threshold_pct/100)  i.e. approaching from below
    - Put:  at risk when spot <= strike * (1 + threshold_pct/100)  i.e. approaching from above
    Returns (bool, distance_pct)
    """
    strike = trade["strike_price"]
    if current_spot_price is None or current_spot_price == 0:
        return False, None

    distance_pct = abs(current_spot_price - strike) / strike * 100

    if trade["trade_type"] == "call":
        at_risk = current_spot_price >= strike * (1 - threshold_pct / 100)
    else:  # put
        at_risk = current_spot_price <= strike * (1 + threshold_pct / 100)

    return at_risk, round(distance_pct, 2)


def is_expiry_near(expiry_date_str, days_threshold=5):
    """Check if expiry is within days_threshold days from today."""
    expiry = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
    days_left = (expiry - date.today()).days
    return days_left <= days_threshold, days_left


def monthly_summary(trades):
    """
    Returns a list of dicts: [{month, year, total_premium, realised_pnl, open_count, closed_count}]
    sorted by year/month descending.
    """
    from collections import defaultdict
    summary = defaultdict(lambda: {"premium_received": 0, "realised_pnl": 0, "open": 0, "closed": 0, "exercised": 0, "expired": 0})

    for t in trades:
        expiry_date = datetime.strptime(t["expiry_date"], "%Y-%m-%d").date()
        key = (expiry_date.year, expiry_date.month)
        premium = t["premium_received"] * t["quantity"] * t["lot_size"]
        summary[key]["premium_received"] += premium
        summary[key][t["status"]] += 1

        if t["status"] in ("closed", "expired", "exercised"):
            close_p = t.get("close_price") or 0
            pnl, _ = trade_pnl(t["premium_received"], close_p, t["quantity"], t["lot_size"],
                                direction=t.get("direction", "sell"))
            summary[key]["realised_pnl"] += pnl

    result = []
    for (year, month), data in sorted(summary.items(), reverse=True):
        result.append({
            "Year": year,
            "Month": datetime(year, month, 1).strftime("%B"),
            "Premium Collected (₹)": round(data["premium_received"], 2),
            "Realised P&L (₹)": round(data["realised_pnl"], 2),
            "Open": data["open"],
            "Closed": data["closed"],
            "Expired": data["expired"],
            "Exercised": data["exercised"],
        })
    return result
