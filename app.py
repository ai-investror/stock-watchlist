from flask import Flask, render_template, request, redirect, url_for, jsonify
from supabase import create_client
import yfinance as yf
import os

app = Flask(__name__)

supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])


def load_watchlist():
    result = supabase.table('watchlist').select('*').execute()
    return result.data


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

        buffett_buy_price = item.get('buffett_buy_price')
        gap_from_buffett = round(((price - buffett_buy_price) / buffett_buy_price) * 100, 1) if (price is not None and buffett_buy_price is not None and buffett_buy_price > 0) else None

        return {
            'ticker': ticker,
            'name': name,
            'price': price,
            'change_pct': change_pct,
            'fcf_billions': fcf_billions,
            'mkt_cap_billions': mkt_cap_billions,
            'p_fcf': p_fcf,
            'pe': pe,
            'buffett_buy_price': buffett_buy_price,
            'gap_from_buffett': gap_from_buffett,
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
            'gap_from_buffett': None,
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
        existing = supabase.table('watchlist').select('ticker').eq('ticker', ticker).execute()
        if not existing.data:
            supabase.table('watchlist').insert({'ticker': ticker}).execute()
    return redirect(url_for('index'))


@app.route('/delete/<ticker>')
def delete(ticker):
    supabase.table('watchlist').delete().eq('ticker', ticker).execute()
    return redirect(url_for('index'))


@app.route('/update/<ticker>', methods=['POST'])
def update(ticker):
    data = request.get_json()
    update_data = {}
    for field in ('buffett_buy_price', 'chance_of_10x'):
        if field in data:
            val = data[field]
            update_data[field] = float(val) if val != '' else None
    supabase.table('watchlist').update(update_data).eq('ticker', ticker).execute()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
