import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


def _email_credentials():
    """Local `.env` first; on Streamlit Community Cloud use Secrets (same key names)."""
    sender = os.getenv("EMAIL_SENDER")
    app_password = os.getenv("EMAIL_APP_PASSWORD")
    if sender and app_password:
        return sender, app_password
    try:
        import streamlit as st

        if "EMAIL_SENDER" in st.secrets and "EMAIL_APP_PASSWORD" in st.secrets:
            return str(st.secrets["EMAIL_SENDER"]), str(st.secrets["EMAIL_APP_PASSWORD"])
    except Exception:
        pass
    return None, None


def send_email(to_email, subject, body_html):
    """Send an email via Gmail SMTP using App Password."""
    sender, app_password = _email_credentials()

    if not sender or not app_password:
        return (
            False,
            "Email credentials not configured. Set EMAIL_SENDER and EMAIL_APP_PASSWORD in `.env` "
            "(local) or in Streamlit app Secrets (deployed).",
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_password)
            server.sendmail(sender, to_email, msg.as_string())
        return True, "Email sent successfully."
    except Exception as e:
        return False, str(e)


def build_risk_alert_email(at_risk_positions):
    """Build HTML email body for at-risk positions."""
    rows = ""
    for p in at_risk_positions:
        rows += f"""
        <tr>
            <td>{p['symbol']}</td>
            <td>{p['trade_type'].upper()}</td>
            <td>₹{p['strike_price']:,.0f}</td>
            <td>₹{p['spot_price']:,.0f}</td>
            <td>{p['distance_pct']:.2f}%</td>
            <td>{p['expiry_date']}</td>
        </tr>"""

    return f"""
    <html><body>
    <h2 style="color:#d32f2f;">⚠️ Options at Risk</h2>
    <p>The following positions are near their strike price:</p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial;">
        <tr style="background:#f5f5f5;">
            <th>Symbol</th><th>Type</th><th>Strike</th>
            <th>Spot</th><th>Distance</th><th>Expiry</th>
        </tr>
        {rows}
    </table>
    <p style="color:gray;font-size:12px;">Sent by Options Tracker</p>
    </body></html>
    """


def build_opportunity_alert_email(uncovered_holdings):
    """Build HTML email body for uncovered holdings (no call sold yet)."""
    rows = ""
    for h in uncovered_holdings:
        rows += f"""
        <tr>
            <td>{h['symbol']}</td>
            <td>{h['quantity']}</td>
            <td>₹{h['cost_price']:,.2f}</td>
            <td>₹{h.get('current_price', 0):,.2f}</td>
        </tr>"""

    return f"""
    <html><body>
    <h2 style="color:#1565c0;">📋 Uncovered Holdings Reminder</h2>
    <p>You have not yet sold calls on the following stocks this month:</p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial;">
        <tr style="background:#f5f5f5;">
            <th>Symbol</th><th>Quantity</th><th>Cost Price</th><th>Current Price</th>
        </tr>
        {rows}
    </table>
    <p style="color:gray;font-size:12px;">Sent by Options Tracker</p>
    </body></html>
    """
