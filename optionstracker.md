# Options Tracker — Project Context for Claude

This document contains the full context of this project. If you are a new Claude instance picking this up, read this entire file before doing anything. Everything decided so far is here.

---

## What This App Is

A personal web app (Streamlit + Python) for an Indian stock market trader who:
- Sells **covered calls** on stocks he holds
- Sells **puts** on stocks he wants to own
- Trades on **NSE** (National Stock Exchange of India)
- Wants to track performance, monitor risk, and find new trade opportunities

---

## Tech Stack (Decided)

| Component | Choice | Reason |
|---|---|---|
| UI Framework | Streamlit (Python) | No frontend coding, fast to build, free hosting |
| Database | SQLite | Simple, file-based, no server needed |
| Live Data | NSE public API (via requests) → swap to broker API later | Works without API keys for now |
| Stock Prices | yfinance (.NS suffix) | Free, reliable for Indian stocks |
| Alerts | Email via Gmail SMTP | User prefers email over Telegram |
| Hosting | Streamlit Community Cloud (free) | Connect GitHub repo, zero config |

---

## Broker API (PENDING — Not Set Up Yet)

The user does not have a broker API set up yet. Current code uses:
- `yfinance` for stock prices
- NSE public API for option chains

When broker API is ready, replace calls in `modules/market_data.py`. Supported brokers:
- **Upstox API v2** (free) — recommended if user has Upstox account
- **Angel One SmartAPI** (free) — recommended if user has Angel One account
- **Zerodha Kite Connect** (₹2,000/month) — best developer experience

The user will only use the broker API for **data fetching**, not for placing trades.

---

## Email Alerts (PENDING — Not Configured Yet)

User wants email alerts (not Telegram). Setup needed:
1. User enables Gmail 2FA
2. User creates a Gmail App Password (16-char)
3. User fills `.env` file with credentials

See `.env.example` for required variables.

---

## App Structure — 3 Tabs

### Tab 1 — Portfolio

**Section A: Full Equity Holdings**
- All stocks the user holds
- Columns: Symbol, Quantity, Cost Price, Current Price, Current Value, Unrealised P&L (₹), Unrealised P&L (%)
- Overall portfolio value + total P&L at top
- Input: Manual form OR CSV upload OR broker API import

**Section B: Open Call Opportunities**
- Stocks from holdings where NO call has been sold for the current month
- Columns: Symbol, Quantity, Cost Price, Current Price
- Purpose: Reminder to sell a call on these

**Section C: Trade Log**
- All options trades entered (calls and puts sold)
- Columns: Symbol, Type (Call/Put), Strike, Expiry, Premium Received, Quantity (lots), Lot Size, Trade Date, Status, Close Price, P&L
- Monthly P&L summary view
- Input: Manual form OR CSV upload

### Tab 2 — Risk Monitor

- All open option positions with live premium prices
- Flags positions where spot price is within X% of strike (user-configurable threshold, default 2%)
- For calls: risk when spot rises toward strike
- For puts: risk when spot falls toward strike
- Auto-refresh every 60 seconds (toggle on/off)
- Alert settings panel: email address, risk threshold %, days-to-expiry alert
- "Send Test Email" button

### Tab 3 — Options Screener

- Fetches all ~180+ NSE F&O stocks on demand
- Shows: Symbol, Spot Price, ATM Strike, Call Premium, Put Premium, Call % of Spot, Put % of Spot
- Sortable by any column (especially Call % and Put %)
- Filterable: min premium %, expiry month
- "Refresh" button (takes ~30-60 seconds for full fetch)
- Personal watchlist: user marks stocks they care about, watchlist refreshes faster

---

## Database Schema

Tables in SQLite (`data/options_tracker.db`):

```sql
holdings (id, symbol, quantity, cost_price, date_added, notes)
trades (id, symbol, trade_type, strike_price, expiry_date, premium_received, quantity, lot_size, trade_date, status, close_price, close_date, notes)
watchlist (id, symbol, added_at)
alert_settings (id, email, risk_threshold_pct, days_to_expiry_alert, alerts_enabled)
```

Trade status values: `open`, `closed`, `exercised`, `expired`
Trade type values: `call`, `put`

---

## Indian Market Specifics

- Exchange: NSE (National Stock Exchange of India)
- Options style: European (can only exercise at expiry)
- Monthly expiry: Last Thursday of each month
- Market hours: 9:15 AM – 3:30 PM IST (Monday–Friday)
- Currency: INR (₹)
- F&O stocks: ~180+ stocks eligible for options trading
- Lot sizes: Each stock has a minimum lot size (e.g., Reliance = 250 shares per lot). These change every 6 months. See `modules/market_data.py` for the LOT_SIZES dictionary.

---

## User's Trading Style

- Sells **covered calls**: Owns the stock, sells call options against it to collect premium
- Sells **puts**: Sells put options on stocks he'd be happy to own at that price
- Trades monthly expiry cycles
- Indian market only (NSE)
- Not a high-frequency trader — 60-second data refresh is sufficient

---

## File Structure

```
options-tracker/
├── optionstracker.md            ← YOU ARE HERE. Read this first.
├── README.md                    ← Setup and run instructions
├── requirements.txt             ← Python dependencies
├── .env.example                 ← Environment variables template
├── .gitignore
├── app.py                       ← Main Streamlit app (3 tabs)
├── modules/
│   ├── __init__.py
│   ├── database.py              ← All SQLite DB operations
│   ├── market_data.py           ← NSE price & options data fetching
│   ├── calculations.py          ← P&L, risk, summary calculations
│   └── alerts.py                ← Email alert logic
├── data/                        ← SQLite DB lives here (gitignored)
│   └── .gitkeep
└── sample_data/
    ├── sample_holdings.csv      ← Template for holdings CSV import
    └── sample_trades.csv        ← Template for trades CSV import
```

---

## What Is Done

- [x] Full project structure created
- [x] Database schema and operations (`modules/database.py`)
- [x] Market data fetching via NSE API + yfinance (`modules/market_data.py`)
- [x] P&L and risk calculations (`modules/calculations.py`)
- [x] Email alerts (`modules/alerts.py`)
- [x] Full Streamlit app with all 3 tabs (`app.py`)
- [x] Sample CSV templates

## What Is Pending

- [ ] User to fill `.env` file with Gmail App Password
- [ ] User to set up broker API credentials (when ready) and update `modules/market_data.py`
- [ ] Deploy to Streamlit Community Cloud (push to GitHub, connect repo)
- [ ] Test with real data once broker API is connected

---

## How to Continue Building

1. Read this file fully
2. Read `app.py` to understand the current state of the UI
3. Read `modules/market_data.py` — this is where broker API integration will go
4. Check `TODO` comments in the code — they mark everything that needs broker API
5. Ask the user which broker they've set up, then implement accordingly

---

## Decisions Already Made (Do Not Re-discuss)

- Streamlit + Python (not React, not Flask)
- SQLite (not PostgreSQL — can migrate later if needed)
- Email alerts (not Telegram)
- 60-second auto-refresh (not WebSocket/tick data)
- NSE public API as placeholder until broker API is ready
- Streamlit Community Cloud for hosting (free)
- User trades only on NSE, monthly expiry cycles
- User uses the broker API for data only, not for placing trades
