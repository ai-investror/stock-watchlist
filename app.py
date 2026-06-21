from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import json
import os

app = Flask(__name__)

WATCHLIST_FILE = 'watchlist.json'


def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE) as f:
            return json.load(f)
    return []


def save_watchlist(tickers):
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(tickers, f)


def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='5d')
        if len(hist) >= 2:
            price = round(float(hist['Close'].iloc[-1]), 2)
            prev_close = float(hist['Close'].iloc[-2])
            change_pct = round(((price - prev_close) / prev_close) * 100, 2)
        elif len(hist) == 1:
            price = round(float(hist['Close'].iloc[-1]), 2)
            change_pct = None
        else:
            return {'ticker': ticker, 'price': None, 'change_pct': None}
        return {'ticker': ticker, 'price': price, 'change_pct': change_pct}
    except Exception:
        return {'ticker': ticker, 'price': None, 'change_pct': None}


@app.route('/')
def index():
    tickers = load_watchlist()
    stocks = [get_stock_data(t) for t in tickers]
    return render_template('index.html', stocks=stocks)


@app.route('/add', methods=['POST'])
def add():
    ticker = request.form.get('ticker', '').upper().strip()
    if ticker:
        tickers = load_watchlist()
        if ticker not in tickers:
            tickers.append(ticker)
            save_watchlist(tickers)
    return redirect(url_for('index'))


@app.route('/delete/<ticker>')
def delete(ticker):
    tickers = load_watchlist()
    tickers = [t for t in tickers if t != ticker]
    save_watchlist(tickers)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
