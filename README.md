# Indian Market Sentiment Analyzer

A tool to analyze the sentiment of the Indian stock market using various data sources including MMI, Nifty 50, India VIX, and FII/DII activity.

## Features
- **Market Mood Index (MMI)**: Fetches the current market mood (Fear/Greed) from Tickertape.
- **NSE Live Data**: Fetches Nifty 50 and India VIX using `yfinance`.
- **Institutional Flow**: Analyzes FII/DII net activity from Moneycontrol.
- **Automated Perspective**: Provides a weighted perspective (Positive/Negative/Neutral).
- **Email Notifications**: Capable of sending daily reports via Gmail.

## Prerequisites
- Python 3.x
- Dependencies: `yfinance`, `requests`, `beautifulsoup4`, `pandas`

## Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install yfinance requests beautifulsoup4 pandas
   ```
3. Initialize the config:
   ```bash
   python market_sentiment_analyzer.py --init-config
   ```
4. Update `config.json` with your email and Gmail App Password.

## Usage
Run the script manually:
```bash
./run_sentiment_job.sh
```

## Scheduling
To schedule the job (e.g., via crontab):
```bash
50 8 * * 1-5 /path/to/run_sentiment_job.sh >> /path/to/sentiment_log.txt 2>&1
```

## Disclaimer
This analysis is for educational purposes only. Investing in the stock market involves risks.
