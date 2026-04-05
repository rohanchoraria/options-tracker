import sqlite3
import os
from datetime import date

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(_DATA_DIR, "options_tracker.db")


def get_connection():
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            cost_price REAL NOT NULL,
            date_added TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            trade_type TEXT NOT NULL,
            strike_price REAL NOT NULL,
            expiry_date TEXT NOT NULL,
            premium_received REAL NOT NULL,
            quantity INTEGER NOT NULL,
            lot_size INTEGER NOT NULL,
            trade_date TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            close_price REAL,
            close_date TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            email TEXT,
            risk_threshold_pct REAL DEFAULT 2.0,
            days_to_expiry_alert INTEGER DEFAULT 5,
            alerts_enabled INTEGER DEFAULT 1
        )
    """)

    # Insert default alert settings if not present
    c.execute("INSERT OR IGNORE INTO alert_settings (id) VALUES (1)")

    conn.commit()
    conn.close()


# ── Holdings ──────────────────────────────────────────────

def add_holding(symbol, quantity, cost_price, date_added, notes=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO holdings (symbol, quantity, cost_price, date_added, notes) VALUES (?, ?, ?, ?, ?)",
        (symbol.upper(), quantity, cost_price, str(date_added), notes)
    )
    conn.commit()
    conn.close()


def get_holdings():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM holdings ORDER BY symbol").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_holding(holding_id, quantity, cost_price, notes):
    conn = get_connection()
    conn.execute(
        "UPDATE holdings SET quantity=?, cost_price=?, notes=? WHERE id=?",
        (quantity, cost_price, notes, holding_id)
    )
    conn.commit()
    conn.close()


def delete_holding(holding_id):
    conn = get_connection()
    conn.execute("DELETE FROM holdings WHERE id=?", (holding_id,))
    conn.commit()
    conn.close()


def bulk_insert_holdings(rows):
    """rows: list of dicts with keys symbol, quantity, cost_price, date_added, notes"""
    conn = get_connection()
    for r in rows:
        conn.execute(
            "INSERT INTO holdings (symbol, quantity, cost_price, date_added, notes) VALUES (?, ?, ?, ?, ?)",
            (r["symbol"].upper(), r["quantity"], r["cost_price"], str(r.get("date_added", date.today())), r.get("notes", ""))
        )
    conn.commit()
    conn.close()


# ── Trades ────────────────────────────────────────────────

def add_trade(symbol, trade_type, strike_price, expiry_date, premium_received, quantity, lot_size, trade_date, notes=""):
    conn = get_connection()
    conn.execute(
        """INSERT INTO trades
           (symbol, trade_type, strike_price, expiry_date, premium_received, quantity, lot_size, trade_date, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (symbol.upper(), trade_type.lower(), strike_price, str(expiry_date),
         premium_received, quantity, lot_size, str(trade_date), notes)
    )
    conn.commit()
    conn.close()


def get_trades(status=None, symbol=None):
    conn = get_connection()
    query = "SELECT * FROM trades WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    if symbol:
        query += " AND symbol=?"
        params.append(symbol.upper())
    query += " ORDER BY trade_date DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def close_trade(trade_id, close_price, close_date):
    conn = get_connection()
    conn.execute(
        "UPDATE trades SET status='closed', close_price=?, close_date=? WHERE id=?",
        (close_price, str(close_date), trade_id)
    )
    conn.commit()
    conn.close()


def mark_trade_exercised(trade_id):
    conn = get_connection()
    conn.execute("UPDATE trades SET status='exercised' WHERE id=?", (trade_id,))
    conn.commit()
    conn.close()


def mark_trade_expired(trade_id):
    conn = get_connection()
    conn.execute("UPDATE trades SET status='expired' WHERE id=?", (trade_id,))
    conn.commit()
    conn.close()


def delete_trade(trade_id):
    conn = get_connection()
    conn.execute("DELETE FROM trades WHERE id=?", (trade_id,))
    conn.commit()
    conn.close()


def bulk_insert_trades(rows):
    conn = get_connection()
    for r in rows:
        conn.execute(
            """INSERT INTO trades
               (symbol, trade_type, strike_price, expiry_date, premium_received, quantity, lot_size, trade_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["symbol"].upper(), r["trade_type"].lower(), r["strike_price"], str(r["expiry_date"]),
             r["premium_received"], r["quantity"], r["lot_size"], str(r["trade_date"]), r.get("notes", ""))
        )
    conn.commit()
    conn.close()


# ── Watchlist ─────────────────────────────────────────────

def add_to_watchlist(symbol):
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO watchlist (symbol) VALUES (?)", (symbol.upper(),))
    conn.commit()
    conn.close()


def get_watchlist():
    conn = get_connection()
    rows = conn.execute("SELECT symbol FROM watchlist ORDER BY symbol").fetchall()
    conn.close()
    return [r["symbol"] for r in rows]


def remove_from_watchlist(symbol):
    conn = get_connection()
    conn.execute("DELETE FROM watchlist WHERE symbol=?", (symbol.upper(),))
    conn.commit()
    conn.close()


# ── Alert Settings ────────────────────────────────────────

def get_alert_settings():
    conn = get_connection()
    row = conn.execute("SELECT * FROM alert_settings WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {}


def save_alert_settings(email, risk_threshold_pct, days_to_expiry_alert, alerts_enabled):
    conn = get_connection()
    conn.execute(
        """UPDATE alert_settings
           SET email=?, risk_threshold_pct=?, days_to_expiry_alert=?, alerts_enabled=?
           WHERE id=1""",
        (email, risk_threshold_pct, days_to_expiry_alert, int(alerts_enabled))
    )
    conn.commit()
    conn.close()
