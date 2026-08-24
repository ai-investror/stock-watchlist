from flask import Flask, render_template, request, redirect, url_for, jsonify
from supabase import create_client
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
import pandas as pd
import os

app = Flask(__name__)

supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])


def load_watchlist():
    result = supabase.table('watchlist').select('*').execute()
    return result.data


def _safe_bs(series, *keys):
    for key in keys:
        if key in series.index and pd.notna(series[key]):
            return float(series[key])
    return None


def get_stock_data(item):
    ticker = item['ticker']
    try:
        stock = yf.Ticker(ticker)

        hist = stock.history(period='1y')
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

        return_6m = None
        return_1y = None
        if price is not None:
            if len(hist) >= 127:
                price_6m_ago = float(hist['Close'].iloc[-127])
                return_6m = round(((price - price_6m_ago) / price_6m_ago) * 100, 1)
            if len(hist) >= 2:
                price_1y_ago = float(hist['Close'].iloc[0])
                return_1y = round(((price - price_1y_ago) / price_1y_ago) * 100, 1)

        info = stock.info
        name = info.get('longName') or info.get('shortName') or ticker

        mkt_cap = info.get('marketCap')
        mkt_cap_billions = round(mkt_cap / 1e9, 2) if mkt_cap is not None else None

        fcf = info.get('freeCashflow')
        fcf_billions = round(fcf / 1e9, 2) if fcf is not None else None
        p_fcf = round(mkt_cap / fcf, 1) if (mkt_cap and fcf and fcf > 0) else None

        pe = info.get('trailingPE')
        pe = round(pe, 1) if pe is not None else None

        revenue = info.get('totalRevenue')
        revenue_billions = round(revenue / 1e9, 2) if revenue is not None else None

        net_income = info.get('netIncomeToCommon')
        net_income_billions = round(net_income / 1e9, 2) if net_income is not None else None

        cash_conversion = round((fcf / net_income) * 100, 1) if (fcf is not None and net_income is not None and net_income != 0) else None

        raw_margin = info.get('profitMargins')
        net_margin_pct = round(raw_margin * 100, 1) if raw_margin is not None else None

        rev_growth_3yr = None
        earn_growth_3yr = None
        roic = None

        try:
            income_stmt = stock.income_stmt
            if income_stmt is not None and not income_stmt.empty:
                for rev_key in ('Total Revenue', 'TotalRevenue'):
                    if rev_key in income_stmt.index:
                        rev_s = income_stmt.loc[rev_key].dropna()
                        n = min(len(rev_s) - 1, 3)
                        if n >= 1:
                            r_new, r_old = float(rev_s.iloc[0]), float(rev_s.iloc[n])
                            if r_old > 0:
                                rev_growth_3yr = round(((r_new / r_old) ** (1 / n) - 1) * 100, 1)
                        break

                for earn_key in ('Net Income', 'NetIncome'):
                    if earn_key in income_stmt.index:
                        earn_s = income_stmt.loc[earn_key].dropna()
                        n = min(len(earn_s) - 1, 3)
                        if n >= 1:
                            e_new, e_old = float(earn_s.iloc[0]), float(earn_s.iloc[n])
                            if e_old > 0 and e_new > 0:
                                earn_growth_3yr = round(((e_new / e_old) ** (1 / n) - 1) * 100, 1)
                        break

            balance_sheet = stock.balance_sheet
            if balance_sheet is not None and not balance_sheet.empty and net_income is not None:
                bs = balance_sheet.iloc[:, 0]
                equity = _safe_bs(bs, 'Stockholders Equity', 'Total Stockholder Equity', 'StockholdersEquity')
                lt_debt = _safe_bs(bs, 'Long Term Debt', 'LongTermDebt') or 0
                curr_debt = _safe_bs(bs, 'Current Debt', 'CurrentDebt', 'Short Long Term Debt') or 0
                cash = _safe_bs(bs, 'Cash And Cash Equivalents', 'CashAndCashEquivalents',
                                'Cash Cash Equivalents And Short Term Investments', 'Cash') or 0
                if equity is not None:
                    invested_capital = equity + lt_debt + curr_debt - cash
                    if invested_capital > 0:
                        roic = round((net_income / invested_capital) * 100, 1)

        except Exception as e:
            print(f"Error fetching financials for {ticker}: {e}")

        buffett_buy_price = item.get('buffett_buy_price')
        gap_from_buffett = round(((price - buffett_buy_price) / buffett_buy_price) * 100, 1) if (price and buffett_buy_price and buffett_buy_price > 0) else None

        return {
            'ticker': ticker,
            'name': name,
            'price': price,
            'change_pct': change_pct,
            'return_6m': return_6m,
            'return_1y': return_1y,
            'mkt_cap_billions': mkt_cap_billions,
            'revenue_billions': revenue_billions,
            'net_income_billions': net_income_billions,
            'net_margin_pct': net_margin_pct,
            'fcf_billions': fcf_billions,
            'cash_conversion': cash_conversion,
            'p_fcf': p_fcf,
            'pe': pe,
            'roic': roic,
            'rev_growth_3yr': rev_growth_3yr,
            'earn_growth_3yr': earn_growth_3yr,
            'buffett_buy_price': buffett_buy_price,
            'buffett_buy_price_date': item.get('buffett_buy_price_date'),
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
            'return_6m': None,
            'return_1y': None,
            'mkt_cap_billions': None,
            'revenue_billions': None,
            'net_income_billions': None,
            'net_margin_pct': None,
            'fcf_billions': None,
            'cash_conversion': None,
            'p_fcf': None,
            'pe': None,
            'roic': None,
            'rev_growth_3yr': None,
            'earn_growth_3yr': None,
            'buffett_buy_price': item.get('buffett_buy_price'),
            'buffett_buy_price_date': item.get('buffett_buy_price_date'),
            'gap_from_buffett': None,
            'chance_of_10x': item.get('chance_of_10x'),
        }


@app.route('/')
def index():
    watchlist = load_watchlist()
    with ThreadPoolExecutor(max_workers=8) as executor:
        stocks = list(executor.map(get_stock_data, watchlist))
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
    if 'buffett_buy_price_date' in data:
        val = data['buffett_buy_price_date']
        update_data['buffett_buy_price_date'] = val if val != '' else None
    supabase.table('watchlist').update(update_data).eq('ticker', ticker).execute()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
