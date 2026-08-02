# Stock Watchlist

A personal web app for tracking stocks I'm interested in.

## Current features
- Add and remove ticker symbols
- See the latest price, today's change %, market cap, and key financials for each stock:
  - Revenue TTM, Earnings TTM, Net Profit Margin
  - Free Cash Flow (TTM), Cash Conversion Ratio
  - P/FCF, P/E, ROIC (Return on Invested Capital)
  - Revenue Growth (3yr) and Earnings Growth (3yr)
- Manually set a Buffett Buy Price and Chance of 10x per stock (click any cell to edit)
- Automatically calculates the gap between current price and your Buffett Buy Price
- Sort by any column — click a header to sort ascending, click again for descending
- Ticker column and header row stay frozen when scrolling
- Hosted at [intelligentinvestor-zb18.onrender.com](https://intelligentinvestor-zb18.onrender.com)

## Planned features
- Fair P/E ratio based on comparable companies
- Backward P/E based on historical earnings growth
- Projected P/E based on projected earnings growth
- Analyst forward estimates for revenue and earnings growth
- Price alerts

*Built as a learning project using Python, Flask, yfinance, and Supabase.*
