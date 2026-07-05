from flask import Flask, render_template, request, redirect, url_for, jsonify
import yfinance as yf
import json
import os

app = Flask(__name__)

WATCHLIST_FILE = 'watchlist.json'


def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE) as f:
            data = json.load(f)
        # Migrate old format (list of strings) to new format (list of dicts)
        if data and isinstance(data[0], str):
            data = [{'ticker': t, 'buffett_buy_price': None, 'chance_of_10x': None} for t in data]
            save_watchlist(data)
        return data
    return []


def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(watchlist, f)


def get_stock_data(item):
    ticker = item['ticker']
    try:
        stock = yf.Ticker(ticker)

        hist = stock.history(period='5d')
        print(f"{ticker}: hist rows={len(hist)}")
        if len(hist) >= 2:
            price = round(float(hist['Close'].iloc[-1]), 2)
            prev_close = float(hist['Close'].iloc[-2])
            change_pct = round(((price - prev_close) / prev_close) * 100, 2)
        elif len(hist) == 1:
            price = round(float(hist['Close'].iloc[-1]), 2)
            change_pct = None
        else:
            price = None
            change_pct = None

        info = stock.info
        name = info.get('longName') or info.get('shortName') or ticker
        fcf = info.get('freeCashflow')
        fcf_billions = round(fcf / 1e9, 2) if fcf is not None else None
        mkt_cap = info.get('marketCap')
        mkt_cap_billions = round(mkt_cap / 1e9, 2) if mkt_cap is not None else None
        p_fcf = round(mkt_cap / fcf, 1) if (mkt_cap is not None and fcf is not None and fcf > 0) else None
        pe = info.get('trailingPE')
        pe = round(pe, 1) if pe is not None else None

        return {
            'ticker': ticker,
            'name': name,
            'price': price,
            'change_pct': change_pct,
            'fcf_billions': fcf_billions,
            'mkt_cap_billions': mkt_cap_billions,
            'p_fcf': p_fcf,
            'pe': pe,
            'buffett_buy_price': item.get('buffett_buy_price'),
            'chance_of_10x': item.get('chance_of_10x'),
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return {
            'ticker': ticker,
            'name': ticker,
            'price': None,
            'change_pct': None,
            'fcf_billions': None,
            'mkt_cap_billions': None,
            'p_fcf': None,
            'pe': None,
            'buffett_buy_price': item.get('buffett_buy_price'),
            'chance_of_10x': item.get('chance_of_10x'),
        }


@app.route('/')
def index():
    watchlist = load_watchlist()
    stocks = [get_stock_data(item) for item in watchlist]
    return render_template('index.html', stocks=stocks)


@app.route('/add', methods=['POST'])
def add():
    ticker = request.form.get('ticker', '').upper().strip()
    if ticker:
        watchlist = load_watchlist()
        existing = [w['ticker'] for w in watchlist]
        if ticker not in existing:
            watchlist.append({'ticker': ticker, 'buffett_buy_price': None, 'chance_of_10x': None})
            save_watchlist(watchlist)
    return redirect(url_for('index'))


@app.route('/delete/<ticker>')
def delete(ticker):
    watchlist = load_watchlist()
    watchlist = [w for w in watchlist if w['ticker'] != ticker]
    save_watchlist(watchlist)
    return redirect(url_for('index'))


@app.route('/update/<ticker>', methods=['POST'])
def update(ticker):
    watchlist = load_watchlist()
    data = request.get_json()
    for item in watchlist:
        if item['ticker'] == ticker:
            for field in ('buffett_buy_price', 'chance_of_10x'):
                if field in data:
                    val = data[field]
                    item[field] = float(val) if val != '' else None
            break
    save_watchlist(watchlist)
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
