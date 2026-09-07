# Stock Watchlist

A personal web app for tracking stocks I'm interested in from a value investing perspective.

## Current features

**Price & returns**
- Last Price, Change %, 6 Month Return, 1 Year Return

**Financials (auto-refreshed daily / quarterly)**
- Revenue TTM, Earnings TTM, Net Profit Margin
- Free Cash Flow TTM, Cash Conversion Ratio
- P/FCF, P/E, ROIC (Return on Invested Capital)
- Revenue Growth (3yr CAGR), Earnings Growth (3yr CAGR)

**Analyst data**
- EPS Growth (1yr analyst consensus)
- 12 Month Price Target, Upside/Downside %
- Analyst Consensus Rating

**Manual inputs** (click any cell to edit, saved permanently)
- Buffett Buy Price and the date it was calculated
- Chance of 10x

**Calculated automatically**
- Gap from Buffett Buy Price (how far current price is above/below your target)
- P/FCF (Market Cap ÷ FCF)

**UI**
- Sort by any column — click header to sort ascending, click again for descending
- Ticker column and header row stay frozen when scrolling
- Refresh All button — force re-scrape all tickers instantly
- Per-ticker refresh button (↻)
- Add and remove tickers

## Branches & deployment

Two parallel versions run simultaneously so changes can be tested safely before going live:

| Branch | Render service | Data source | Status |
|--------|---------------|-------------|--------|
| `main` | Production — [intelligentinvestor-zb18.onrender.com](https://intelligentinvestor-zb18.onrender.com) | yfinance | Stable |
| `fmp-migration` | Test service (separate URL) | stockanalysis.com scraper | In testing |

**Switching versions locally:**
```
git checkout main          # yfinance version
git checkout fmp-migration # scraper version
python3 app.py
```

**Merge plan:** Once `fmp-migration` has been tested on the test Render service, it will be merged into `main` and the production service will auto-update.

## Tech stack

- **Backend:** Python + Flask
- **Data:** stockanalysis.com (`fmp-migration`) / yfinance (`main`)
- **Database:** Supabase (Postgres) — caches scraped data, stores manual inputs
- **Frontend:** Jinja2 templates + vanilla JS
- **Hosting:** Render (auto-deploys from GitHub)

*Built as a learning project using Python, Flask, and Supabase.*
