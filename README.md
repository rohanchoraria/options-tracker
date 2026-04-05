# Options Tracker

Personal app to track covered calls and short puts on the Indian stock market (NSE).

Read `optionstracker.md` for full project context before making changes.

---

## Setup

### 1. Install dependencies

```bash
C:\Users\rohan\Cursor\.claude\python.exe -m pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your Gmail credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
EMAIL_SENDER=your_gmail@gmail.com
EMAIL_APP_PASSWORD=your16charapppassword
EMAIL_RECIPIENT=your_email@gmail.com
```

To get a Gmail App Password:
1. Enable 2FA on your Google account
2. Go to Google Account > Security > 2-Step Verification > App Passwords
3. Generate a password for "Mail"

### 3. Run the app

```bash
C:\Users\rohan\Cursor\.claude\python.exe -m streamlit run app.py
```

The app opens at `http://localhost:8501`

---

## Usage

### Tab 1 — Portfolio
- Add your stock holdings manually or import via CSV
- View live P&L on all holdings
- See which stocks have no call sold this month (reminders)
- Log your options trades (calls and puts sold)
- View monthly P&L summary

### Tab 2 — Risk Monitor
- See all open positions with live prices
- Positions highlighted in red when spot is near strike
- Configure email alerts for risky positions

### Tab 3 — Options Screener
- Fetch ATM call and put premiums for all NSE F&O stocks
- Sort by premium % to find best opportunities
- Maintain a watchlist for quick refresh

---

## CSV Import Formats

### Holdings CSV
```
symbol,quantity,cost_price,date_added,notes
RELIANCE,250,2800.00,2025-01-15,
```

### Trades CSV
```
symbol,trade_type,strike_price,expiry_date,premium_received,quantity,lot_size,trade_date,notes
RELIANCE,call,2900,2025-03-27,45.00,1,250,2025-03-05,
```

See `sample_data/` folder for example files.

---

## Pending Setup

- [ ] Broker API integration (for live option prices on Risk Monitor tab)
- [ ] Deploy to Streamlit Community Cloud (steps below)

## Deployment (Streamlit Community Cloud)

1. **Create a GitHub repository** (empty, no README) and push **this** `options-tracker` folder as the repo root:
   ```bash
   cd options-tracker
   git init
   git add .
   git commit -m "Initial Options Tracker"
   git branch -M main
   git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
   git push -u origin main
   ```
2. Sign in at [share.streamlit.io](https://share.streamlit.io/) with GitHub and click **Create app**.
3. Choose your repo, branch **main**, and main file **`app.py`**.
4. Open **Advanced settings** → set **Python** to **3.12** (recommended; matches Streamlit Cloud default).
5. In **Secrets**, paste the contents of `secrets.example.toml` with your real Gmail app password values (same keys as `.env`). Email alerts read from there on Cloud.
6. **Deploy.**

**Notes**

- **SQLite on Cloud:** The `data/` database is stored on the app’s ephemeral disk. Data can be reset when the app sleeps or redeploys. For durable storage later, move to an external DB or object storage.
- **NSE / yfinance:** Requests run from Streamlit’s servers (not India). If NSE blocks or behaves differently, you may need your broker API for reliable chains.
- Template for secrets: `secrets.example.toml`
