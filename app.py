"""
Options Tracker — Main Streamlit App
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

# ── Page Config ───────────────────────────────────────────

st.set_page_config(page_title="Options Tracker", page_icon="📈", layout="wide")
db.init_db()

# ── Upstox OAuth Callback ─────────────────────────────────

_params = st.query_params
if "code" in _params and "upstox_token" not in st.session_state:
    _token = upstox.exchange_code(_params["code"])
    if _token:
        st.session_state.upstox_token = _token
        st.session_state.authenticated = True
        st.query_params.clear()
        st.rerun()
    else:
        st.error("Upstox login failed.")
        st.query_params.clear()

# ── Password Gate ─────────────────────────────────────────

if not st.session_state.get("authenticated"):
    st.title("Options Tracker")
    with st.form("login_form"):
        pwd = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        from modules.config import get as _cfg
        if pwd == _cfg("APP_PASSWORD", ""):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

# ── DB Cache ──────────────────────────────────────────────

@st.cache_data(ttl=60)
def _get_holdings():
    return db.get_holdings()

@st.cache_data(ttl=60)
def _get_trades(status=None):
    return db.get_trades(status=status)

@st.cache_data(ttl=60)
def _get_watchlist():
    return db.get_watchlist()

@st.cache_data(ttl=300)
def _get_alert_settings():
    return db.get_alert_settings()

@st.cache_data(ttl=60)
def _get_equity_trades():
    return db.get_equity_trades()

def _clear_db_cache():
    _get_holdings.clear()
    _get_trades.clear()
    _get_watchlist.clear()
    _get_alert_settings.clear()
    _get_equity_trades.clear()

# ── Sidebar ───────────────────────────────────────────────

with st.sidebar:
    st.markdown("**Live Data**")
    if "upstox_token" in st.session_state:
        st.success("Upstox connected")
        if st.button("Disconnect", use_container_width=True):
            del st.session_state["upstox_token"]
            st.rerun()
    else:
        st.warning("Upstox not connected")
        st.caption("Connect for live option premiums.")
        st.link_button("Login with Upstox", upstox.get_auth_url(), use_container_width=True)

# ── CSS ───────────────────────────────────────────────────

st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
[data-testid="stDataFrame"] th {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important; font-weight: 600 !important;
    letter-spacing: 0.04em !important; text-transform: uppercase !important;
    background: #F9FAFB !important;
}
[data-testid="stDataFrame"] td {
    font-family: 'JetBrains Mono', monospace !important; font-size: 13px !important;
}
[data-testid="stExpander"] summary { font-weight: 600 !important; font-size: 14px !important; }
[data-testid="InputInstructions"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────

def hero_bar(metrics):
    cols = st.columns(len(metrics))
    for col, (label, value, color) in zip(cols, metrics):
        col.markdown(
            f'<div style="padding:4px 0 16px 0;">'
            f'<div style="font-family:monospace;font-size:11px;font-weight:500;'
            f'letter-spacing:0.08em;text-transform:uppercase;color:#9CA3AF;margin-bottom:4px;">{label}</div>'
            f'<div style="font-family:monospace;font-size:26px;font-weight:700;'
            f'color:{color};line-height:1.1;">{value}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

def fmt_inr(v):
    return "—" if v is None else f"₹{v:,.0f}"

def pnl_color(v):
    if v is None: return "#111827"
    return "#16A34A" if v >= 0 else "#DC2626"

def style_pnl_df(df, *pnl_cols):
    def _color(val):
        try:
            v = float(str(val).replace("₹","").replace(",","").replace("%","").replace("+",""))
            return f"color:{'#16A34A' if v>=0 else '#DC2626'};font-weight:600;"
        except Exception:
            return ""
    styler = df.style
    for col in pnl_cols:
        if col in df.columns:
            styler = styler.map(_color, subset=[col])
    return styler

def section_label(text):
    st.markdown(
        f'<div style="font-family:monospace;font-size:11px;font-weight:500;'
        f'letter-spacing:0.08em;text-transform:uppercase;color:#9CA3AF;margin:12px 0 2px 0;">{text}</div>',
        unsafe_allow_html=True,
    )

# ── Header & Tabs ─────────────────────────────────────────

st.markdown("# Options Tracker")

tab1, tab2, tab3, tab4 = st.tabs(["Portfolio", "Risk Monitor", "Options Screener", "P&L Summary"])

# ══════════════════════════════════════════════════════════
# TAB 1 — PORTFOLIO
# ══════════════════════════════════════════════════════════

@st.fragment
def _render_tab1():

    # ── Equity Holdings ───────────────────────────────────
    section_label("Equity Holdings")

    c1, c2 = st.columns(2)
    with c1:
        with st.expander("➕ Add Holding"):
            with st.form("form_add_holding"):
                sym   = st.selectbox("Symbol", [""] + sorted(upstox.INSTRUMENT_KEYS.keys()))
                qty   = st.number_input("Quantity", min_value=1, step=1)
                cp    = st.number_input("Cost Price (₹)", min_value=0.01, format="%.2f")
                da    = st.date_input("Date Added", value=date.today())
                notes = st.text_input("Notes (optional)")
                if st.form_submit_button("Add"):
                    if sym:
                        db.add_holding(sym, qty, cp, da, notes)
                        st.success(f"{sym} added.")
                        _clear_db_cache()
                        st.rerun(scope="app")
                    else:
                        st.warning("Select a symbol.")

    with c2:
        with st.expander("📂 Import Holdings CSV"):
            st.caption("Columns: symbol, quantity, cost_price, date_added")
            uploaded_h = st.file_uploader("Upload CSV", type="csv", key="holdings_csv")
            if uploaded_h:
                try:
                    df_h = pd.read_csv(uploaded_h)
                    if {"symbol","quantity","cost_price","date_added"}.issubset(df_h.columns):
                        db.bulk_insert_holdings(df_h.to_dict("records"))
                        st.success(f"{len(df_h)} holdings imported.")
                        _clear_db_cache()
                        st.rerun(scope="app")
                    else:
                        st.error("Missing required columns.")
                except Exception as e:
                    st.error(str(e))

    holdings = _get_holdings()
    prices   = st.session_state.get("prices", {})

    if holdings:
        if st.button("🔄 Refresh Prices", key="refresh_prices"):
            with st.spinner("Fetching prices..."):
                st.session_state["prices"] = market.get_multiple_stock_prices(
                    [h["symbol"] for h in holdings])
            prices = st.session_state["prices"]

    # Build rows
    rows = []
    total_invested = total_current = 0
    for h in holdings:
        cp_val    = h["cost_price"] * h["quantity"]
        cur_price = prices.get(h["symbol"])
        cur_val   = (cur_price * h["quantity"]) if cur_price else None
        pnl_amt   = (cur_val - cp_val) if cur_val is not None else None
        pnl_pct   = (pnl_amt / cp_val * 100) if pnl_amt is not None and cp_val > 0 else None
        total_invested += cp_val
        if cur_val: total_current += cur_val
        rows.append({
            "Symbol":           h["symbol"],
            "Qty":              h["quantity"],
            "Cost Price (₹)":   round(h["cost_price"], 2),
            "Current Price (₹)":round(cur_price, 2) if cur_price else None,
            "Invested (₹)":     round(cp_val),
            "Current Value (₹)":round(cur_val) if cur_val else None,
            "P&L (₹)":          round(pnl_amt) if pnl_amt is not None else None,
            "P&L %":            f"{pnl_pct:+.1f}%" if pnl_pct is not None else "—",
            "Notes":            h.get("notes",""),
        })

    if holdings:
        total_pnl     = total_current - total_invested if total_current else 0
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        hero_bar([
            ("Total Invested",  fmt_inr(total_invested), "#111827"),
            ("Current Value",   fmt_inr(total_current),  "#111827"),
            ("Unrealised P&L",  fmt_inr(total_pnl),      pnl_color(total_pnl)),
            ("Return",          f"{total_pnl_pct:+.1f}%",pnl_color(total_pnl_pct)),
        ])

    with st.expander("Portfolio at a glance", expanded=True):
        if rows:
            st.dataframe(
                style_pnl_df(pd.DataFrame(rows), "P&L (₹)", "P&L %"),
                use_container_width=True, hide_index=True,
                column_config={
                    "Cost Price (₹)":    st.column_config.NumberColumn(format="%.2f"),
                    "Current Price (₹)": st.column_config.NumberColumn(format="%.2f"),
                    "Invested (₹)":      st.column_config.NumberColumn(format="%.0f"),
                    "Current Value (₹)": st.column_config.NumberColumn(format="%.0f"),
                    "P&L (₹)":           st.column_config.NumberColumn(format="%.0f"),
                },
            )
        else:
            st.info("No holdings yet. Add one above or import a CSV.")

    if holdings:
        with st.expander("📤 Record Exit / Sell"):
            h_opts  = {f"{h['symbol']} — {h['quantity']} shares @ ₹{h['cost_price']}": h for h in holdings}
            sel_lbl = st.selectbox("Select holding", list(h_opts.keys()), key="exit_sel")
            sel_h   = h_opts[sel_lbl]
            with st.form("form_exit_holding"):
                exit_qty   = st.number_input("Quantity sold", min_value=1,
                                             max_value=int(sel_h["quantity"]),
                                             value=int(sel_h["quantity"]),
                                             key=f"exit_qty_{sel_h['id']}")
                exit_price = st.number_input("Sell price (₹)", min_value=0.01, format="%.2f",
                                             value=float(sel_h["cost_price"]),
                                             key=f"exit_price_{sel_h['id']}")
                exit_date  = st.date_input("Exit date", value=date.today())
                exit_notes = st.text_input("Notes (optional)")
                if st.form_submit_button("Record Exit"):
                    pnl     = (exit_price - sel_h["cost_price"]) * exit_qty
                    pnl_pct = (pnl / (sel_h["cost_price"] * exit_qty) * 100)
                    db.add_equity_trade(sel_h["symbol"], exit_qty, sel_h["cost_price"],
                                        exit_price, round(pnl, 2), exit_date, exit_notes)
                    new_qty = sel_h["quantity"] - exit_qty
                    if new_qty <= 0:
                        db.delete_holding(sel_h["id"])
                        st.success(f"Full exit. P&L: {fmt_inr(pnl)} ({pnl_pct:+.1f}%)")
                    else:
                        db.update_holding(sel_h["id"], new_qty, sel_h["cost_price"], sel_h.get("notes",""))
                        st.success(f"Partial exit. {new_qty} remain. P&L: {fmt_inr(pnl)} ({pnl_pct:+.1f}%)")
                    _clear_db_cache()
                    st.rerun(scope="app")

        with st.expander("✏️ Edit a Holding"):
            h_edit = {f"{h['symbol']} — {h['quantity']} shares @ ₹{h['cost_price']}": h for h in holdings}
            sel_eh = h_edit[st.selectbox("Select", list(h_edit.keys()), key="edit_holding_sel")]
            with st.form("form_edit_holding"):
                e_qty   = st.number_input("Quantity", min_value=1, step=1,
                                          value=int(sel_eh["quantity"]), key=f"eh_qty_{sel_eh['id']}")
                e_cp    = st.number_input("Cost Price (₹)", min_value=0.01, format="%.2f",
                                          value=float(sel_eh["cost_price"]), key=f"eh_cp_{sel_eh['id']}")
                e_notes = st.text_input("Notes", value=sel_eh.get("notes",""), key=f"eh_notes_{sel_eh['id']}")
                if st.form_submit_button("Save"):
                    db.update_holding(sel_eh["id"], e_qty, e_cp, e_notes)
                    st.success("Updated.")
                    _clear_db_cache()
                    st.rerun(scope="app")

        with st.expander("🗑️ Delete a Holding"):
            h_del = {f"{h['symbol']} (ID {h['id']})": h["id"] for h in holdings}
            sel_d = st.selectbox("Select", list(h_del.keys()), key="del_holding_sel")
            if st.button("Delete", key="del_holding_btn"):
                db.delete_holding(h_del[sel_d])
                st.success("Deleted.")
                _clear_db_cache()
                st.rerun(scope="app")

    st.divider()

    # ── Call Opportunities ────────────────────────────────
    section_label("Call Opportunities")
    open_trades = _get_trades(status="open")

    with st.expander("Stocks with no call sold this month", expanded=True):
        if holdings:
            opps = calc.get_open_opportunities(holdings, open_trades)
            if opps:
                st.warning(f"⚡ {len(opps)} stock(s) with no call sold this month")
                st.dataframe(pd.DataFrame([{
                    "Symbol":           h["symbol"],
                    "Qty Held":         h["quantity"],
                    "Cost Price (₹)":   round(h["cost_price"]),
                    "Current Price (₹)":round(prices[h["symbol"]], 2) if prices.get(h["symbol"]) is not None else None,
                    "Lot Size":         market.get_lot_size(h["symbol"]),
                } for h in opps]), use_container_width=True, hide_index=True)
            else:
                st.success("All holdings have a call sold this month.")
        else:
            st.info("Add holdings to track opportunities.")

    st.divider()

    # ── Open Positions ────────────────────────────────────
    section_label("Open Positions")

    c1, c2 = st.columns(2)
    with c1:
        with st.expander("➕ Add Trade"):
            known_syms = sorted(upstox.INSTRUMENT_KEYS.keys())
            t_sym = st.selectbox("Symbol", [""] + known_syms, key="add_trade_sym")
            auto_lot = market.get_lot_size(t_sym) if t_sym else 1
            if t_sym:
                st.caption(f"Lot size: {auto_lot}")
            with st.form("form_add_trade"):
                t_dir     = st.radio("Direction", ["Sell","Buy"], horizontal=True)
                t_type    = st.selectbox("Option Type", ["call","put"])
                t_strike  = st.number_input("Strike Price (₹)", min_value=0.01, format="%.2f")
                t_expiry  = st.date_input("Expiry Date")
                t_premium = st.number_input(
                    "Premium Received (₹)" if t_dir=="Sell" else "Premium Paid (₹)",
                    min_value=0.01, format="%.2f")
                t_qty     = st.number_input("Lots", min_value=1, step=1)
                t_date    = st.date_input("Trade Date", value=date.today())
                t_notes   = st.text_input("Notes (optional)")
                if st.form_submit_button("Add Trade"):
                    if t_sym:
                        db.add_trade(t_sym, t_type, t_strike, t_expiry, t_premium,
                                     t_qty, auto_lot, t_date, t_notes, direction=t_dir.lower())
                        st.success("Trade added.")
                        _clear_db_cache()
                        st.rerun(scope="app")
                    else:
                        st.warning("Select a symbol.")

    with c2:
        with st.expander("📂 Import Trades CSV"):
            st.caption("Columns: symbol, trade_type, strike_price, expiry_date, premium_received, quantity, lot_size, trade_date")
            uploaded_t = st.file_uploader("Upload CSV", type="csv", key="trades_csv")
            if uploaded_t:
                try:
                    df_t = pd.read_csv(uploaded_t)
                    req  = {"symbol","trade_type","strike_price","expiry_date",
                            "premium_received","quantity","lot_size","trade_date"}
                    if req.issubset(df_t.columns):
                        db.bulk_insert_trades(df_t.to_dict("records"))
                        st.success(f"{len(df_t)} trades imported.")
                        _clear_db_cache()
                        st.rerun(scope="app")
                    else:
                        st.error(f"Missing columns: {req - set(df_t.columns)}")
                except Exception as e:
                    st.error(str(e))

    # Open positions summary bar
    if open_trades:
        op_premium  = sum(t["premium_received"]*t["quantity"]*t["lot_size"]
                          for t in open_trades if (t.get("direction") or "sell") == "sell")
        op_days     = [calc.is_expiry_near(t["expiry_date"], 999)[1] for t in open_trades]
        nearest_exp = min(op_days) if op_days else None
        hero_bar([
            ("Open Positions",    str(len(open_trades)),   "#111827"),
            ("Total Premium Recv",fmt_inr(op_premium),     "#16A34A"),
            ("Nearest Expiry",
             f"{nearest_exp}d" if nearest_exp is not None else "—",
             "#DC2626" if nearest_exp is not None and nearest_exp <= 7 else "#111827"),
        ])

    with st.expander("Current options positions", expanded=True):
        if open_trades:
            st.dataframe(pd.DataFrame([{
                "Symbol":     t["symbol"],
                "Direction":  (t.get("direction") or "sell").upper(),
                "Type":       t["trade_type"].upper(),
                "Strike (₹)": round(t["strike_price"]),
                "Expiry":     t["expiry_date"],
                "Days Left":  calc.is_expiry_near(t["expiry_date"], 999)[1],
                "Premium (₹)":round(t["premium_received"], 1),
                "Lots":       t["quantity"],
                "Lot Size":   t["lot_size"],
                "Total (₹)":  round(t["premium_received"]*t["quantity"]*t["lot_size"]),
                "Notes":      t.get("notes",""),
            } for t in open_trades]), use_container_width=True, hide_index=True,
                column_config={
                    "Strike (₹)":  st.column_config.NumberColumn(format="%.0f"),
                    "Premium (₹)": st.column_config.NumberColumn(format="%.1f"),
                    "Total (₹)":   st.column_config.NumberColumn(format="%.0f"),
                })
        else:
            st.info("No open positions. Add a trade above.")

    if open_trades:
        with st.expander("✏️ Edit a Trade"):
            edit_opts = {
                f"{t.get('direction','sell').upper()} {t['symbol']} {t['trade_type'].upper()} "
                f"{t['strike_price']} exp {t['expiry_date']} (ID {t['id']})": t
                for t in open_trades
            }
            et = edit_opts[st.selectbox("Select trade", list(edit_opts.keys()), key="edit_trade_sel")]
            auto_edit_lot = market.get_lot_size(et["symbol"])
            st.caption(f"Lot size for {et['symbol']}: {auto_edit_lot}")
            with st.form("form_edit_trade"):
                e_dir     = st.radio("Direction", ["Sell","Buy"], horizontal=True,
                                     index=0 if (et.get("direction") or "sell").lower()=="sell" else 1,
                                     key=f"edit_dir_{et['id']}")
                e_type    = st.selectbox("Option Type", ["call","put"],
                                         index=0 if et["trade_type"]=="call" else 1,
                                         key=f"edit_type_{et['id']}")
                e_strike  = st.number_input("Strike (₹)", min_value=0.01, format="%.2f",
                                            value=float(et["strike_price"]), key=f"edit_strike_{et['id']}")
                e_expiry  = st.date_input("Expiry",
                                          value=datetime.strptime(et["expiry_date"],"%Y-%m-%d").date(),
                                          key=f"edit_expiry_{et['id']}")
                e_premium = st.number_input("Premium (₹)", min_value=0.01, format="%.2f",
                                            value=float(et["premium_received"]), key=f"edit_premium_{et['id']}")
                e_qty     = st.number_input("Lots", min_value=1, step=1,
                                            value=int(et["quantity"]), key=f"edit_qty_{et['id']}")
                e_notes   = st.text_input("Notes", value=et.get("notes",""), key=f"edit_notes_{et['id']}")
                if st.form_submit_button("Save Changes"):
                    db.update_trade(et["id"], e_strike, e_expiry, e_premium,
                                    e_qty, auto_edit_lot, e_notes, e_dir, e_type)
                    st.success("Updated.")
                    _clear_db_cache()
                    st.rerun(scope="app")

        with st.expander("Close positions at month end"):
            st.caption("Record outcome: expired worthless · bought back · exercised/assigned")
            with st.form("form_close_trade"):
                trade_map  = {t["id"]: t for t in open_trades}
                trade_opts = {
                    f"{t.get('direction','sell').upper()} {t['symbol']} {t['trade_type'].upper()} "
                    f"{t['strike_price']} exp {t['expiry_date']}": t["id"]
                    for t in open_trades
                }
                sel_id    = trade_opts[st.selectbox("Select position", list(trade_opts.keys()))]
                sel_trade = trade_map[sel_id]
                direction = sel_trade.get("direction") or "sell"
                action    = st.radio("Outcome", ["Expired worthless","Closed / Bought back","Exercised"],
                                     horizontal=True)
                close_p   = st.number_input("Close Price (₹)", min_value=0.0, format="%.2f") \
                            if action == "Closed / Bought back" else 0.0
                close_d   = st.date_input("Date", value=date.today())

                if action == "Exercised":
                    shares = sel_trade["quantity"] * sel_trade["lot_size"]
                    t_type = sel_trade["trade_type"]
                    symbol = sel_trade["symbol"]
                    strike = sel_trade["strike_price"]
                    msgs   = {
                        ("sell","call"): f"Shares called away: remove {shares} {symbol} (sold @ ₹{strike})",
                        ("sell","put"):  f"Shares assigned: add {shares} {symbol} @ ₹{strike}",
                        ("buy","call"):  f"You exercised: add {shares} {symbol} @ ₹{strike}",
                        ("buy","put"):   f"You exercised: remove {shares} {symbol} (sold @ ₹{strike})",
                    }
                    st.info(f"Portfolio impact: {msgs.get((direction, t_type), '')}")
                    auto_update = st.checkbox("Auto-update portfolio", value=True)
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
                            shares   = sel_trade["quantity"] * sel_trade["lot_size"]
                            symbol   = sel_trade["symbol"]
                            strike   = sel_trade["strike_price"]
                            t_type   = sel_trade["trade_type"]
                            adding   = (direction=="sell" and t_type=="put") or \
                                       (direction=="buy"  and t_type=="call")
                            cur_h    = db.get_holdings()
                            existing = next((x for x in cur_h if x["symbol"]==symbol), None)
                            if adding:
                                if existing:
                                    tq = existing["quantity"] + shares
                                    bc = ((existing["cost_price"]*existing["quantity"]) + (strike*shares)) / tq
                                    db.update_holding(existing["id"], tq, round(bc,4), existing.get("notes",""))
                                else:
                                    db.add_holding(symbol, shares, strike, close_d, notes="Assigned from options")
                            else:
                                if existing:
                                    nq = existing["quantity"] - shares
                                    if nq <= 0:
                                        db.delete_holding(existing["id"])
                                    else:
                                        db.update_holding(existing["id"], nq, existing["cost_price"], existing.get("notes",""))
                                    db.add_equity_trade(symbol, shares, existing["cost_price"], strike,
                                                        round((strike-existing["cost_price"])*shares,2),
                                                        close_d, notes=f"Exercise: {direction} {t_type}")
                    st.success("Outcome recorded.")
                    _clear_db_cache()
                    st.rerun(scope="app")

    # ── Trade History ─────────────────────────────────────
    all_trades = _get_trades()
    if all_trades:
        st.divider()
        closed = [t for t in all_trades if t["status"] != "open"]
        with st.expander(f"Trade History ({len(closed)} closed)"):
            if closed:
                fc1, fc2 = st.columns(2)
                tf = fc1.selectbox("Type", ["all","call","put"], key="hist_type")
                mo = sorted(set(datetime.strptime(t["trade_date"],"%Y-%m-%d").strftime("%Y-%m")
                                for t in closed), reverse=True)
                mf = fc2.selectbox("Month", ["all"]+mo, key="hist_month")
                filtered = [t for t in closed
                            if (tf=="all" or t["trade_type"]==tf)
                            and (mf=="all" or datetime.strptime(t["trade_date"],"%Y-%m-%d").strftime("%Y-%m")==mf)]
                hist_rows = []
                for t in filtered:
                    pnl, _ = calc.trade_pnl(t["premium_received"], t.get("close_price") or 0,
                                            t["quantity"], t["lot_size"], direction=t.get("direction","sell"))
                    hist_rows.append({
                        "Symbol":           t["symbol"],
                        "Dir":              (t.get("direction") or "sell").upper(),
                        "Type":             t["trade_type"].upper(),
                        "Strike (₹)":       round(t["strike_price"]),
                        "Expiry":           t["expiry_date"],
                        "Premium (₹)":      round(t["premium_received"],1),
                        "Total (₹)":        round(t["premium_received"]*t["quantity"]*t["lot_size"]),
                        "Outcome":          t["status"].capitalize(),
                        "Close Price (₹)":  round(t["close_price"],1) if t.get("close_price") else None,
                        "Realised P&L (₹)": round(pnl),
                    })
                st.dataframe(style_pnl_df(pd.DataFrame(hist_rows),"Realised P&L (₹)"),
                             use_container_width=True, hide_index=True,
                             column_config={
                                 "Strike (₹)":       st.column_config.NumberColumn(format="%.0f"),
                                 "Premium (₹)":      st.column_config.NumberColumn(format="%.1f"),
                                 "Total (₹)":        st.column_config.NumberColumn(format="%.0f"),
                                 "Close Price (₹)":  st.column_config.NumberColumn(format="%.1f"),
                                 "Realised P&L (₹)": st.column_config.NumberColumn(format="%.0f"),
                             })
            else:
                st.info("No closed trades yet.")

        with st.expander("🗑️ Delete a Trade"):
            del_opts = {f"{t['symbol']} {t['trade_type'].upper()} {t['strike_price']} (ID {t['id']})": t["id"]
                        for t in all_trades}
            sel_del  = st.selectbox("Select", list(del_opts.keys()), key="del_trade_sel")
            if st.button("Delete Trade", key="del_trade_btn"):
                db.delete_trade(del_opts[sel_del])
                st.success("Deleted.")
                _clear_db_cache()
                st.rerun(scope="app")

        st.divider()
        section_label("Monthly Summary")
        summary = calc.monthly_summary(all_trades)
        if summary:
            st.dataframe(style_pnl_df(pd.DataFrame(summary),"Realised P&L (₹)"),
                         use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# TAB 2 — RISK MONITOR
# ══════════════════════════════════════════════════════════

@st.fragment
def _render_tab2():
    section_label("Risk Monitor")
    st.markdown("### Open positions — live risk view")

    with st.expander("⚙️ Alert Settings"):
        settings = _get_alert_settings()
        with st.form("alert_settings_form"):
            a_email     = st.text_input("Alert Email", value=settings.get("email",""))
            a_threshold = st.slider("Risk Threshold (%)", 0.5, 10.0,
                                    float(settings.get("risk_threshold_pct",2.0)), 0.5)
            a_days      = st.number_input("Alert when expiry within N days", 1, 30,
                                          int(settings.get("days_to_expiry_alert",5)))
            a_enabled   = st.checkbox("Enable email alerts",
                                      value=bool(settings.get("alerts_enabled",1)))
            if st.form_submit_button("Save Settings"):
                db.save_alert_settings(a_email, a_threshold, a_days, a_enabled)
                st.success("Settings saved.")
                _clear_db_cache()

        if st.button("Send Test Email"):
            settings = _get_alert_settings()
            ok, msg = send_email(settings.get("email",""),
                                 "Options Tracker — Test Alert",
                                 "<h3>Test alert from Options Tracker.</h3>")
            st.success(msg) if ok else st.error(msg)

    open_trades_r = _get_trades(status="open")
    if not open_trades_r:
        st.info("No open trades to monitor.")
        return

    threshold  = float(_get_alert_settings().get("risk_threshold_pct",2.0))
    days_alert = int(_get_alert_settings().get("days_to_expiry_alert",5))

    if st.button("🔄 Refresh Risk Monitor", key="refresh_risk"):
        with st.spinner("Fetching live data..."):
            _tok        = st.session_state.get("upstox_token")
            syms        = list(set(t["symbol"] for t in open_trades_r))
            prices_live = market.get_multiple_stock_prices(syms)
            risk_rows   = []
            at_risk     = []
            tot_prem    = tot_pnl = 0
            for t in open_trades_r:
                spot = prices_live.get(t["symbol"])
                ar, dist     = calc.is_at_risk(t, spot, threshold)
                _, days_left = calc.is_expiry_near(t["expiry_date"], days_alert)
                cur_prem     = (upstox.get_option_premium(t["symbol"],t["strike_price"],
                                t["expiry_date"],t["trade_type"],_tok) if _tok
                               else market.get_option_premium(t["symbol"],t["strike_price"],
                                t["expiry_date"],t["trade_type"]))
                pnl_amt, pnl_pct = calc.trade_pnl(t["premium_received"], cur_prem or 0,
                                                   t["quantity"], t["lot_size"],
                                                   direction=t.get("direction","sell"))
                tot_prem += t["premium_received"]*t["quantity"]*t["lot_size"]
                tot_pnl  += pnl_amt
                flags     = (["Near Strike"] if ar else []) + \
                            ([f"Expiry {days_left}d"] if calc.is_expiry_near(t["expiry_date"],days_alert)[0] else [])
                risk_rows.append({
                    "Symbol":          t["symbol"],
                    "Type":            t["trade_type"].upper(),
                    "Strike (₹)":      round(t["strike_price"]),
                    "Spot (₹)":        round(spot) if spot else None,
                    "Distance %":      f"{dist:.0f}%" if dist is not None else "—",
                    "Cur Premium (₹)": round(cur_prem,1) if cur_prem else None,
                    "P&L (₹)":         round(pnl_amt),
                    "P&L %":           f"{pnl_pct:+.0f}%",
                    "Expiry":          t["expiry_date"],
                    "Days Left":       days_left,
                    "Risk":            ", ".join(flags) if flags else "OK",
                })
                if ar and spot:
                    at_risk.append({**t, "spot_price":spot, "distance_pct":dist})
            st.session_state["risk_rows"]    = risk_rows
            st.session_state["at_risk_list"] = at_risk
            st.session_state["risk_totals"]  = (tot_prem, tot_pnl)

    if "risk_rows" not in st.session_state:
        st.info("Click **Refresh Risk Monitor** to load live prices and current premiums.")
    else:
        risk_rows = st.session_state["risk_rows"]
        at_risk   = st.session_state["at_risk_list"]
        tot_prem, tot_pnl = st.session_state["risk_totals"]

        hero_bar([
            ("Open Positions",  str(len(open_trades_r)), "#111827"),
            ("Premium Received",fmt_inr(tot_prem),       "#111827"),
            ("Unrealised P&L",  fmt_inr(tot_pnl),        pnl_color(tot_pnl)),
            ("At Risk",         str(len(at_risk)),
             "#DC2626" if at_risk else "#16A34A"),
        ])

        def _hl(row):
            r = str(row.get("Risk",""))
            if "Near Strike" in r: return ["background-color:#FEF2F2"]*len(row)
            if "Expiry"      in r: return ["background-color:#FFFBEB"]*len(row)
            return [""]*len(row)

        st.dataframe(
            style_pnl_df(pd.DataFrame(risk_rows),"P&L (₹)","P&L %").apply(_hl, axis=1),
            use_container_width=True, hide_index=True,
            column_config={
                "Strike (₹)":      st.column_config.NumberColumn(format="%.0f"),
                "Spot (₹)":        st.column_config.NumberColumn(format="%.0f"),
                "Cur Premium (₹)": st.column_config.NumberColumn(format="%.1f"),
                "P&L (₹)":         st.column_config.NumberColumn(format="%.0f"),
            })

        if at_risk:
            st.error(f"⚠️ {len(at_risk)} position(s) at risk")
            if st.button("Send Risk Alert Email"):
                ok, msg = send_email(_get_alert_settings().get("email",""),
                                     "⚠️ Options Tracker — Positions at Risk",
                                     build_risk_alert_email(at_risk))
                st.success(msg) if ok else st.error(msg)
        else:
            st.success("All positions are safe.")


# ══════════════════════════════════════════════════════════
# TAB 3 — OPTIONS SCREENER
# ══════════════════════════════════════════════════════════

@st.fragment
def _render_tab3():
    section_label("Options Screener")
    st.markdown("### Options Screener")

    watchlist = _get_watchlist()
    with st.expander(f"⭐ Manage Watchlist ({len(watchlist)} stocks)"):
        wc1, wc2 = st.columns(2)
        with wc1:
            with st.form("form_add_wl", clear_on_submit=True):
                new_wl = st.selectbox("Add symbol", [""] + sorted(upstox.INSTRUMENT_KEYS.keys()))
                if st.form_submit_button("Add") and new_wl:
                    db.add_to_watchlist(new_wl)
                    _clear_db_cache()
                    st.rerun(scope="app")
        if watchlist:
            with wc2:
                rem = st.selectbox("Remove", watchlist, key="wl_remove")
                if st.button("Remove", key="wl_remove_btn"):
                    db.remove_from_watchlist(rem)
                    _clear_db_cache()
                    st.rerun(scope="app")

    section_label("Watchlist")
    if not watchlist:
        st.info("Add stocks to your watchlist above.")
    else:
        _tok_wl    = st.session_state.get("upstox_token")
        wl_refresh = st.button("🔄 Refresh Watchlist", key="wl_refresh")
        if wl_refresh:
            with st.spinner("Fetching watchlist premiums..."):
                wl_results = []
                for sym in watchlist:
                    d = upstox.get_atm_premiums(sym,_tok_wl) if _tok_wl else market.get_atm_premiums(sym)
                    if d:
                        wl_results.append({
                            "Symbol":          d["symbol"],
                            "Spot (₹)":        d["spot_price"],
                            "ATM Strike":      d["atm_strike"],
                            "Call Premium (₹)":d["call_premium"] or "—",
                            "Put Premium (₹)": d["put_premium"]  or "—",
                            "Call %":          d["call_pct"] or 0,
                            "Put %":           d["put_pct"]  or 0,
                            "Expiry":          d["expiry_date"],
                        })
                st.session_state["wl_data"] = wl_results

        if st.session_state.get("wl_data"):
            st.dataframe(pd.DataFrame(st.session_state["wl_data"]).sort_values("Call %",ascending=False),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Click **Refresh Watchlist** to load live premiums.")

    st.divider()
    section_label("Full F&O Scan")
    sc1, sc2, _, sc4 = st.columns(4)
    min_call = sc1.number_input("Min Call %", 0.0, 10.0, 0.0, 0.25)
    min_put  = sc2.number_input("Min Put %",  0.0, 10.0, 0.0, 0.25)
    if sc4.button("🔄 Scan All F&O Stocks", use_container_width=True):
        fo      = sorted(upstox.INSTRUMENT_KEYS.keys())
        prog    = st.progress(0)
        _tok_sc = st.session_state.get("upstox_token")
        res     = []
        for i, sym in enumerate(fo):
            prog.progress((i+1)/len(fo), text=f"{sym} ({i+1}/{len(fo)})")
            d = upstox.get_atm_premiums(sym,_tok_sc) if _tok_sc else market.get_atm_premiums(sym)
            if d:
                res.append({"Symbol":d["symbol"],"Spot (₹)":d["spot_price"],
                            "ATM Strike":d["atm_strike"],
                            "Call Premium (₹)":d["call_premium"] or "—",
                            "Put Premium (₹)":d["put_premium"] or "—",
                            "Call %":d["call_pct"] or 0,"Put %":d["put_pct"] or 0,
                            "Expiry":d["expiry_date"]})
            time.sleep(0.4)
        prog.empty()
        if res:
            watchlist_set = set(_get_watchlist())
            df_sc = pd.DataFrame(res)
            if min_call > 0: df_sc = df_sc[df_sc["Call %"] >= min_call]
            if min_put  > 0: df_sc = df_sc[df_sc["Put %"]  >= min_put]
            df_sc = df_sc.sort_values("Call %", ascending=False)
            df_sc["WL"] = df_sc["Symbol"].apply(lambda s: "⭐" if s in watchlist_set else "")
            hero_bar([("Scanned",str(len(fo)),"#111827"),("Shown",str(len(df_sc)),"#111827"),
                      ("Top Call %",f"{df_sc['Call %'].max():.1f}%","#16A34A"),
                      ("Top Put %", f"{df_sc['Put %'].max():.1f}%", "#16A34A")])
            st.dataframe(df_sc, use_container_width=True, hide_index=True)
        else:
            st.warning("No data returned.")
    else:
        st.info("Click **Scan All F&O Stocks** to fetch premiums for all NSE F&O stocks.")


# ══════════════════════════════════════════════════════════
# TAB 4 — P&L SUMMARY
# ══════════════════════════════════════════════════════════

@st.fragment
def _render_tab4():
    section_label("P&L Summary")
    st.markdown("### Realised & unrealised P&L")

    all_tr    = _get_trades()
    holdings4 = _get_holdings()
    eq_tr     = _get_equity_trades()
    prices4   = st.session_state.get("prices", {})

    closed_opts   = [t for t in all_tr if t["status"] in ("closed","expired","exercised")]
    opts_realised = sum(calc.trade_pnl(t["premium_received"],t.get("close_price") or 0,
                                       t["quantity"],t["lot_size"],
                                       direction=t.get("direction","sell"))[0] for t in closed_opts)
    opts_premium  = sum(t["premium_received"]*t["quantity"]*t["lot_size"]
                        for t in all_tr if t.get("direction","sell")=="sell")
    eq_realised   = sum(t["pnl"] for t in eq_tr) if eq_tr else 0

    eq_unrealised = eq_invested = 0
    for h in holdings4:
        cost = h["cost_price"] * h["quantity"]
        eq_invested += cost
        cur = prices4.get(h["symbol"])
        if cur: eq_unrealised += (cur * h["quantity"]) - cost

    opts_unrealised = (st.session_state["risk_totals"][1]
                       if "risk_totals" in st.session_state
                       else sum(calc.trade_pnl(t["premium_received"],0,t["quantity"],t["lot_size"],
                                               direction=t.get("direction","sell"))[0]
                                for t in all_tr if t["status"]=="open"))

    total_realised   = opts_realised + eq_realised
    total_unrealised = eq_unrealised + opts_unrealised

    hero_bar([
        ("Total Realised P&L",        fmt_inr(total_realised),   pnl_color(total_realised)),
        ("Total Unrealised P&L",      fmt_inr(total_unrealised), pnl_color(total_unrealised)),
        ("Options Premium Collected", fmt_inr(opts_premium),     "#111827"),
        ("Equity Invested",           fmt_inr(eq_invested),      "#111827"),
    ])

    section_label("Realised Breakdown")
    r1, r2 = st.columns(2)
    r1.metric("Options (closed/expired/exercised)", fmt_inr(opts_realised),
              delta=f"{opts_realised:+,.0f}")
    r2.metric("Equity exits", fmt_inr(eq_realised),
              delta=f"{eq_realised:+,.0f}")

    if eq_tr:
        st.divider()
        section_label("Equity Trade History")
        st.dataframe(style_pnl_df(pd.DataFrame([{
            "Symbol":  t["symbol"],
            "Qty":     t["quantity"],
            "Buy (₹)": round(t["buy_price"]),
            "Sell (₹)":round(t["sell_price"]),
            "P&L (₹)": round(t["pnl"]),
            "P&L %":   f"{(t['pnl']/(t['buy_price']*t['quantity'])*100):+.1f}%"
                       if t["buy_price"] and t["quantity"] else "—",
            "Date":    t["trade_date"],
        } for t in eq_tr]),"P&L (₹)","P&L %"),
        use_container_width=True, hide_index=True)
    else:
        st.info("No equity exits yet. Use 'Record Exit / Sell' in the Portfolio tab.")

    st.divider()
    section_label("Unrealised Breakdown")
    u1, u2 = st.columns(2)
    u1.metric("Equity holdings (MTM)", fmt_inr(eq_unrealised),
              delta=f"{eq_unrealised:+,.0f}",
              help="Refresh Prices in Portfolio tab for live values.")
    u2.metric("Open options (MTM)", fmt_inr(opts_unrealised),
              delta=f"{opts_unrealised:+,.0f}",
              help="Refresh Risk Monitor (Tab 2) for live values.")

    if all_tr:
        st.divider()
        section_label("Options — Monthly Breakdown")
        summary = calc.monthly_summary(all_tr)
        if summary:
            st.dataframe(style_pnl_df(pd.DataFrame(summary),"Realised P&L (₹)"),
                         use_container_width=True, hide_index=True)


# ── Render Tabs ───────────────────────────────────────────

with tab1:
    _render_tab1()

with tab2:
    _render_tab2()

with tab3:
    _render_tab3()

with tab4:
    _render_tab4()
