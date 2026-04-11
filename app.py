"""
Options Tracker — Main Streamlit App
Design system: design_system_atlas.yaml (Mono)
Read optionstracker.md before making changes.
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
import time

import modules.database as db
import modules.market_data as market
import modules.calculations as calc
import modules.upstox as upstox
from modules.alerts import send_email, build_risk_alert_email, build_opportunity_alert_email


def _render_html(html):
    """Render raw HTML — uses st.html() if available, falls back to st.markdown."""
    try:
        st.html(html)
    except AttributeError:
        st.markdown(html, unsafe_allow_html=True)


# ── Page Config ───────────────────────────────────────────

st.set_page_config(page_title="Options Tracker", page_icon="📈", layout="wide")
db.init_db()

# ── Upstox OAuth Callback (must run before password gate) ─
_params = st.query_params
if "code" in _params and "upstox_token" not in st.session_state:
    with st.spinner("Connecting to Upstox..."):
        _token = upstox.exchange_code(_params["code"])
    if _token:
        st.session_state.upstox_token = _token
        st.session_state.authenticated = True
        st.query_params.clear()
        st.rerun()
    else:
        st.error("Upstox login failed — please try again.")
        st.query_params.clear()

# ── Password Gate ─────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.title("Options Tracker")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        from modules.config import get as _get_secret
        if pwd == _get_secret("APP_PASSWORD", ""):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

# ── Upstox Sidebar ────────────────────────────────────────
with st.sidebar:
    _render_html("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:500;
                letter-spacing:0.08em;text-transform:uppercase;color:#9CA3AF;
                margin-bottom:8px;">Live Data</div>
    """)

    if "upstox_token" in st.session_state:
        st.success("Upstox connected")
        if st.button("Disconnect", use_container_width=True):
            del st.session_state["upstox_token"]
            st.rerun()
    else:
        st.warning("Upstox not connected")
        st.caption("Connect to fetch live option premiums.")
        auth_url = upstox.get_auth_url()
        st.link_button("Login with Upstox", auth_url, use_container_width=True)

# ── Atlas Design System — CSS Injection ───────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

/* Base */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Headings → Space Grotesk */
h1, h2, h3 {
    font-family: 'Space Grotesk', sans-serif !important;
    letter-spacing: -0.02em;
    color: #111827;
}

/* App title */
h1 { font-size: 28px !important; font-weight: 700 !important; letter-spacing: -0.03em !important; }

/* Tab labels */
button[data-baseweb="tab"] p {
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 600 !important;
    font-size: 15px !important;
}

/* Metric labels */
[data-testid="stMetricLabel"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: #9CA3AF !important;
}

/* Metric values */
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    color: #111827 !important;
}

/* Metric delta */
[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
}

/* Dataframe */
[data-testid="stDataFrame"] th {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    background: #F9FAFB !important;
    text-align: center !important;
}
[data-testid="stDataFrame"] td {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
    text-align: center !important;
}
/* First column (stock name) stays left-aligned */
[data-testid="stDataFrame"] th:first-child,
[data-testid="stDataFrame"] td:first-child {
    text-align: left !important;
}

/* Divider */
hr { border-color: #E5E7EB !important; }

/* Expander */
[data-testid="stExpander"] summary {
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}

/* Info / warning / success boxes */
[data-testid="stAlert"] {
    font-family: 'Inter', sans-serif !important;
    border-radius: 4px !important;
}

/* Sidebar and inputs */
label { font-family: 'Inter', sans-serif !important; font-size: 14px !important; }
input, select, textarea {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
}

/* Caption */
[data-testid="stCaptionContainer"] p {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    color: #9CA3AF !important;
}
</style>
""", unsafe_allow_html=True)


# ── Atlas Helper Components ───────────────────────────────

def hero_bar(metrics):
    """
    Dark ink hero bar with large mono metrics.
    metrics: list of (label, value, color) — color is hex string.
    """
    n = len(metrics)
    items = ""
    for i, (label, value, color) in enumerate(metrics):
        border = "border-right:1px solid rgba(255,255,255,0.08);" if i < n - 1 else ""
        items += f"""
        <div style="flex:1;text-align:center;padding:0 20px;{border}">
            <div style="font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:500;
                        letter-spacing:0.1em;text-transform:uppercase;color:rgba(255,255,255,0.45);
                        margin-bottom:10px;">{label}</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:30px;font-weight:700;
                        letter-spacing:-0.02em;color:{color};">{value}</div>
        </div>"""
    _render_html(f"""
    <div style="background:#111827;border-radius:8px;padding:28px 16px;
                display:flex;align-items:center;margin-bottom:20px;">
        {items}
    </div>""")


def section_label(text):
    """Uppercase monospace section marker — the Atlas terminal look."""
    _render_html(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:500;
                letter-spacing:0.08em;text-transform:uppercase;color:#9CA3AF;
                margin-bottom:2px;margin-top:8px;">{text}</div>""")


def section_heading(text):
    """H3-style heading without Streamlit's anchor link."""
    _render_html(f"""
    <h3 style="font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:600;
               letter-spacing:-0.02em;color:#111827;margin:4px 0 16px 0;">{text}</h3>""")


def fmt_inr(amount):
    """Format a number as ₹ with Indian comma style."""
    if amount is None:
        return "—"
    return f"₹{amount:,.0f}"


def pnl_color(val):
    """Return Atlas semantic color for a P&L value."""
    if isinstance(val, (int, float)):
        return "#16A34A" if val >= 0 else "#DC2626"
    return "#111827"


def style_pnl_df(df, pnl_col="P&L (₹)", pct_col=None):
    """Apply green/red coloring to P&L columns in a dataframe styler."""
    def color_val(val):
        try:
            v = float(str(val).replace("₹", "").replace(",", "").replace("%", ""))
            color = "#16A34A" if v >= 0 else "#DC2626"
            return f"color:{color};font-family:'JetBrains Mono',monospace;font-weight:600;"
        except Exception:
            return ""

    cols = [c for c in [pnl_col, pct_col] if c and c in df.columns]
    styler = df.style
    for col in cols:
        styler = styler.applymap(color_val, subset=[col])
    return styler


# ── App Header ────────────────────────────────────────────

_render_html("""
<div style="margin-bottom:20px;">
    <span style="font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:700;
                 letter-spacing:-0.03em;color:#111827;">Options Tracker</span>
</div>
""")

tab1, tab2, tab3, tab4 = st.tabs(["Portfolio", "Risk Monitor", "Options Screener", "P&L Summary"])


# ══════════════════════════════════════════════════════════
# TAB 1 — PORTFOLIO
# ══════════════════════════════════════════════════════════

with tab1:

    # ── Section A: Equity Holdings ────────────────────────

    section_label("Equity Holdings")
    section_heading("Your portfolio at a glance")

    col_add, col_import, col_broker = st.columns([1, 1, 2])

    with col_add:
        with st.expander("➕ Add Holding"):
            with st.form("form_add_holding"):
                sym = st.text_input("Symbol (e.g. RELIANCE)").strip().upper()
                qty = st.number_input("Quantity", min_value=1, step=1)
                cp = st.number_input("Cost Price (₹)", min_value=0.01, format="%.2f")
                da = st.date_input("Date Added", value=date.today())
                notes = st.text_input("Notes (optional)")
                if st.form_submit_button("Add"):
                    if sym:
                        db.add_holding(sym, qty, cp, da, notes)
                        st.success(f"{sym} added.")
                        st.rerun()

    with col_import:
        with st.expander("📂 Import Holdings CSV"):
            st.markdown("Download template: `sample_data/sample_holdings.csv`")
            uploaded_h = st.file_uploader("Upload CSV", type="csv", key="holdings_csv")
            if uploaded_h:
                try:
                    df_h = pd.read_csv(uploaded_h)
                    required = {"symbol", "quantity", "cost_price", "date_added"}
                    if required.issubset(df_h.columns):
                        db.bulk_insert_holdings(df_h.to_dict("records"))
                        st.success(f"{len(df_h)} holdings imported.")
                        st.rerun()
                    else:
                        st.error(f"CSV must have columns: {required}")
                except Exception as e:
                    st.error(str(e))

    with col_broker:
        st.info("Broker import available once API credentials are configured.")

    holdings = db.get_holdings()

    if holdings:
        symbols = [h["symbol"] for h in holdings]
        with st.spinner("Fetching live prices..."):
            prices = market.get_multiple_stock_prices(symbols)

        rows = []
        total_invested = 0
        total_current = 0

        for h in holdings:
            cp_val = h["cost_price"] * h["quantity"]
            cur_price = prices.get(h["symbol"])
            cur_val = (cur_price * h["quantity"]) if cur_price else None
            pnl_amt = (cur_val - cp_val) if cur_val is not None else None
            pnl_pct = (pnl_amt / cp_val * 100) if pnl_amt is not None and cp_val > 0 else None
            total_invested += cp_val
            if cur_val:
                total_current += cur_val
            rows.append({
                "Symbol": h["symbol"],
                "Qty": h["quantity"],
                "Cost Price (₹)": h["cost_price"],
                "Current Price (₹)": cur_price or "—",
                "Invested (₹)": round(cp_val, 2),
                "Current Value (₹)": round(cur_val, 2) if cur_val else "—",
                "P&L (₹)": round(pnl_amt, 2) if pnl_amt is not None else "—",
                "P&L %": f"{pnl_pct:+.2f}%" if pnl_pct is not None else "—",
                "Notes": h.get("notes", ""),
            })

        # Hero bar
        total_pnl = total_current - total_invested if total_current else 0
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        hero_bar([
            ("Total Invested", fmt_inr(total_invested), "#FFFFFF"),
            ("Current Value", fmt_inr(total_current), "#FFFFFF"),
            ("Unrealised P&L", fmt_inr(total_pnl), "#16A34A" if total_pnl >= 0 else "#DC2626"),
            ("Return", f"{total_pnl_pct:+.2f}%", "#16A34A" if total_pnl_pct >= 0 else "#DC2626"),
        ])

        df_display = pd.DataFrame(rows)
        st.dataframe(
            style_pnl_df(df_display, "P&L (₹)", "P&L %"),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("📤 Record Exit / Sell"):
            holding_options = {f"{h['symbol']} — {h['quantity']} shares @ ₹{h['cost_price']}": h for h in holdings}
            sel_label = st.selectbox("Select holding", list(holding_options.keys()), key="exit_sel")
            sel_h = holding_options[sel_label]
            with st.form("form_exit_holding"):
                exit_qty = st.number_input("Quantity sold", min_value=1, max_value=int(sel_h["quantity"]), value=int(sel_h["quantity"]))
                exit_price = st.number_input("Sell price (₹)", min_value=0.01, format="%.2f", value=float(sel_h["cost_price"]))
                exit_date = st.date_input("Exit date", value=date.today(), key="exit_date")
                exit_notes = st.text_input("Notes (optional)", key="exit_notes")
                if st.form_submit_button("Record Exit"):
                    proceeds = exit_qty * exit_price
                    cost = exit_qty * sel_h["cost_price"]
                    pnl = proceeds - cost
                    pnl_pct = (pnl / cost * 100) if cost > 0 else 0
                    db.add_equity_trade(sel_h["symbol"], exit_qty, sel_h["cost_price"],
                                        exit_price, round(pnl, 2), exit_date, exit_notes)
                    new_qty = sel_h["quantity"] - exit_qty
                    if new_qty <= 0:
                        db.delete_holding(sel_h["id"])
                        st.success(f"Full exit recorded. P&L: {fmt_inr(pnl)} ({pnl_pct:+.2f}%)")
                    else:
                        db.update_holding(sel_h["id"], new_qty, sel_h["cost_price"], sel_h.get("notes", ""))
                        st.success(f"Partial exit recorded. Sold {exit_qty} shares, {new_qty} remain. P&L: {fmt_inr(pnl)} ({pnl_pct:+.2f}%)")
                    st.rerun()

        with st.expander("🗑️ Delete a Holding"):
            holding_options_del = {f"{h['symbol']} (ID {h['id']})": h["id"] for h in holdings}
            sel = st.selectbox("Select holding to delete", list(holding_options_del.keys()))
            if st.button("Delete", key="del_holding"):
                db.delete_holding(holding_options_del[sel])
                st.success("Deleted.")
                st.rerun()
    else:
        st.info("No holdings yet. Add one above or import a CSV.")

    st.divider()

    # ── Section B: Open Call Opportunities ───────────────

    section_label("Call Opportunities")
    section_heading("Stocks with no call sold this month")

    open_trades = db.get_trades(status="open")

    if holdings:
        opportunities = calc.get_open_opportunities(holdings, open_trades)
        if opportunities:
            opp_rows = []
            for h in opportunities:
                cur_price = prices.get(h["symbol"]) if holdings else None
                lot = market.get_lot_size(h["symbol"])
                opp_rows.append({
                    "Symbol": h["symbol"],
                    "Qty Held": h["quantity"],
                    "Cost Price (₹)": h["cost_price"],
                    "Current Price (₹)": cur_price or "—",
                    "Lot Size": lot,
                    "Notes": h.get("notes", ""),
                })
            st.warning(f"⚡ {len(opportunities)} stock(s) with no call sold this month")
            st.dataframe(pd.DataFrame(opp_rows), use_container_width=True, hide_index=True)
        else:
            st.success("All holdings have a call sold for this month.")
    else:
        st.info("Add holdings above to track call opportunities.")

    st.divider()

    # ── Section C: Open Positions ─────────────────────────

    section_label("Open Positions")
    section_heading("Current options positions")

    col_t1, col_t2 = st.columns([1, 1])
    with col_t1:
        with st.expander("➕ Add Trade"):
            with st.form("form_add_trade"):
                t_sym = st.text_input("Symbol").strip().upper()
                t_dir = st.radio("Direction", ["Sell", "Buy"], horizontal=True,
                                 help="Sell = write/short the option. Buy = long the option.")
                t_type = st.selectbox("Option Type", ["call", "put"])
                t_strike = st.number_input("Strike Price (₹)", min_value=0.01, format="%.2f")
                t_expiry = st.date_input("Expiry Date")
                premium_label = "Premium Received (₹)" if t_dir == "Sell" else "Premium Paid (₹)"
                t_premium = st.number_input(premium_label, min_value=0.01, format="%.2f")
                t_qty = st.number_input("Lots", min_value=1, step=1)
                t_lot = st.number_input("Lot Size", min_value=1, step=1,
                                        value=market.get_lot_size(t_sym) if t_sym else 1)
                t_date = st.date_input("Trade Date", value=date.today())
                t_notes = st.text_input("Notes (optional)")
                if st.form_submit_button("Add Trade"):
                    if t_sym:
                        db.add_trade(t_sym, t_type, t_strike, t_expiry, t_premium,
                                     t_qty, t_lot, t_date, t_notes, direction=t_dir.lower())
                        st.success(f"Trade added: {t_dir} {t_sym} {t_type.upper()} {t_strike}")
                        st.rerun()

    with col_t2:
        with st.expander("📂 Import Trades CSV"):
            st.markdown("Download template: `sample_data/sample_trades.csv`")
            uploaded_t = st.file_uploader("Upload CSV", type="csv", key="trades_csv")
            if uploaded_t:
                try:
                    df_t = pd.read_csv(uploaded_t)
                    required_t = {"symbol", "trade_type", "strike_price", "expiry_date",
                                  "premium_received", "quantity", "lot_size", "trade_date"}
                    if required_t.issubset(df_t.columns):
                        db.bulk_insert_trades(df_t.to_dict("records"))
                        st.success(f"{len(df_t)} trades imported.")
                        st.rerun()
                    else:
                        st.error(f"CSV must have columns: {required_t}")
                except Exception as e:
                    st.error(str(e))

    # Open positions table
    open_trades = db.get_trades(status="open")
    all_trades = db.get_trades()

    if open_trades:
        open_rows = []
        for t in open_trades:
            direction = t.get("direction") or "sell"
            premium_total = t["premium_received"] * t["quantity"] * t["lot_size"]
            _, days_left = calc.is_expiry_near(t["expiry_date"], 999)
            premium_col = "Premium Recv (₹)" if direction == "sell" else "Premium Paid (₹)"
            open_rows.append({
                "Symbol": t["symbol"],
                "Direction": direction.upper(),
                "Type": t["trade_type"].upper(),
                "Strike (₹)": t["strike_price"],
                "Expiry": t["expiry_date"],
                "Days Left": days_left,
                premium_col: t["premium_received"],
                "Lots": t["quantity"],
                "Lot Size": t["lot_size"],
                "Total (₹)": round(premium_total, 2),
                "Trade Date": t["trade_date"],
                "Notes": t.get("notes", ""),
            })
        st.dataframe(pd.DataFrame(open_rows), use_container_width=True, hide_index=True)

        # ── Record Outcome (end of month) ─────────────────
        st.divider()
        section_label("Record Outcome")
        section_heading("Close positions at month end")
        _render_html("""
        <div style="background:#F9FAFB;border:1px solid #E5E7EB;border-left:3px solid #2563EB;
                    border-radius:0 4px 4px 0;padding:12px 16px;margin-bottom:16px;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#6B7280;">
                At month end, record what happened to each position:
                <b>Expired worthless</b> (full premium kept) ·
                <b>Bought back</b> (enter buyback price, P&amp;L = premium received − buyback cost) ·
                <b>Exercised</b> (option was assigned against you)
            </span>
        </div>""")

        with st.form("form_close_trade"):
            trade_map = {t["id"]: t for t in open_trades}
            trade_opts = {
                f"{t.get('direction','sell').upper()} {t['symbol']} {t['trade_type'].upper()} {t['strike_price']} exp {t['expiry_date']}": t["id"]
                for t in open_trades
            }
            sel_label = st.selectbox("Select position", list(trade_opts.keys()))
            sel_id = trade_opts[sel_label]
            sel_trade = trade_map[sel_id]
            direction = sel_trade.get("direction") or "sell"

            action = st.radio("Outcome", ["Expired worthless", "Closed / Bought back", "Exercised"], horizontal=True)
            close_p = st.number_input("Close Price (₹)", min_value=0.0, format="%.2f",
                                      help="Price at which position was closed") if action == "Closed / Bought back" else 0.0
            close_d = st.date_input("Date", value=date.today())

            # Exercise portfolio impact preview
            if action == "Exercised":
                shares = sel_trade["quantity"] * sel_trade["lot_size"]
                strike = sel_trade["strike_price"]
                symbol = sel_trade["symbol"]
                t_type = sel_trade["trade_type"]

                if direction == "sell" and t_type == "call":
                    impact_msg = f"Shares called away: remove {shares} shares of {symbol} from portfolio (sold at ₹{strike})"
                elif direction == "sell" and t_type == "put":
                    impact_msg = f"Shares assigned: add {shares} shares of {symbol} to portfolio at ₹{strike}"
                elif direction == "buy" and t_type == "call":
                    impact_msg = f"You exercised: add {shares} shares of {symbol} to portfolio at ₹{strike}"
                else:  # buy put
                    impact_msg = f"You exercised: remove {shares} shares of {symbol} from portfolio (sold at ₹{strike})"

                st.info(f"Portfolio impact: {impact_msg}")
                auto_update = st.checkbox("Automatically update portfolio", value=True)
            else:
                auto_update = False

            if st.form_submit_button("Record Outcome"):
                if action == "Closed / Bought back":
                    db.close_trade(sel_id, close_p, close_d)
                elif action == "Expired worthless":
                    db.close_trade(sel_id, 0.0, close_d)
                    db.mark_trade_expired(sel_id)
                else:
                    db.mark_trade_exercised(sel_id)
                    if auto_update:
                        shares = sel_trade["quantity"] * sel_trade["lot_size"]
                        strike = sel_trade["strike_price"]
                        symbol = sel_trade["symbol"]
                        t_type = sel_trade["trade_type"]
                        # Determine whether to add or remove shares
                        adding = (direction == "sell" and t_type == "put") or \
                                 (direction == "buy" and t_type == "call")
                        if adding:
                            # Merge into existing holding at blended cost price
                            holdings_cur = db.get_holdings()
                            existing = next((x for x in holdings_cur if x["symbol"] == symbol), None)
                            if existing:
                                total_qty = existing["quantity"] + shares
                                blended_cost = ((existing["cost_price"] * existing["quantity"]) + (strike * shares)) / total_qty
                                db.update_holding(existing["id"], total_qty, round(blended_cost, 4), existing.get("notes", ""))
                            else:
                                db.add_holding(symbol, shares, strike, close_d,
                                               notes=f"Assigned/exercised from options trade")
                        else:
                            # Remove shares — reduce or delete existing holding
                            holdings = db.get_holdings()
                            h = next((x for x in holdings if x["symbol"] == symbol), None)
                            if h:
                                new_qty = h["quantity"] - shares
                                if new_qty <= 0:
                                    db.delete_holding(h["id"])
                                else:
                                    db.update_holding(h["id"], new_qty, h["cost_price"], h.get("notes", ""))
                                # Log as equity exit — sold at strike price
                                exit_pnl = (strike - h["cost_price"]) * shares
                                db.add_equity_trade(symbol, shares, h["cost_price"], strike,
                                                    round(exit_pnl, 2), close_d,
                                                    notes=f"Exercise: {direction} {t_type}")

                st.success("Outcome recorded.")
                st.rerun()
    else:
        st.info("No open positions. Add a trade above.")

    # ── Trade History ─────────────────────────────────────
    if all_trades:
        st.divider()
        closed_trades = [t for t in all_trades if t["status"] != "open"]
        with st.expander(f"📋 Trade History ({len(closed_trades)} closed trades)"):
            if closed_trades:
                fc1, fc2 = st.columns(2)
                type_filter = fc1.selectbox("Type", ["all", "call", "put"], key="hist_type")
                month_options = sorted(
                    set(datetime.strptime(t["trade_date"], "%Y-%m-%d").strftime("%Y-%m") for t in closed_trades),
                    reverse=True
                )
                month_filter = fc2.selectbox("Month", ["all"] + month_options, key="hist_month")

                filtered = closed_trades
                if type_filter != "all":
                    filtered = [t for t in filtered if t["trade_type"] == type_filter]
                if month_filter != "all":
                    filtered = [t for t in filtered
                                if datetime.strptime(t["trade_date"], "%Y-%m-%d").strftime("%Y-%m") == month_filter]

                hist_rows = []
                for t in filtered:
                    premium_total = t["premium_received"] * t["quantity"] * t["lot_size"]
                    pnl, _ = calc.trade_pnl(t["premium_received"], t.get("close_price") or 0,
                                            t["quantity"], t["lot_size"],
                                            direction=t.get("direction", "sell"))
                    hist_rows.append({
                        "Symbol": t["symbol"],
                        "Direction": (t.get("direction") or "sell").upper(),
                        "Type": t["trade_type"].upper(),
                        "Strike (₹)": t["strike_price"],
                        "Expiry": t["expiry_date"],
                        "Premium (₹)": t["premium_received"],
                        "Total Premium (₹)": round(premium_total, 2),
                        "Outcome": t["status"].capitalize(),
                        "Close Price (₹)": t.get("close_price") or "—",
                        "Realised P&L (₹)": pnl,
                        "Close Date": t.get("close_date") or "—",
                    })

                st.dataframe(
                    style_pnl_df(pd.DataFrame(hist_rows), "Realised P&L (₹)"),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("No closed trades yet.")

            with st.expander("🗑️ Delete a Trade"):
                del_opts = {f"{t['symbol']} {t['trade_type'].upper()} {t['strike_price']} (ID {t['id']})": t["id"]
                            for t in all_trades}
                sel_del = st.selectbox("Select trade to delete", list(del_opts.keys()))
                if st.button("Delete Trade"):
                    db.delete_trade(del_opts[sel_del])
                    st.success("Deleted.")
                    st.rerun()

        # ── Monthly Summary ───────────────────────────────
        st.divider()
        section_label("Monthly Summary")
        summary = calc.monthly_summary(all_trades)
        if summary:
            st.dataframe(
                style_pnl_df(pd.DataFrame(summary), "Realised P&L (₹)"),
                use_container_width=True, hide_index=True,
            )


# ══════════════════════════════════════════════════════════
# TAB 2 — RISK MONITOR
# ══════════════════════════════════════════════════════════

with tab2:
    section_label("Risk Monitor")
    section_heading("Open positions — live risk view")

    with st.expander("⚙️ Alert Settings"):
        settings = db.get_alert_settings()
        with st.form("alert_settings_form"):
            a_email = st.text_input("Alert Email", value=settings.get("email", ""))
            a_threshold = st.slider("Risk Threshold (%)", 0.5, 10.0,
                                    float(settings.get("risk_threshold_pct", 2.0)), 0.5)
            a_days = st.number_input("Alert when expiry within N days", 1, 30,
                                     int(settings.get("days_to_expiry_alert", 5)))
            a_enabled = st.checkbox("Enable email alerts", value=bool(settings.get("alerts_enabled", 1)))
            if st.form_submit_button("Save Settings"):
                db.save_alert_settings(a_email, a_threshold, a_days, a_enabled)
                st.success("Settings saved.")

        if st.button("Send Test Email"):
            saved = db.get_alert_settings()
            ok, msg = send_email(
                saved.get("email", ""),
                "Options Tracker — Test Alert",
                "<h3>This is a test alert from Options Tracker.</h3>"
            )
            st.success(msg) if ok else st.error(msg)

    open_trades = db.get_trades(status="open")

    if not open_trades:
        st.info("No open trades to monitor.")
    else:
        settings = db.get_alert_settings()
        threshold = float(settings.get("risk_threshold_pct", 2.0))
        days_alert = int(settings.get("days_to_expiry_alert", 5))

        auto_refresh = st.toggle("Auto-refresh every 60s", value=False)

        with st.spinner("Fetching live prices for open positions..."):
            symbols = list(set(t["symbol"] for t in open_trades))
            prices = market.get_multiple_stock_prices(symbols)

        risk_rows = []
        at_risk_list = []
        total_open_premium = 0
        total_pnl_open = 0

        for t in open_trades:
            spot = prices.get(t["symbol"])
            at_risk, dist_pct = calc.is_at_risk(t, spot, threshold)
            expiry_near, days_left = calc.is_expiry_near(t["expiry_date"], days_alert)
            _tok = st.session_state.get("upstox_token")
            if _tok:
                cur_premium = upstox.get_option_premium(
                    t["symbol"], t["strike_price"], t["expiry_date"], t["trade_type"], _tok
                )
            else:
                cur_premium = market.get_option_premium(
                    t["symbol"], t["strike_price"], t["expiry_date"], t["trade_type"]
                )
            pnl_amt, pnl_pct = calc.trade_pnl(
                t["premium_received"], cur_premium or 0, t["quantity"], t["lot_size"],
                direction=t.get("direction", "sell")
            )
            total_open_premium += t["premium_received"] * t["quantity"] * t["lot_size"]
            total_pnl_open += pnl_amt

            risk_flag = []
            if at_risk:
                risk_flag.append("Near Strike")
            if expiry_near:
                risk_flag.append(f"Expiry in {days_left}d")

            risk_rows.append({
                "Symbol": t["symbol"],
                "Type": t["trade_type"].upper(),
                "Strike (₹)": t["strike_price"],
                "Spot (₹)": spot or "—",
                "Distance %": f"{dist_pct:.2f}%" if dist_pct is not None else "—",
                "Current Premium (₹)": cur_premium or "—",
                "P&L (₹)": pnl_amt,
                "P&L %": f"{pnl_pct:+.1f}%",
                "Expiry": t["expiry_date"],
                "Days Left": days_left,
                "Risk": ", ".join(risk_flag) if risk_flag else "OK",
            })

            if at_risk and spot:
                at_risk_list.append({**t, "spot_price": spot, "distance_pct": dist_pct})

        # Hero bar for open positions
        hero_bar([
            ("Open Positions", str(len(open_trades)), "#FFFFFF"),
            ("Premium Received", fmt_inr(total_open_premium), "#FFFFFF"),
            ("Unrealised P&L", fmt_inr(total_pnl_open), "#16A34A" if total_pnl_open >= 0 else "#DC2626"),
            ("At Risk", str(len(at_risk_list)), "#DC2626" if at_risk_list else "#16A34A"),
        ])

        df_risk = pd.DataFrame(risk_rows)

        def highlight_risk(row):
            risk = str(row.get("Risk", ""))
            if "Near Strike" in risk:
                return ["background-color:#FEF2F2"] * len(row)
            elif "Expiry" in risk:
                return ["background-color:#FFFBEB"] * len(row)
            return [""] * len(row)

        st.dataframe(
            style_pnl_df(df_risk, "P&L (₹)", "P&L %").apply(highlight_risk, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        if at_risk_list:
            st.error(f"⚠️ {len(at_risk_list)} position(s) at risk — spot is near strike")
            if st.button("Send Risk Alert Email"):
                saved = db.get_alert_settings()
                html = build_risk_alert_email(at_risk_list)
                ok, msg = send_email(saved.get("email", ""), "⚠️ Options Tracker — Positions at Risk", html)
                st.success(msg) if ok else st.error(msg)
        else:
            st.success("All positions are safe.")

        if auto_refresh:
            time.sleep(60)
            st.rerun()


# ══════════════════════════════════════════════════════════
# TAB 3 — OPTIONS SCREENER
# ══════════════════════════════════════════════════════════

with tab3:
    section_label("Options Screener")
    section_heading("Options Screener")

    # ── Watchlist Management ──────────────────────────────
    watchlist = db.get_watchlist()
    with st.expander(f"⭐ Manage Watchlist ({len(watchlist)} stocks)"):
        wl_col1, wl_col2 = st.columns(2)
        with wl_col1:
            known_symbols = sorted(upstox.INSTRUMENT_KEYS.keys())
            with st.form("form_add_watchlist", clear_on_submit=True):
                new_wl = st.selectbox("Add symbol", [""] + known_symbols)
                if st.form_submit_button("Add") and new_wl:
                    db.add_to_watchlist(new_wl)
                    st.rerun()
        if watchlist:
            with wl_col2:
                rem = st.selectbox("Remove", watchlist)
                if st.button("Remove"):
                    db.remove_from_watchlist(rem)
                    st.rerun()

    # ── Watchlist Data (auto-loads) ───────────────────────
    section_label("Watchlist")

    if not watchlist:
        st.info("Add stocks to your watchlist above to see live premiums here.")
    else:
        _tok = st.session_state.get("upstox_token")
        wl_refresh = st.button("🔄 Refresh Watchlist", key="wl_refresh")

        if wl_refresh or "wl_data" not in st.session_state or st.session_state.get("wl_symbols") != watchlist:
            with st.spinner("Fetching watchlist premiums..."):
                wl_results = []
                for sym in watchlist:
                    data = upstox.get_atm_premiums(sym, _tok) if _tok else market.get_atm_premiums(sym)
                    if data:
                        wl_results.append({
                            "Symbol": data["symbol"],
                            "Spot (₹)": data["spot_price"],
                            "ATM Strike": data["atm_strike"],
                            "Call Premium (₹)": data["call_premium"] or "—",
                            "Put Premium (₹)": data["put_premium"] or "—",
                            "Call %": data["call_pct"] or 0,
                            "Put %": data["put_pct"] or 0,
                            "Expiry": data["expiry_date"],
                        })
                st.session_state.wl_data = wl_results
                st.session_state.wl_symbols = watchlist

        wl_results = st.session_state.get("wl_data", [])
        if wl_results:
            df_wl = pd.DataFrame(wl_results).sort_values("Call %", ascending=False)
            st.dataframe(df_wl, use_container_width=True, hide_index=True)
        else:
            st.warning("No data returned. Connect Upstox or check market hours.")

    st.divider()

    # ── Full F&O Screener ─────────────────────────────────
    section_label("Full F&O Scan")

    sc1, sc2, sc3, sc4 = st.columns([1, 1, 1, 1])
    min_call_pct = sc1.number_input("Min Call % of Spot", 0.0, 10.0, 0.0, 0.25)
    min_put_pct = sc2.number_input("Min Put % of Spot", 0.0, 10.0, 0.0, 0.25)
    run_screener = sc4.button("🔄 Scan All F&O Stocks", use_container_width=True)

    if run_screener:
        fo_stocks = market.get_fo_stocks()

        if fo_stocks:
            results = []
            progress = st.progress(0, text="Fetching option chains...")
            total = len(fo_stocks)

            _tok = st.session_state.get("upstox_token")
            for i, sym in enumerate(fo_stocks):
                progress.progress((i + 1) / total, text=f"Fetching {sym} ({i+1}/{total})...")
                data = upstox.get_atm_premiums(sym, _tok) if _tok else market.get_atm_premiums(sym)
                if data:
                    results.append({
                        "Symbol": data["symbol"],
                        "Spot (₹)": data["spot_price"],
                        "ATM Strike": data["atm_strike"],
                        "Call Premium (₹)": data["call_premium"] or "—",
                        "Put Premium (₹)": data["put_premium"] or "—",
                        "Call %": data["call_pct"] or 0,
                        "Put %": data["put_pct"] or 0,
                        "Expiry": data["expiry_date"],
                    })
                time.sleep(0.4)

            progress.empty()

            if results:
                df_screen = pd.DataFrame(results)

                if min_call_pct > 0:
                    df_screen = df_screen[df_screen["Call %"] >= min_call_pct]
                if min_put_pct > 0:
                    df_screen = df_screen[df_screen["Put %"] >= min_put_pct]

                df_screen = df_screen.sort_values("Call %", ascending=False)

                wl_set = set(db.get_watchlist())
                df_screen["Watchlist"] = df_screen["Symbol"].apply(lambda s: "⭐" if s in wl_set else "")

                hero_bar([
                    ("Stocks Scanned", str(total), "#FFFFFF"),
                    ("Results Shown", str(len(df_screen)), "#FFFFFF"),
                    ("Top Call %", f"{df_screen['Call %'].max():.2f}%", "#16A34A"),
                    ("Top Put %", f"{df_screen['Put %'].max():.2f}%", "#16A34A"),
                ])

                st.dataframe(df_screen, use_container_width=True, hide_index=True)

                add_wl_sym = st.selectbox("Add to watchlist from results",
                                          ["—"] + df_screen["Symbol"].tolist())
                if add_wl_sym != "—" and st.button("Add to Watchlist"):
                    db.add_to_watchlist(add_wl_sym)
                    st.success(f"{add_wl_sym} added to watchlist.")
                    st.rerun()
            else:
                st.warning("No data returned. Connect Upstox or check market hours.")
    else:
        _render_html("""
        <div style="background:#F9FAFB;border:1px solid #E5E7EB;border-left:3px solid #2563EB;
                    border-radius:0 4px 4px 0;padding:12px 16px;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#6B7280;">
                Click <strong>Scan All F&amp;O Stocks</strong> to fetch premiums for all ~180 NSE F&amp;O stocks.
                Takes ~2–3 minutes. Requires Upstox login.
            </span>
        </div>""")


# ══════════════════════════════════════════════════════════
# TAB 4 — P&L SUMMARY
# ══════════════════════════════════════════════════════════

with tab4:
    section_label("P&L Summary")
    section_heading("Realised & unrealised across equity and options")

    # ── Load data ─────────────────────────────────────────
    all_trades_summary = db.get_trades()
    holdings_summary = db.get_holdings()
    equity_trades = db.get_equity_trades()

    # ── Realised: Options ─────────────────────────────────
    closed_options = [t for t in all_trades_summary if t["status"] in ("closed", "expired", "exercised")]
    options_realised = sum(
        calc.trade_pnl(t["premium_received"], t.get("close_price") or 0,
                       t["quantity"], t["lot_size"], direction=t.get("direction", "sell"))[0]
        for t in closed_options
    )
    options_premium_collected = sum(
        t["premium_received"] * t["quantity"] * t["lot_size"]
        for t in all_trades_summary if t.get("direction", "sell") == "sell"
    )

    # ── Realised: Equity exits ────────────────────────────
    equity_realised = sum(t["pnl"] for t in equity_trades) if equity_trades else 0

    # ── Unrealised: Holdings ──────────────────────────────
    holding_symbols = list(set(h["symbol"] for h in holdings_summary))
    if holding_symbols:
        with st.spinner("Fetching live prices..."):
            live_prices = market.get_multiple_stock_prices(holding_symbols)
    else:
        live_prices = {}

    equity_unrealised = 0
    equity_invested = 0
    for h in holdings_summary:
        cost = h["cost_price"] * h["quantity"]
        equity_invested += cost
        cur = live_prices.get(h["symbol"])
        if cur:
            equity_unrealised += (cur * h["quantity"]) - cost

    # ── Unrealised: Open options ──────────────────────────
    open_options = [t for t in all_trades_summary if t["status"] == "open"]
    options_unrealised = 0
    _tok = st.session_state.get("upstox_token")
    for t in open_options:
        if _tok:
            cur_p = upstox.get_option_premium(t["symbol"], t["strike_price"], t["expiry_date"], t["trade_type"], _tok)
        else:
            cur_p = None
        pnl_amt, _ = calc.trade_pnl(t["premium_received"], cur_p or 0,
                                     t["quantity"], t["lot_size"], direction=t.get("direction", "sell"))
        options_unrealised += pnl_amt

    total_realised = options_realised + equity_realised
    total_unrealised = equity_unrealised + options_unrealised

    # ── Hero bar ──────────────────────────────────────────
    hero_bar([
        ("Total Realised P&L", fmt_inr(total_realised), "#16A34A" if total_realised >= 0 else "#DC2626"),
        ("Total Unrealised P&L", fmt_inr(total_unrealised), "#16A34A" if total_unrealised >= 0 else "#DC2626"),
        ("Options Premium Collected", fmt_inr(options_premium_collected), "#FFFFFF"),
        ("Equity Invested", fmt_inr(equity_invested), "#FFFFFF"),
    ])

    # ── Realised breakdown ────────────────────────────────
    section_label("Realised Breakdown")
    r_col1, r_col2 = st.columns(2)
    r_col1.metric("Options P&L (closed/expired/exercised)", fmt_inr(options_realised),
                  delta=f"{options_realised:+,.0f}")
    r_col2.metric("Equity exits P&L", fmt_inr(equity_realised),
                  delta=f"{equity_realised:+,.0f}")

    # ── Equity trade history ──────────────────────────────
    if equity_trades:
        st.divider()
        section_label("Equity Trade History")
        eq_rows = [{
            "Symbol": t["symbol"],
            "Qty": t["quantity"],
            "Buy Price (₹)": t["buy_price"],
            "Sell Price (₹)": t["sell_price"],
            "P&L (₹)": t["pnl"],
            "P&L %": f"{(t['pnl'] / (t['buy_price'] * t['quantity']) * 100):+.2f}%" if t["buy_price"] and t["quantity"] else "—",
            "Date": t["trade_date"],
            "Notes": t.get("notes", ""),
        } for t in equity_trades]
        st.dataframe(
            style_pnl_df(pd.DataFrame(eq_rows), "P&L (₹)", "P&L %"),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No equity exits recorded yet. Use 'Record Exit / Sell' in the Portfolio tab.")

    # ── Unrealised breakdown ──────────────────────────────
    st.divider()
    section_label("Unrealised Breakdown")
    u_col1, u_col2 = st.columns(2)
    u_col1.metric("Equity holdings (mark-to-market)", fmt_inr(equity_unrealised),
                  delta=f"{equity_unrealised:+,.0f}")
    u_col2.metric("Open options (mark-to-market)", fmt_inr(options_unrealised),
                  delta=f"{options_unrealised:+,.0f}",
                  help="Requires Upstox login for live option premiums.")

    # ── Options monthly summary ───────────────────────────
    if all_trades_summary:
        st.divider()
        section_label("Options — Monthly Breakdown")
        summary = calc.monthly_summary(all_trades_summary)
        if summary:
            st.dataframe(
                style_pnl_df(pd.DataFrame(summary), "Realised P&L (₹)"),
                use_container_width=True, hide_index=True,
            )
