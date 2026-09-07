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
- Hosted at [intelligentinvestor-zb18.onrender.com](https://intelligentinvestor-zb18.onrender.com)

## Planned features
- Fair P/E ratio based on comparable companies
- Backward P/E based on historical earnings growth
- Projected P/E based on projected earnings growth
- Analyst forward estimates for revenue and earnings growth
- Parallel fetching to speed up page load
- Price alerts

## Branches & deployment

This project runs two parallel versions so we can test changes safely before going live:

| Branch | Render service | Data source | Notes |
|--------|---------------|-------------|-------|
| `main` | Production (live URL) | yfinance | Stable, works locally |
| `fmp-migration` | Test service (separate URL) | stockanalysis.com scraper | In development |

**How switching works:**
- To run the yfinance version locally: `git checkout main`
- The production Render service always stays on `main` until a deliberate merge
- The test Render service runs `fmp-migration` independently

**Merge plan:** Once `fmp-migration` has been tested on the test Render service for an acceptable period, it will be merged into `main` — at which point the production service auto-updates. Until then, both versions remain independently reachable.

*Built as a learning project using Python, Flask, and Supabase.*