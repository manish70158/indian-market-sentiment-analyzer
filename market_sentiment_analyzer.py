import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import json
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import argparse
import sys
from io import StringIO

# --- CONFIGURATION ---
CONFIG_FILE = "/Users/manishkumar/Documents/learning/antigravity/research/config.json"

def get_mmi_sentiment():
    """Fetch Market Mood Index from Tickertape."""
    url = "https://www.tickertape.in/market-mood-index"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try parsing from __NEXT_DATA__ script tag
        next_data_script = soup.find('script', id='__NEXT_DATA__')
        if next_data_script:
            data = json.loads(next_data_script.string or "{}")
            # Recursively find 'mmi' or 'currentValue' in the JSON
            def find_mmi(obj):
                if isinstance(obj, dict):
                    if 'mmi' in obj and isinstance(obj['mmi'], (int, float)):
                        return float(obj['mmi'])
                    for k, v in obj.items():
                        res = find_mmi(v)
                        if res is not None: return res
                elif isinstance(obj, list):
                    for item in obj:
                        res = find_mmi(item)
                        if res is not None: return res
                return None
            
            mmi_val = find_mmi(data)
            if mmi_val is not None:
                value = round(mmi_val, 2)
                if value < 30: zone = "Extreme Fear"
                elif value < 50: zone = "Fear"
                elif value < 70: zone = "Neutral"
                elif value < 80: zone = "Greed"
                else: zone = "Extreme Greed"
                return {"value": value, "zone": zone, "error": None}

        # Fallback to regex
        match = re.search(r'"currentValue":([\d.]+)', response.text)
        if match:
            value = round(float(match.group(1)), 2)
            if value < 30: zone = "Extreme Fear"
            elif value < 50: zone = "Fear"
            elif value < 70: zone = "Neutral"
            elif value < 80: zone = "Greed"
            else: zone = "Extreme Greed"
            return {"value": value, "zone": zone, "error": None}
            
        return {"value": None, "zone": "Unknown", "error": "Could not parse MMI"}
    except Exception as e:
        return {"value": None, "zone": "Error", "error": str(e)}

def get_nifty_vix_data():
    """Fetch Nifty 50 and India VIX data using yfinance."""
    try:
        # Using tickers that are more stable
        nifty = yf.Ticker("^NSEI")
        vix = yf.Ticker("^INDIAVIX")
        
        # Use 5d to ensure we get at least 2 rows even on Mondays or early mornings
        n_hist = nifty.history(period="5d")
        v_hist = vix.history(period="5d")
        
        if len(n_hist) < 2 or len(v_hist) < 2:
            return {"error": f"Insufficient history data: Nifty({len(n_hist)}), VIX({len(v_hist)})"}
            
        n_curr = float(n_hist['Close'].iloc[-1])
        n_prev = float(n_hist['Close'].iloc[-2])
        n_change = ((n_curr - n_prev) / n_prev) * 100
        
        v_curr = float(v_hist['Close'].iloc[-1])
        v_prev = float(v_hist['Close'].iloc[-2])
        v_change = ((v_curr - v_prev) / v_prev) * 100
        
        return {
            "nifty_price": round(n_curr, 2),
            "nifty_change": round(n_change, 2),
            "vix_price": round(v_curr, 2),
            "vix_change": round(v_change, 2),
            "error": None
        }
    except Exception as e:
        return {"error": f"YFinance Error: {str(e)}"}

def get_fii_dii_activity():
    """Fetch FII/DII activity from Moneycontrol."""
    url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for the table in the container identified by subagent
        container = soup.find('div', class_='fidi_tbescrol')
        table = container.find('table') if container else soup.find('table', class_='mctable1')
        
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 7:
                    date_raw = cols[0].text.strip()
                    # Pattern check: Date should look like 23-Feb-2026
                    date_match = re.search(r'\d{2}-\w{3}-\d{4}', date_raw)
                    if date_match:
                        date = date_match.group(0)
                        # FII Net is usually 4th col (idx 3), DII Net is 7th col (idx 6)
                        fii_net_str = cols[3].text.strip().replace(',', '')
                        dii_net_str = cols[6].text.strip().replace(',', '')
                        return {
                            "date": date,
                            "fii_net": float(fii_net_str) if fii_net_str else 0.0,
                            "dii_net": float(dii_net_str) if dii_net_str else 0.0,
                            "error": None
                        }
        return {"error": "Could not parse FII/DII table"}
    except Exception as e:
        return {"error": str(e)}

def analyze_sentiment(mmi, market, flow):
    """Analyze the combined data to give a perspective."""
    score = 0
    reasons = []
    
    # 1. MMI Analysis (MMI is a contrarian indicator at extremes)
    if mmi.get('value') is not None:
        val = float(mmi['value'])
        zone = str(mmi['zone'])
        reasons.append(f"MMI: {val} ({zone})")
        if zone == "Extreme Fear": score += 2 
        elif zone == "Fear": score += 1
        elif zone == "Extreme Greed": score -= 2 
        elif zone == "Greed": score -= 1
    
    # 2. Market Momentum (Nifty) - Stronger weight
    if not market.get('error'):
        change = float(market['nifty_change'])
        reasons.append(f"Nifty 50: {change}%")
        if change > 1.5: score += 4
        elif change > 0.8: score += 2
        elif change > 0.3: score += 1
        elif change < -1.5: score -= 4
        elif change < -0.8: score -= 2
        elif change < -0.3: score -= 1
        
    # 3. Volatility (VIX)
    if not market.get('error'):
        vix = float(market['vix_price'])
        vix_c = float(market['vix_change'])
        reasons.append(f"VIX: {vix} ({vix_c}% change)")
        if vix > 22: score -= 3
        elif vix > 18: score -= 2
        elif vix > 15: score -= 1
        if vix_c > 10: score -= 2
        elif vix_c > 5: score -= 1
        elif vix_c < -5: score += 1
        
    # 4. Institutional Flow
    if not flow.get('error'):
        fii = float(flow['fii_net'])
        reasons.append(f"FII Net: {fii} Cr")
        if fii > 3000: score += 2
        elif fii > 0: score += 1
        elif fii < -3000: score -= 2
        elif fii < 0: score -= 1
        
    # Perspective mapping
    if score >= 6: perspective = "STRONGLY POSITIVE"
    elif score >= 3: perspective = "POSITIVE"
    elif score >= 1: perspective = "NEUTRAL TO POSITIVE"
    elif score <= -6: perspective = "STRONGLY NEGATIVE"
    elif score <= -3: perspective = "NEGATIVE"
    elif score <= -1: perspective = "NEUTRAL TO NEGATIVE"
    else: perspective = "NEUTRAL"
        
    return {
        "perspective": perspective,
        "score": score,
        "reasons": reasons
    }

def send_email(subject, content):
    """Send email notification."""
    sender_email = ""
    receiver_email = []
    app_password = ""
    
    # Try reading from config file first
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            sender_email = str(config.get("sender_email", "")).strip()
            receiver_email = config.get("receiver_emails", [])
            app_password = str(config.get("app_password", "")).strip()
        except:
            pass
            
    # Fallback/Override with environment variables for GitHub Actions
    sender_email = os.environ.get("SENDER_EMAIL", sender_email)
    app_password = os.environ.get("APP_PASSWORD", app_password)
    env_receivers = os.environ.get("RECEIVER_EMAILS")
    if env_receivers:
        receiver_email = [r.strip() for r in env_receivers.split(",")]
        
    if not sender_email or not app_password or not receiver_email:
        print("Error: Missing email credentials. Set env vars SENDER_EMAIL, APP_PASSWORD, RECEIVER_EMAILS or provide config.json.")
        return False

    try:
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = ", ".join(receiver_email)
        message["Subject"] = subject
        
        message.attach(MIMEText(content, "plain"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
            
        print(f"Email sent successfully to {', '.join(receiver_email)}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def init_config():
    """Create a template config file."""
    template = {
        "sender_email": "YOUR_GMAIL@gmail.com",
        "app_password": "YOUR_APP_PASSWORD",
        "receiver_emails": ["a.manish1689@gmail.com"]
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(template, f, indent=4)
    print(f"Created template config at {CONFIG_FILE}. Please update it with your Gmail App Password.")

def main():
    parser = argparse.ArgumentParser(description="Indian Market Sentiment Analyzer")
    parser.add_argument("--email", action="store_true", help="Send the result via email")
    parser.add_argument("--init-config", action="store_true", help="Initialize a template config file")
    args = parser.parse_args()

    if args.init_config:
        init_config()
        return

    # Capture output if sending email
    if args.email:
        output_buffer = StringIO()
        sys.stdout = output_buffer

    now = datetime.now()
    print(f"\n{'='*60}")
    print(f"   INDIAN MARKET SENTIMENT ANALYZER - {now.strftime('%d %b %Y %H:%M')}")
    print(f"{'='*60}")
    
    mmi_res = get_mmi_sentiment()
    market_res = get_nifty_vix_data()
    flow_res = get_fii_dii_activity()
    
    print(f"\n{'-'*20} DATA SUMMARY {'-'*20}")
    if mmi_res.get('value') is not None: 
        print(f"MMI Score      : {mmi_res['value']} [{mmi_res['zone']}]")
    else:
        print(f"MMI Score      : Error ({mmi_res.get('error')})")
        
    if not market_res.get('error'):
        n_c = float(market_res['nifty_change'])
        v_c = float(market_res['vix_change'])
        n_sign = "+" if n_c > 0 else ""
        v_sign = "+" if v_c > 0 else ""
        print(f"Nifty 50       : {market_res['nifty_price']} ({n_sign}{n_c}%)")
        print(f"India VIX      : {market_res['vix_price']} ({v_sign}{v_c}%)")
    else:
        print(f"Market Data    : Error ({market_res.get('error')})")
        
    if not flow_res.get('error'):
        f_net = float(flow_res['fii_net'])
        d_net = float(flow_res['dii_net'])
        f_sign = "+" if f_net > 0 else ""
        d_sign = "+" if d_net > 0 else ""
        print(f"FII Net Activity: {f_sign}{f_net} Cr")
        print(f"DII Net Activity: {d_sign}{d_net} Cr")
        print(f"Flow Date      : {flow_res['date']}")
    else:
        print(f"Flow Data      : Error ({flow_res.get('error')})")
        
    analysis = analyze_sentiment(mmi_res, market_res, flow_res)
    
    print(f"\n{'-'*20} FINAL PERSPECTIVE {'-'*20}")
    print(f"   >>> {analysis['perspective']} <<<")
    print(f"{'-'*55}")
    
    print("\nKey Sentiment Drivers:")
    for r in analysis['reasons']:
        print(f"  • {r}")
        
    print(f"\n{'='*60}")
    print(" Disclaimer: This analysis is for educational purposes only.")
    print(f"{'='*60}\n")

    if args.email:
        # Restore stdout and send email
        analysis_text = output_buffer.getvalue()
        sys.stdout = sys.__stdout__
        print(analysis_text) # Still print to console
        
        subject = f"Market Sentiment Analysis: {analysis['perspective']} ({now.strftime('%d %b')})"
        send_email(subject, analysis_text)

if __name__ == "__main__":
    main()



