"""
Database module — Supabase REST API backend.
Uses plain HTTP requests (no supabase client package needed).
"""

from datetime import date
import requests
from modules.config import get


def _headers():
    key = get("SUPABASE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _url(table):
    return f"{get('SUPABASE_URL')}/rest/v1/{table}"


def _get(table, params=None):
    r = requests.get(_url(table), headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()


def _post(table, data):
    r = requests.post(_url(table), headers=_headers(), json=data)
    r.raise_for_status()
    return r.json()


def _patch(table, match: dict, data: dict):
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.patch(_url(table), headers=_headers(), params=params, json=data)
    r.raise_for_status()


def _delete(table, match: dict):
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.delete(_url(table), headers=_headers(), params=params)
    r.raise_for_status()


def init_db():
    """No-op: tables are created via Supabase SQL editor."""
    pass


# ── Holdings ──────────────────────────────────────────────

def add_holding(symbol, quantity, cost_price, date_added, notes=""):
    _post("holdings", {
        "symbol": symbol.upper(),
        "quantity": quantity,
        "cost_price": cost_price,
        "date_added": str(date_added),
        "notes": notes,
    })


def get_holdings():
    return _get("holdings", params={"order": "symbol.asc"})


def update_holding(holding_id, quantity, cost_price, notes):
    _patch("holdings", {"id": holding_id}, {
        "quantity": quantity,
        "cost_price": cost_price,
        "notes": notes,
    })


def delete_holding(holding_id):
    _delete("holdings", {"id": holding_id})


def bulk_insert_holdings(rows):
    records = [
        {
            "symbol": r["symbol"].upper(),
            "quantity": r["quantity"],
            "cost_price": r["cost_price"],
            "date_added": str(r.get("date_added", date.today())),
            "notes": r.get("notes", ""),
        }
        for r in rows
    ]
    _post("holdings", records)


# ── Trades ────────────────────────────────────────────────

def add_trade(symbol, trade_type, strike_price, expiry_date, premium_received,
              quantity, lot_size, trade_date, notes="", direction="sell"):
    _post("trades", {
        "symbol": symbol.upper(),
        "trade_type": trade_type.lower(),
        "direction": direction.lower(),
        "strike_price": strike_price,
        "expiry_date": str(expiry_date),
        "premium_received": premium_received,
        "quantity": quantity,
        "lot_size": lot_size,
        "trade_date": str(trade_date),
        "notes": notes,
    })


def get_trades(status=None, symbol=None):
    params = {"order": "trade_date.desc"}
    if status:
        params["status"] = f"eq.{status}"
    if symbol:
        params["symbol"] = f"eq.{symbol.upper()}"
    return _get("trades", params=params)


def close_trade(trade_id, close_price, close_date):
    _patch("trades", {"id": trade_id}, {
        "status": "closed",
        "close_price": close_price,
        "close_date": str(close_date),
    })


def mark_trade_exercised(trade_id):
    _patch("trades", {"id": trade_id}, {"status": "exercised"})


def mark_trade_expired(trade_id):
    _patch("trades", {"id": trade_id}, {"status": "expired"})


def delete_trade(trade_id):
    _delete("trades", {"id": trade_id})


def bulk_insert_trades(rows):
    records = [
        {
            "symbol": r["symbol"].upper(),
            "trade_type": r["trade_type"].lower(),
            "direction": r.get("direction", "sell").lower(),
            "strike_price": r["strike_price"],
            "expiry_date": str(r["expiry_date"]),
            "premium_received": r["premium_received"],
            "quantity": r["quantity"],
            "lot_size": r["lot_size"],
            "trade_date": str(r["trade_date"]),
            "notes": r.get("notes", ""),
        }
        for r in rows
    ]
    _post("trades", records)


# ── Watchlist ─────────────────────────────────────────────

def add_to_watchlist(symbol):
    # upsert via Prefer header
    h = {**_headers(), "Prefer": "resolution=merge-duplicates,return=representation"}
    r = requests.post(_url("watchlist"), headers=h, json={"symbol": symbol.upper()})
    r.raise_for_status()


def get_watchlist():
    data = _get("watchlist", params={"order": "symbol.asc"})
    return [r["symbol"] for r in data]


def remove_from_watchlist(symbol):
    _delete("watchlist", {"symbol": symbol.upper()})


# ── Equity Trades ─────────────────────────────────────────

def add_equity_trade(symbol, quantity, buy_price, sell_price, pnl, trade_date, notes=""):
    _post("equity_trades", {
        "symbol": symbol.upper(),
        "quantity": quantity,
        "buy_price": buy_price,
        "sell_price": sell_price,
        "pnl": pnl,
        "trade_date": str(trade_date),
        "notes": notes,
    })


def get_equity_trades():
    return _get("equity_trades", params={"order": "trade_date.desc"})


# ── Alert Settings ────────────────────────────────────────

def get_alert_settings():
    data = _get("alert_settings", params={"id": "eq.1"})
    return data[0] if data else {}


def save_alert_settings(email, risk_threshold_pct, days_to_expiry_alert, alerts_enabled):
    _patch("alert_settings", {"id": 1}, {
        "email": email,
        "risk_threshold_pct": risk_threshold_pct,
        "days_to_expiry_alert": days_to_expiry_alert,
        "alerts_enabled": int(alerts_enabled),
    })
