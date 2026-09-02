# Stock Watchlist

A personal web app for tracking stocks I'm interested in.

## Current features
- Add and remove ticker symbols
- See the latest price and key price data for each stock:
  - Last Price, Change %, 6 Month Return, 1 Year Return
- See key financials for each stock:
  - Revenue TTM, Earnings TTM, Net Profit Margin
  - Free Cash Flow (TTM), Cash Conversion Ratio
  - P/FCF, P/E, ROIC (Return on Invested Capital)
  - Revenue Growth (3yr) and Earnings Growth (3yr)
- Manually set per stock (click any cell to edit, saved permanently):
  - Buffett Buy Price and the date it was calculated
  - Chance of 10x
- Automatically calculates the gap between current price and your Buffett Buy Price
- Sort by any column — click a header to sort ascending, click again for descending
- Ticker column and header row stay frozen when scrolling
- Parallel fetching (2 workers) for faster page load
- Hosted at [intelligentinvestor-zb18.onrender.com](https://intelligentinvestor-zb18.onrender.com)

## Planned features
- Switch data source from yfinance to Financial Modeling Prep (FMP) for reliable cloud hosting
- Supabase caching for all financial data — instant page loads, no live API calls on every visit
- Auto-refresh: daily prices, weekly returns, quarterly fundamentals (staggered to stay within free tier limits)
- Manual per-stock refresh button for when earnings just came out
- Analyst consensus growth projections (3yr and 5yr)
- Fair P/E ratio based on comparable companies
- Backward P/E based on historical earnings growth
- Projected P/E based on projected earnings growth
- Price alerts

## Local development
Copy `.env.example` to `.env` and fill in your credentials:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
FMP_KEY=your_fmp_key
```
Then run: `python3 app.py`

*Built as a learning project using Python, Flask, yfinance, Supabase, and Financial Modeling Prep.*
