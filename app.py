from flask import Flask, render_template, request, redirect, url_for, jsonify
from supabase import create_client
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from datetime import datetime, date, timezone
import requests
import re
import os

load_dotenv()

app = Flask(__name__)
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

SA_BASE = 'https://stockanalysis.com/stocks'
SA_API  = 'https://stockanalysis.com/api/symbol/s'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
FUNDAMENTAL_REFRESH_DAYS = 90


# ── Number helpers ────────────────────────────────────────────────────────────

def safe_round(val, decimals=2):
    try:
        return round(float(val), decimals) if val is not None else None
    except Exception:
        return None

def m_float(s):
    """Parse a millions-denominated string to a plain float (stays in millions)."""
    if not s or str(s).strip() in ('-', ''):
        return None
    try:
        return float(str(s).replace(',', '').strip())
    except Exception:
        return None

def m_to_b(s):
    """Parse a millions-denominated string and convert to billions for storage."""
    f = m_float(s)
    return f / 1000 if f is not None else None

def parse_bm(s):
    """Parse a B/M/T-suffixed overview string to billions.
    '11.28B-28%' → 11.28,  '596.52M' → 0.597,  '3.3T' → 3300"""
    if not s or str(s).strip() in ('-', 'n/a', ''):
        return None
    try:
        m = re.match(r'^(-?[\d.]+)([BMKT]?)', str(s).strip().replace(',', ''))
        if not m:
            return None
        val, suffix = float(m.group(1)), m.group(2)
        if suffix == 'T': return val * 1000
        if suffix == 'B': return val
        if suffix == 'M': return val / 1000
        if suffix == 'K': return val / 1_000_000
        return val
    except Exception:
        return None

def parse_pct(s):
    """'8.2%' → 8.2,  '-1.27%' → -1.27,  'Pro' → None"""
    if not s or str(s).strip() in ('-', 'Pro', ''):
        return None
    try:
        return float(str(s).replace('%', '').replace('+', '').strip())
    except Exception:
        return None

def parse_float(s):
    if not s or str(s).strip() in ('-', 'n/a', ''):
        return None
    try:
        return float(str(s).replace(',', '').strip())
    except Exception:
        return None


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def sa_fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            return BeautifulSoup(r.text, 'html.parser')
        print(f"HTTP {r.status_code}: {url}")
    except Exception as e:
        print(f"Fetch error {url}: {e}")
    return None

def sa_api(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            j = r.json()
            return j.get('data') if isinstance(j, dict) else j
    except Exception as e:
        print(f"API error {url}: {e}")
    return None


# ── Table parsing ─────────────────────────────────────────────────────────────

def parse_kv(soup):
    """Parse all tables as flat key→value pairs, no header row skipped.
    Used for the overview page where Market Cap is the very first row."""
    result = {}
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cols = row.find_all(['th', 'td'])
            if len(cols) >= 2:
                result[cols[0].get_text(strip=True)] = cols[1].get_text(strip=True)
    return result

def parse_tables(soup):
    """Return list of (header_list, row_dict) for every <table> on the page."""
    result = []
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        header, data, first = [], {}, True
        for row in rows:
            cols = row.find_all(['th', 'td'])
            if not cols:
                continue
            if first:
                header = [c.get_text(strip=True) for c in cols]
                first = False
                continue
            label = cols[0].get_text(strip=True)
            data[label] = [c.get_text(strip=True) for c in cols[1:]]
        result.append((header, data))
    return result

def tbl_row(tables, key):
    """Exact key lookup across all tables — returns the values list."""
    for _, data in tables:
        if key in data:
            return data[key]
    return None

def tbl_val(tables, key, col=0):
    """Return a single cell value (default first column) from an exact-match row."""
    r = tbl_row(tables, key)
    return r[col] if r and len(r) > col else None

def find_data_row(tables, prefix):
    """Find the value row for a metric like 'Revenue', skipping pure-percent rows.
    StockAnalysis merges the label with its sub-label, e.g. 'RevenueRevenue Growth',
    so we match by prefix and exclude rows whose first value is a percentage."""
    for _, data in tables:
        for k, v in data.items():
            if k.startswith(prefix) and v and not v[0].endswith('%'):
                return v
    return None


# ── Staleness checks ──────────────────────────────────────────────────────────

def is_stale_daily(item):
    updated = item.get('daily_updated_at')
    if not updated:
        return True
    try:
        return datetime.fromisoformat(updated.replace('Z', '+00:00')).date() < date.today()
    except Exception:
        return True

def is_stale_fundamentals(item):
    updated = item.get('fundamentals_updated_at')
    if not updated:
        return True
    try:
        days_old = (date.today() - datetime.fromisoformat(updated.replace('Z', '+00:00')).date()).days
        return days_old > FUNDAMENTAL_REFRESH_DAYS
    except Exception:
        return True

def load_watchlist():
    return supabase.table('watchlist').select('*').execute().data


# ── Daily refresh ─────────────────────────────────────────────────────────────
# Fetches: price, change%, mkt cap, PE, analyst rating, price target, 6M/1Y returns

def refresh_daily(item):
    ticker = item['ticker']
    try:
        soup = sa_fetch(f'{SA_BASE}/{ticker.lower()}/')
        if not soup:
            return

        # Company name from page title: "Domino's Pizza (DPZ) Stock..."
        company_name = ticker
        title_tag = soup.find('title')
        if title_tag:
            m = re.match(r'^(.+?)\s*\(', title_tag.get_text())
            if m:
                company_name = m.group(1).strip()

        # Current price — large bold div unique to the price display
        price = None
        price_tag = soup.find('div', class_=lambda c: c and 'text-4xl' in c and 'font-bold' in c)
        if price_tag:
            try:
                price = float(price_tag.get_text(strip=True).replace(',', ''))
            except Exception:
                pass

        # Change % — "(+1.23%)" or "(-1.23%)" sits near the price element
        change_pct = None
        if price_tag and price_tag.parent:
            for sib in price_tag.parent.find_all(['span', 'div']):
                m = re.search(r'\(([+-]?[\d.]+)%\)', sib.get_text(strip=True))
                if m:
                    raw = m.group(1)
                    # if no sign in the text, determine sign from the number itself
                    change_pct = safe_round(float(raw), 2)
                    break

        # Overview stats — parse_kv reads every row including Market Cap (first row)
        kv = parse_kv(soup)

        mkt_cap        = safe_round(parse_bm(kv.get('Market Cap')), 3)
        pe             = safe_round(parse_float(kv.get('PE Ratio')), 1)
        analyst_rating = kv.get('Analysts')

        # Price target: "380.64 (+11.6%)" → price_target=380.64, upside_pct=11.6
        price_target = upside_pct = None
        pt_str = kv.get('Price Target') or ''
        m = re.match(r'\$?([\d,.]+)\s*\(([+-][\d.]+)%\)', pt_str)
        if m:
            price_target = safe_round(float(m.group(1).replace(',', '')), 2)
            upside_pct   = safe_round(float(m.group(2)), 1)

        # 6M / 1Y returns via StockAnalysis internal history API
        # range=5Y gives 60 monthly closes; index 6 = 6M ago, index 12 = 1Y ago
        return_6m = return_1y = None
        hist = sa_api(f'{SA_API}/{ticker}/history?range=5Y&period=Monthly')
        if hist and len(hist) >= 13:
            c0, c6, c12 = hist[0].get('c'), hist[6].get('c'), hist[12].get('c')
            if c0 and c6:
                return_6m = safe_round((c0 - c6) / c6 * 100, 1)
            if c0 and c12:
                return_1y = safe_round((c0 - c12) / c12 * 100, 1)

        supabase.table('watchlist').update({
            'company_name':   company_name,
            'price':          price,
            'change_pct':     change_pct,
            'mkt_cap':        mkt_cap,
            'pe':             pe,
            'price_target':   price_target,
            'upside_pct':     upside_pct,
            'analyst_rating': analyst_rating,
            'return_6m':      return_6m,
            'return_1y':      return_1y,
            'daily_updated_at': datetime.now(timezone.utc).isoformat(),
        }).eq('ticker', ticker).execute()
        print(f"Daily OK: {ticker}")
    except Exception as e:
        print(f"Daily error {ticker}: {e}")


# ── Quarterly refresh ─────────────────────────────────────────────────────────
# Fetches: revenue, net income, FCF, ROIC, growth rates, EPS analyst estimate

def refresh_fundamentals(item):
    ticker = item['ticker']
    try:
        revenue = net_income = net_margin = None
        rev_growth_3yr = earn_growth_3yr = None
        operating_income_m = None  # kept in millions for ROIC calc

        # 1. Income statement
        soup = sa_fetch(f'{SA_BASE}/{ticker.lower()}/financials/')
        if soup:
            tables = parse_tables(soup)

            rev_row = find_data_row(tables, 'Revenue')
            ni_row  = find_data_row(tables, 'Net Income')
            oi_row  = find_data_row(tables, 'Operating Income')

            if rev_row:
                revenue = safe_round(m_to_b(rev_row[0]), 3)   # TTM → billions
                # 3yr CAGR: index 1 = FY2025, index 4 = FY2022
                if len(rev_row) >= 5:
                    r_new, r_old = m_float(rev_row[1]), m_float(rev_row[4])
                    if r_new and r_old and r_old > 0:
                        rev_growth_3yr = safe_round(((r_new / r_old) ** (1/3) - 1) * 100, 1)

            if ni_row:
                net_income = safe_round(m_to_b(ni_row[0]), 3)
                if len(ni_row) >= 5:
                    e_new, e_old = m_float(ni_row[1]), m_float(ni_row[4])
                    if e_new and e_old and e_old > 0 and e_new > 0:
                        earn_growth_3yr = safe_round(((e_new / e_old) ** (1/3) - 1) * 100, 1)

            if oi_row:
                operating_income_m = m_float(oi_row[0])   # stays in millions

            if revenue and net_income and revenue > 0:
                net_margin = safe_round((net_income / revenue) * 100, 1)

        # 2. Cash flow statement
        fcf = cash_conversion = None
        cash_income_tax_m = None
        soup = sa_fetch(f'{SA_BASE}/{ticker.lower()}/financials/cash-flow-statement/')
        if soup:
            tables = parse_tables(soup)
            fcf_row = tbl_row(tables, 'Free Cash Flow')       # Table 5
            tax_row = tbl_row(tables, 'Cash Income Tax Paid') # Table 6

            if fcf_row:
                fcf = safe_round(m_to_b(fcf_row[0]), 3)
            if tax_row:
                # Scan past any '-' entries (e.g. TTM not yet reported for recent fiscal year-end)
                for v in tax_row:
                    f = m_float(v)
                    if f is not None:
                        cash_income_tax_m = f
                        break

            if fcf and net_income and net_income != 0:
                cash_conversion = safe_round((fcf / net_income) * 100, 1)

        # 3. Balance sheet → ROIC
        roic = None
        soup = sa_fetch(f'{SA_BASE}/{ticker.lower()}/financials/balance-sheet/')
        if soup:
            tables = parse_tables(soup)
            total_debt_m = m_float(tbl_val(tables, 'Total Debt'))
            equity_m     = m_float(tbl_val(tables, "Shareholders' Equity"))
            cash_m       = m_float(tbl_val(tables, 'Cash & Equivalents'))

            if all(x is not None for x in [operating_income_m, cash_income_tax_m,
                                            net_income, total_debt_m, equity_m, cash_m]):
                ni_m  = net_income * 1000  # billions → millions
                denom = ni_m + cash_income_tax_m
                tax_rate = min(max(cash_income_tax_m / denom, 0), 0.5) if denom > 0 else 0.21
                nopat = operating_income_m * (1 - tax_rate)
                invested_capital = total_debt_m + equity_m - cash_m
                if invested_capital != 0:
                    roic = safe_round((nopat / invested_capital) * 100, 1)

        # 4. Forecast page → 1yr analyst EPS growth consensus
        eps_growth_1yr = None
        soup = sa_fetch(f'{SA_BASE}/{ticker.lower()}/forecast/')
        if soup:
            tables = parse_tables(soup)
            for header, data in tables:
                if header and header[0] == 'EPS Growth':
                    avg = data.get('Avg', [])
                    if avg:
                        eps_growth_1yr = safe_round(parse_pct(avg[0]), 1)
                    break

        supabase.table('watchlist').update({
            'revenue':        revenue,
            'net_income':     net_income,
            'net_margin':     net_margin,
            'fcf':            fcf,
            'cash_conversion': cash_conversion,
            'roic':           roic,
            'rev_growth_3yr': rev_growth_3yr,
            'earn_growth_3yr': earn_growth_3yr,
            'eps_growth_1yr': eps_growth_1yr,
            'fundamentals_updated_at': datetime.now(timezone.utc).isoformat(),
        }).eq('ticker', ticker).execute()
        print(f"Fundamentals OK: {ticker}")
    except Exception as e:
        print(f"Fundamentals error {ticker}: {e}")


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    watchlist = load_watchlist()

    stale_daily = [x for x in watchlist if is_stale_daily(x)]
    if stale_daily:
        with ThreadPoolExecutor(max_workers=3) as ex:
            ex.map(refresh_daily, stale_daily)

    stale_fund = [x for x in watchlist if is_stale_fundamentals(x)][:10]
    if stale_fund:
        with ThreadPoolExecutor(max_workers=3) as ex:
            ex.map(refresh_fundamentals, stale_fund)

    watchlist = load_watchlist()

    stocks = []
    for item in watchlist:
        price             = item.get('price')
        mkt_cap           = item.get('mkt_cap')
        fcf               = item.get('fcf')
        buffett_buy_price = item.get('buffett_buy_price')

        p_fcf = safe_round(mkt_cap / fcf, 1) if (mkt_cap and fcf and fcf > 0) else None
        gap_from_buffett = safe_round(
            ((price - buffett_buy_price) / buffett_buy_price) * 100, 1
        ) if (price and buffett_buy_price and buffett_buy_price > 0) else None

        stocks.append({
            'ticker':           item['ticker'],
            'name':             item.get('company_name') or item['ticker'],
            'price':            price,
            'change_pct':       item.get('change_pct'),
            'return_6m':        item.get('return_6m'),
            'return_1y':        item.get('return_1y'),
            'mkt_cap':          mkt_cap,
            'revenue':          item.get('revenue'),
            'net_income':       item.get('net_income'),
            'net_margin':       item.get('net_margin'),
            'fcf':              fcf,
            'cash_conversion':  item.get('cash_conversion'),
            'p_fcf':            p_fcf,
            'pe':               item.get('pe'),
            'roic':             item.get('roic'),
            'rev_growth_3yr':   item.get('rev_growth_3yr'),
            'earn_growth_3yr':  item.get('earn_growth_3yr'),
            'eps_growth_1yr':   item.get('eps_growth_1yr'),
            'price_target':     item.get('price_target'),
            'upside_pct':       item.get('upside_pct'),
            'analyst_rating':   item.get('analyst_rating'),
            'buffett_buy_price':      buffett_buy_price,
            'buffett_buy_price_date': item.get('buffett_buy_price_date'),
            'gap_from_buffett': gap_from_buffett,
            'chance_of_10x':    item.get('chance_of_10x'),
        })

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
            v = data[field]
            update_data[field] = float(v) if v != '' else None
    if 'buffett_buy_price_date' in data:
        v = data['buffett_buy_price_date']
        update_data['buffett_buy_price_date'] = v if v != '' else None
    supabase.table('watchlist').update(update_data).eq('ticker', ticker).execute()
    return jsonify({'ok': True})


@app.route('/refresh-all', methods=['POST'])
def refresh_all():
    watchlist = load_watchlist()
    with ThreadPoolExecutor(max_workers=3) as ex:
        ex.map(refresh_daily, watchlist)
    with ThreadPoolExecutor(max_workers=3) as ex:
        ex.map(refresh_fundamentals, watchlist)
    return redirect(url_for('index'))


@app.route('/refresh/<ticker>', methods=['POST'])
def refresh_stock(ticker):
    watchlist = load_watchlist()
    item = next((x for x in watchlist if x['ticker'] == ticker), None)
    if item:
        refresh_daily(item)
        refresh_fundamentals(item)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
