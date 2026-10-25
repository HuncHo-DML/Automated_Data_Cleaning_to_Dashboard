# Live dashboard: reads messy NovaMart data from GitHub, cleans it, and refreshes every minute
import re
import time

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

DATA_URL = 'https://raw.githubusercontent.com/HuncHo-DML/novamart_data_cleaning/refs/heads/main/novamart_orders_messy.csv'
REFRESH_SECONDS = 60

st.set_page_config(page_title='NovaMart Live Dashboard', layout='wide')

MISSING_MARKERS = ['N/A', 'NA', 'null', '-', 'None', 'missing', '?', '']


def parse_date(s):
    out = pd.Series(pd.NaT, index=s.index, dtype='datetime64[ns]')
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m-%d-%Y', '%d %b %Y', '%B %d, %Y']:
        still_empty = out.isna()
        parsed = pd.to_datetime(s[still_empty], format=fmt, errors='coerce')
        out[still_empty] = parsed.astype('datetime64[ns]')
    return out


def to_money(s):
    s = s.astype('string').str.lower().str.replace(r'[^\d.\-]', '', regex=True)
    return pd.to_numeric(s, errors='coerce')


def clean_phone(p):
    if pd.isna(p):
        return pd.NA
    digits = re.sub(r'\D', '', p)
    if digits.startswith('234') and len(digits) == 13:
        digits = '0' + digits[3:]
    if len(digits) == 10:
        digits = '0' + digits
    return digits if len(digits) == 11 else pd.NA


def clean_data(raw):
    log = {'raw_rows': len(raw)}
    df = raw.copy()

    df.columns = (df.columns.str.strip().str.lower()
                  .str.replace(r'[^\w\s]', '', regex=True)
                  .str.replace(r'\s+', '_', regex=True))
    df = df.rename(columns={'dob': 'date_of_birth', 'phone_no': 'phone', 'email_address': 'email',
                            'qty': 'quantity', 'unit_price_ngn': 'unit_price'})

    for c in df.columns:
        df[c] = df[c].astype('string').str.strip()
        df[c] = df[c].replace({m: pd.NA for m in MISSING_MARKERS})
    before = len(df)
    df = df.dropna(how='all')
    log['blank_rows_removed'] = before - len(df)

    df['customer_name'] = (df['customer_name']
                           .str.replace(r'^([^,]+),\s*(.+)$', r'\2 \1', regex=True)
                           .str.replace(r'\s+', ' ', regex=True)
                           .str.title())
    df['product_name'] = df['product_name'].str.title()

    gender_map = {'male': 'Male', 'm': 'Male', 'female': 'Female', 'f': 'Female'}
    cat_map = {'electronic': 'Electronics', 'electronics': 'Electronics', 'fashion': 'Fashion',
               'fashon': 'Fashion', 'home & kitchen': 'Home & Kitchen',
               'home and kitchen': 'Home & Kitchen', 'home&kitchen': 'Home & Kitchen',
               'beauty': 'Beauty', 'beuaty': 'Beauty', 'groceries': 'Groceries', 'grocery': 'Groceries'}
    pay_map = {'card': 'Card', 'debit card': 'Card', 'bank transfer': 'Bank Transfer',
               'transfer': 'Bank Transfer', 'cash on delivery': 'Cash on Delivery',
               'cod': 'Cash on Delivery', 'ussd': 'USSD', 'wallet': 'Wallet', 'e-wallet': 'Wallet'}
    status_map = {'delivered': 'Delivered', 'deliverd': 'Delivered', 'pending': 'Pending',
                  'cancelled': 'Cancelled', 'canceled': 'Cancelled', 'returned': 'Returned',
                  'shipped': 'Shipped'}
    state_map = {'lagos': 'Lagos', 'lagos state': 'Lagos', 'lag': 'Lagos', 'fct': 'FCT',
                 'f.c.t': 'FCT', 'abuja': 'FCT', 'rivers': 'Rivers', 'rivers state': 'Rivers',
                 'kano': 'Kano', 'kano state': 'Kano', 'oyo': 'Oyo', 'oyo state': 'Oyo',
                 'enugu': 'Enugu', 'enugu state': 'Enugu', 'kaduna': 'Kaduna',
                 'kaduna state': 'Kaduna', 'edo': 'Edo', 'edo state': 'Edo', 'imo': 'Imo',
                 'imo state': 'Imo', 'ogun': 'Ogun', 'ogun state': 'Ogun', 'plateau': 'Plateau',
                 'plateau state': 'Plateau'}
    for col, mapping in [('gender', gender_map), ('product_category', cat_map),
                         ('payment_method', pay_map), ('delivery_status', status_map),
                         ('state', state_map)]:
        df[col] = df[col].str.lower().map(mapping).astype('object')
    df['city'] = df['city'].str.title().replace({'P/H': 'Port Harcourt'}).astype('object')

    df['email'] = df['email'].str.lower()
    bad_email = ~df['email'].fillna('a@b.com').str.match(r'^[^@\s]+@[^@\s]+\.[a-z]{2,}$')
    bad_email = bad_email | df['email'].fillna('').str.endswith('.con')
    log['invalid_emails_removed'] = int(bad_email.sum())
    df.loc[bad_email, 'email'] = pd.NA
    df['phone'] = df['phone'].apply(clean_phone).astype('string')

    df['unit_price'] = to_money(df['unit_price'])
    df['total_amount'] = to_money(df['total_amount'])
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
    df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
    d = pd.to_numeric(df['discount'].str.replace('%', '', regex=False), errors='coerce')
    df['discount'] = d.where(d > 1, d * 100)

    for c in ['date_of_birth', 'signup_date', 'order_date']:
        df[c] = parse_date(df[c])

    df['order_id'] = df['order_id'].str.upper()
    before = len(df)
    df = df.drop_duplicates(subset='order_id', keep='first')
    log['duplicates_removed'] = before - len(df)

    today = pd.Timestamp.today().normalize()
    bad_qty = (df['quantity'] <= 0) | (df['quantity'] > 100) | (df['quantity'] % 1 != 0)
    bad_rating = (df['rating'] < 1) | (df['rating'] > 5) | (df['rating'] % 1 != 0)
    bad_price = (df['unit_price'] <= 0) | (df['unit_price'] > 1_000_000)
    bad_disc = (df['discount'] < 0) | (df['discount'] > 100)
    log['impossible_values_removed'] = int(bad_qty.sum() + bad_rating.sum() + bad_price.sum() + bad_disc.sum())
    df.loc[bad_qty.fillna(False), 'quantity'] = np.nan
    df.loc[bad_rating.fillna(False), 'rating'] = np.nan
    df.loc[bad_price.fillna(False), 'unit_price'] = np.nan
    df.loc[bad_disc.fillna(False), 'discount'] = np.nan
    df.loc[(df['date_of_birth'] < '1920-01-01') | (df['date_of_birth'] > today), 'date_of_birth'] = pd.NaT
    df.loc[df['order_date'] > today, 'order_date'] = pd.NaT

    expected = (df['quantity'] * df['unit_price'] * (1 - df['discount'].fillna(0) / 100)).round(2)
    mismatch = ((expected - df['total_amount']).abs() > 1).fillna(False).astype(bool)
    log['totals_recalculated'] = int(mismatch.sum())

    df['rating_missing'] = df['rating'].isna()
    median_price = df.groupby('product_name')['unit_price'].transform('median')
    df['unit_price'] = df['unit_price'].fillna(median_price)
    for c in ['customer_name', 'gender', 'payment_method', 'city', 'state', 'delivery_status',
              'product_category']:
        df[c] = df[c].fillna('Unknown')
    df['quantity'] = df['quantity'].fillna(df['quantity'].median())
    df['notes'] = df['notes'].fillna('')
    expected = (df['quantity'] * df['unit_price'] * (1 - df['discount'].fillna(0) / 100)).round(2)
    df['total_amount'] = df['total_amount'].mask(mismatch, expected)
    df['total_amount'] = df['total_amount'].fillna(expected)

    df['is_member'] = df['is_member'].str.lower().isin(['yes', 'y', 'true', '1'])
    df['quantity'] = df['quantity'].astype('Int64')
    df['rating'] = df['rating'].astype('Int64')

    for c in ['unit_price', 'discount', 'total_amount']:
        df[c] = df[c].astype('float64')
    for c in df.select_dtypes('string').columns:
        df[c] = df[c].astype('object')

    log['clean_rows'] = len(df)
    return df.reset_index(drop=True), log


@st.cache_data(max_entries=2, show_spinner=False)
def load_and_clean(url):
    raw = pd.read_csv(url, dtype=str, keep_default_na=False)
    return clean_data(raw)


@st.fragment(run_every=REFRESH_SECONDS)
def dashboard():
    bucket = int(time.time() // REFRESH_SECONDS)
    try:
        df, log = load_and_clean(f'{DATA_URL}?v={bucket}')
    except Exception as error:
        st.error('Could not load the data from GitHub. Check DATA_URL at the top of app.py.')
        st.code(str(error))
        return

    st.title('NovaMart Live Orders Dashboard')
    st.caption(f'Last check: {time.strftime("%H:%M:%S", time.gmtime())} UTC. '
               f'The page checks GitHub for new data every {REFRESH_SECONDS} seconds.')

    with st.expander('Filters', expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        states = c1.multiselect('State', sorted(df['state'].unique()), default=sorted(df['state'].unique()))
        cats = c2.multiselect('Product category', sorted(df['product_category'].unique()),
                              default=sorted(df['product_category'].unique()))
        statuses = c3.multiselect('Delivery status', sorted(df['delivery_status'].unique()),
                                  default=sorted(df['delivery_status'].unique()))
        pays = c4.multiselect('Payment method', sorted(df['payment_method'].unique()),
                              default=sorted(df['payment_method'].unique()))
        c5, c6 = st.columns(2)
        members_only = c5.checkbox('Members only')
        min_date = df['order_date'].min().date()
        max_date = df['order_date'].max().date()
        dates = c6.date_input('Order date range', value=(min_date, max_date),
                              min_value=min_date, max_value=max_date)

    d = df[df['state'].isin(states) & df['product_category'].isin(cats) &
           df['delivery_status'].isin(statuses) & df['payment_method'].isin(pays)]
    if members_only:
        d = d[d['is_member']]
    if len(dates) == 2:
        start, end = pd.Timestamp(dates[0]), pd.Timestamp(dates[1])
        d = d[d['order_date'].isna() | d['order_date'].between(start, end)]

    if d.empty:
        st.warning('No orders match these filters.')
        return

    revenue = d['total_amount'].sum()
    orders = d['order_id'].nunique()
    rating = d['rating'].mean()
    delivered = (d['delivery_status'] == 'Delivered').mean() * 100

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric('Revenue', f'\u20a6{revenue:,.0f}')
    k2.metric('Orders', f'{orders:,}')
    k3.metric('Average order', f'\u20a6{revenue / orders:,.0f}')
    k4.metric('Average rating', 'n/a' if pd.isna(rating) else f'{rating:.2f}')
    k5.metric('Delivered', f'{delivered:.1f}%')

    col1, col2 = st.columns(2)
    dated = d.dropna(subset=['order_date'])
    if len(dated) > 0:
        month = dated['order_date'].dt.to_period('M').dt.to_timestamp()
        monthly = dated.groupby(month)['total_amount'].sum().reset_index()
        col1.plotly_chart(px.line(monthly, x='order_date', y='total_amount', markers=True,
                                  title='Revenue by month'))
    by_cat = d.groupby('product_category', as_index=False)['total_amount'].sum()
    col2.plotly_chart(px.bar(by_cat, x='product_category', y='total_amount',
                             title='Revenue by category'))

    col3, col4 = st.columns(2)
    by_state = d.groupby('state').size().reset_index(name='orders')
    col3.plotly_chart(px.bar(by_state, x='state', y='orders', title='Orders by state'))
    col4.plotly_chart(px.pie(d, names='payment_method', values='total_amount',
                             title='Revenue by payment method'))

    col5, col6 = st.columns(2)
    by_status = d.groupby('delivery_status').size().reset_index(name='orders')
    col5.plotly_chart(px.bar(by_status, x='delivery_status', y='orders',
                             title='Orders by delivery status'))
    rated = d.dropna(subset=['rating'])
    if len(rated) > 0:
        col6.plotly_chart(px.histogram(rated, x='rating', nbins=5, title='Rating distribution'))

    with st.expander('What the cleaning step did to the GitHub file'):
        labels = {'raw_rows': 'Rows in the GitHub file', 'blank_rows_removed': 'Blank rows removed',
                  'duplicates_removed': 'Duplicate orders removed',
                  'invalid_emails_removed': 'Invalid emails set to missing',
                  'impossible_values_removed': 'Impossible values set to missing',
                  'totals_recalculated': 'Totals recalculated', 'clean_rows': 'Clean rows used'}
        st.dataframe(pd.DataFrame({'Step': list(labels.values()), 'Rows': [log[k] for k in labels]}),
                     hide_index=True)

    with st.expander('Show the clean data table'):
        st.dataframe(d)
    st.download_button('Download the clean data (CSV)', d.to_csv(index=False),
                       'novamart_orders_clean.csv', 'text/csv')


dashboard()
