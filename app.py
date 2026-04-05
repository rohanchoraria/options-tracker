"""
Options Tracker — Main Streamlit App
Read optionstracker.md before making changes.
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
import time

import modules.database as db
import modules.market_data as market
import modules.calculations as calc
from modules.alerts import send_email, build_risk_alert_email, build_opportunity_alert_email

# ── Page Config ───────────────────────────────────────────

st.set_page_config(page_title="Options Tracker", page_icon="📈", layout="wide")
db.init_db()

st.title("📈 Options Tracker")
st.caption("Indian Stock Market — Covered Calls & Short Puts")

tab1, tab2, tab3 = st.tabs(["📁 Portfolio", "⚠️ Risk Monitor", "🔍 Options Screener"])


# ══════════════════════════════════════════════════════════
# TAB 1 — PORTFOLIO
# ══════════════════════════════════════════════════════════

with tab1:

    # ── Section A: Equity Holdings ────────────────────────

    st.subheader("Equity Holdings")

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
        st.info("Broker import will be available once API credentials are configured. See `.env.example`.")

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
                "ID": h["id"],
                "Symbol": h["symbol"],
                "Qty": h["quantity"],
                "Cost Price (₹)": h["cost_price"],
                "Current Price (₹)": cur_price or "—",
                "Invested (₹)": round(cp_val, 2),
                "Current Value (₹)": round(cur_val, 2) if cur_val else "—",
                "P&L (₹)": round(pnl_amt, 2) if pnl_amt is not None else "—",
                "P&L %": f"{pnl_pct:.2f}%" if pnl_pct is not None else "—",
                "Notes": h.get("notes", ""),
            })

        # Portfolio summary metrics
        total_pnl = total_current - total_invested if total_current else 0
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Invested", f"₹{total_invested:,.0f}")
        m2.metric("Current Value", f"₹{total_current:,.0f}")
        m3.metric("Unrealised P&L", f"₹{total_pnl:,.0f}", delta=f"{total_pnl_pct:.2f}%")

        df_display = pd.DataFrame(rows).drop(columns=["ID"])
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # Delete holding
        with st.expander("🗑️ Delete a Holding"):
            holding_options = {f"{h['symbol']} (ID {h['id']})": h["id"] for h in holdings}
            sel = st.selectbox("Select holding to delete", list(holding_options.keys()))
            if st.button("Delete", key="del_holding"):
                db.delete_holding(holding_options[sel])
                st.success("Deleted.")
                st.rerun()
    else:
        st.info("No holdings yet. Add one above or import a CSV.")

    st.divider()

    # ── Section B: Open Call Opportunities ───────────────

    st.subheader("Open Call Opportunities (No Call Sold This Month)")

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
            st.warning(f"⚡ {len(opportunities)} stock(s) with no call sold this month:")
            st.dataframe(pd.DataFrame(opp_rows), use_container_width=True, hide_index=True)
        else:
            st.success("All holdings have a call sold for this month.")
    else:
        st.info("Add holdings above to track call opportunities.")

    st.divider()

    # ── Section C: Trade Log ──────────────────────────────

    st.subheader("Trade Log")

    col_t1, col_t2 = st.columns([1, 1])

    with col_t1:
        with st.expander("➕ Add Trade"):
            with st.form("form_add_trade"):
                t_sym = st.text_input("Symbol").strip().upper()
                t_type = st.selectbox("Type", ["call", "put"])
                t_strike = st.number_input("Strike Price (₹)", min_value=0.01, format="%.2f")
                t_expiry = st.date_input("Expiry Date")
                t_premium = st.number_input("Premium Received (₹)", min_value=0.01, format="%.2f")
                t_qty = st.number_input("Lots", min_value=1, step=1)
                t_lot = st.number_input("Lot Size", min_value=1, step=1,
                                        value=market.get_lot_size(t_sym) if t_sym else 1)
                t_date = st.date_input("Trade Date", value=date.today())
                t_notes = st.text_input("Notes (optional)")
                if st.form_submit_button("Add Trade"):
                    if t_sym:
                        db.add_trade(t_sym, t_type, t_strike, t_expiry, t_premium,
                                     t_qty, t_lot, t_date, t_notes)
                        st.success(f"Trade added: {t_sym} {t_type.upper()} {t_strike}")
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

    all_trades = db.get_trades()

    if all_trades:
        # Filter controls
        fc1, fc2, fc3 = st.columns(3)
        status_filter = fc1.selectbox("Status", ["all", "open", "closed", "expired", "exercised"])
        type_filter = fc2.selectbox("Type", ["all", "call", "put"])
        month_options = sorted(
            set(datetime.strptime(t["trade_date"], "%Y-%m-%d").strftime("%Y-%m") for t in all_trades),
            reverse=True
        )
        month_filter = fc3.selectbox("Month", ["all"] + month_options)

        filtered = all_trades
        if status_filter != "all":
            filtered = [t for t in filtered if t["status"] == status_filter]
        if type_filter != "all":
            filtered = [t for t in filtered if t["trade_type"] == type_filter]
        if month_filter != "all":
            filtered = [t for t in filtered
                        if datetime.strptime(t["trade_date"], "%Y-%m-%d").strftime("%Y-%m") == month_filter]

        trade_rows = []
        for t in filtered:
            premium_total = t["premium_received"] * t["quantity"] * t["lot_size"]
            if t["status"] in ("closed", "expired") and t.get("close_price") is not None:
                pnl, pnl_pct = calc.trade_pnl(t["premium_received"], t["close_price"],
                                               t["quantity"], t["lot_size"])
            else:
                pnl, pnl_pct = "—", "—"

            trade_rows.append({
                "ID": t["id"],
                "Symbol": t["symbol"],
                "Type": t["trade_type"].upper(),
                "Strike (₹)": t["strike_price"],
                "Expiry": t["expiry_date"],
                "Premium (₹)": t["premium_received"],
                "Lots": t["quantity"],
                "Lot Size": t["lot_size"],
                "Total Premium (₹)": round(premium_total, 2),
                "Trade Date": t["trade_date"],
                "Status": t["status"].capitalize(),
                "Realised P&L (₹)": pnl,
                "Notes": t.get("notes", ""),
            })

        st.dataframe(pd.DataFrame(trade_rows).drop(columns=["ID"]),
                     use_container_width=True, hide_index=True)

        # Close / manage trade
        with st.expander("✏️ Close / Update a Trade"):
            trade_opts = {f"{t['symbol']} {t['trade_type'].upper()} {t['strike_price']} exp {t['expiry_date']} (ID {t['id']})": t["id"]
                          for t in all_trades if t["status"] == "open"}
            if trade_opts:
                sel_t = st.selectbox("Select trade", list(trade_opts.keys()))
                action = st.radio("Action", ["Close (bought back)", "Expired worthless", "Exercised"])
                close_p = st.number_input("Close/Buyback Price (₹)", min_value=0.0, format="%.2f") if action == "Close (bought back)" else 0.0
                close_d = st.date_input("Close Date", value=date.today())
                if st.button("Update Trade"):
                    tid = trade_opts[sel_t]
                    if action == "Close (bought back)":
                        db.close_trade(tid, close_p, close_d)
                    elif action == "Expired worthless":
                        db.close_trade(tid, 0.0, close_d)
                        db.mark_trade_expired(tid)
                    else:
                        db.mark_trade_exercised(tid)
                    st.success("Trade updated.")
                    st.rerun()
            else:
                st.info("No open trades to close.")

        with st.expander("🗑️ Delete a Trade"):
            del_opts = {f"{t['symbol']} {t['trade_type'].upper()} {t['strike_price']} (ID {t['id']})": t["id"]
                        for t in all_trades}
            sel_del = st.selectbox("Select trade to delete", list(del_opts.keys()))
            if st.button("Delete Trade"):
                db.delete_trade(del_opts[sel_del])
                st.success("Deleted.")
                st.rerun()

        # Monthly summary
        st.subheader("Monthly Summary")
        summary = calc.monthly_summary(all_trades)
        if summary:
            st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
    else:
        st.info("No trades yet. Add one above or import a CSV.")


# ══════════════════════════════════════════════════════════
# TAB 2 — RISK MONITOR
# ══════════════════════════════════════════════════════════

with tab2:
    st.subheader("Open Positions — Risk Monitor")

    # Alert settings
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

        # Auto-refresh toggle
        auto_refresh = st.toggle("Auto-refresh every 60s", value=False)

        with st.spinner("Fetching live prices for open positions..."):
            symbols = list(set(t["symbol"] for t in open_trades))
            prices = market.get_multiple_stock_prices(symbols)

        risk_rows = []
        at_risk_list = []

        for t in open_trades:
            spot = prices.get(t["symbol"])
            at_risk, dist_pct = calc.is_at_risk(t, spot, threshold)
            expiry_near, days_left = calc.is_expiry_near(t["expiry_date"], days_alert)
            cur_premium = market.get_option_premium(
                t["symbol"], t["strike_price"], t["expiry_date"], t["trade_type"]
            )
            pnl_amt, pnl_pct = calc.trade_pnl(
                t["premium_received"], cur_premium or 0, t["quantity"], t["lot_size"]
            )
            risk_flag = []
            if at_risk:
                risk_flag.append("Near Strike")
            if expiry_near:
                risk_flag.append(f"Expiry in {days_left}d")

            row = {
                "Symbol": t["symbol"],
                "Type": t["trade_type"].upper(),
                "Strike (₹)": t["strike_price"],
                "Spot (₹)": spot or "—",
                "Distance %": f"{dist_pct:.2f}%" if dist_pct is not None else "—",
                "Current Premium (₹)": cur_premium or "—",
                "P&L (₹)": pnl_amt,
                "P&L %": f"{pnl_pct:.1f}%",
                "Expiry": t["expiry_date"],
                "Days Left": days_left,
                "Risk": ", ".join(risk_flag) if risk_flag else "OK",
            }
            risk_rows.append(row)

            if at_risk and spot:
                at_risk_list.append({**t, "spot_price": spot, "distance_pct": dist_pct})

        df_risk = pd.DataFrame(risk_rows)

        # Highlight at-risk rows
        def highlight_risk(row):
            if "Near Strike" in str(row.get("Risk", "")):
                return ["background-color: #ffcccc"] * len(row)
            elif "Expiry" in str(row.get("Risk", "")):
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        st.dataframe(df_risk.style.apply(highlight_risk, axis=1),
                     use_container_width=True, hide_index=True)

        # Send alerts for at-risk positions
        if at_risk_list:
            st.error(f"⚠️ {len(at_risk_list)} position(s) at risk!")
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
    st.subheader("Options Screener — NSE F&O Stocks")
    st.caption("Find the highest premium opportunities across all F&O stocks.")

    # Watchlist management
    watchlist = db.get_watchlist()
    with st.expander(f"⭐ My Watchlist ({len(watchlist)} stocks)"):
        wl_col1, wl_col2 = st.columns(2)
        new_wl = wl_col1.text_input("Add to watchlist (symbol)").strip().upper()
        if wl_col1.button("Add") and new_wl:
            db.add_to_watchlist(new_wl)
            st.rerun()
        if watchlist:
            rem = wl_col2.selectbox("Remove from watchlist", watchlist)
            if wl_col2.button("Remove"):
                db.remove_from_watchlist(rem)
                st.rerun()

    # Screener controls
    sc1, sc2, sc3, sc4 = st.columns([1, 1, 1, 1])
    use_watchlist = sc1.checkbox("Watchlist only", value=False)
    min_call_pct = sc2.number_input("Min Call % of Spot", 0.0, 10.0, 0.0, 0.25)
    min_put_pct = sc3.number_input("Min Put % of Spot", 0.0, 10.0, 0.0, 0.25)
    run_screener = sc4.button("🔄 Fetch / Refresh Data", use_container_width=True)

    if run_screener:
        if use_watchlist and watchlist:
            fo_stocks = watchlist
        elif use_watchlist and not watchlist:
            st.warning("Watchlist is empty. Add stocks to watchlist first.")
            fo_stocks = []
        else:
            fo_stocks = market.get_fo_stocks()

        if fo_stocks:
            results = []
            progress = st.progress(0, text="Fetching option chains...")
            total = len(fo_stocks)

            for i, sym in enumerate(fo_stocks):
                progress.progress((i + 1) / total, text=f"Fetching {sym} ({i+1}/{total})...")
                data = market.get_atm_premiums(sym)
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
                time.sleep(0.4)  # be gentle with NSE API

            progress.empty()

            if results:
                df_screen = pd.DataFrame(results)

                # Apply filters
                if min_call_pct > 0:
                    df_screen = df_screen[df_screen["Call %"] >= min_call_pct]
                if min_put_pct > 0:
                    df_screen = df_screen[df_screen["Put %"] >= min_put_pct]

                df_screen = df_screen.sort_values("Call %", ascending=False)

                st.success(f"Showing {len(df_screen)} stocks.")

                # Watchlist toggle per row
                wl_set = set(db.get_watchlist())
                df_screen["In Watchlist"] = df_screen["Symbol"].apply(lambda s: "⭐" if s in wl_set else "")

                st.dataframe(df_screen, use_container_width=True, hide_index=True)

                # Quick add to watchlist from screener
                add_wl_sym = st.selectbox("Add to watchlist from results",
                                          ["—"] + df_screen["Symbol"].tolist())
                if add_wl_sym != "—" and st.button("Add to Watchlist"):
                    db.add_to_watchlist(add_wl_sym)
                    st.success(f"{add_wl_sym} added to watchlist.")
                    st.rerun()
            else:
                st.warning("No data returned. NSE API may be unavailable or market is closed.")
    else:
        st.info("Click **Fetch / Refresh Data** to load option premiums. Full scan takes ~2-3 minutes for all F&O stocks. Use watchlist for faster results.")
