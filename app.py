# Live dashboard: reads messy NovaMart data from GitHub, cleans it, and refreshes every minute
import io
import re
import time

import matplotlib
import matplotlib.dates
matplotlib.use('Agg')  # no display needed on the server
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from matplotlib.backends.backend_pdf import PdfPages

DATA_URL = 'https://raw.githubusercontent.com/HuncHo-DML/novamart_data_cleaning/refs/heads/main/novamart_orders_messy.csv'
REFRESH_SECONDS = 60

st.set_page_config(page_title='NovaMart Live Dashboard', layout='wide',
                   initial_sidebar_state='expanded')

# Text values that really mean "no data"
MISSING_MARKERS = ['N/A', 'NA', 'null', '-', 'None', 'missing', '?', '']


def parse_date(s):
    # Try each known date format in turn on whatever is still unparsed
    out = pd.Series(pd.NaT, index=s.index, dtype='datetime64[ns]')
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m-%d-%Y', '%d %b %Y', '%B %d, %Y']:
        still_empty = out.isna()
        parsed = pd.to_datetime(s[still_empty], format=fmt, errors='coerce')
        out[still_empty] = parsed.astype('datetime64[ns]')
    return out


def to_money(s):
    # Strip currency symbols and commas, keep digits, dot and minus
    s = s.astype('string').str.lower().str.replace(r'[^\d.\-]', '', regex=True)
    return pd.to_numeric(s, errors='coerce')


def clean_phone(p):
    # Normalise Nigerian numbers to the 11-digit 0XXXXXXXXXX form
    if pd.isna(p):
        return pd.NA
    digits = re.sub(r'\D', '', p)
    if digits.startswith('234') and len(digits) == 13:
        digits = '0' + digits[3:]
    if len(digits) == 10:
        digits = '0' + digits
    return digits if len(digits) == 11 else pd.NA


def clean_data(raw):
    log = {'raw_rows': len(raw)}  # counts shown in the cleaning summary
    df = raw.copy()

    # Tidy column names
    df.columns = (df.columns.str.strip().str.lower()
                  .str.replace(r'[^\w\s]', '', regex=True)
                  .str.replace(r'\s+', '_', regex=True))
    df = df.rename(columns={'dob': 'date_of_birth', 'phone_no': 'phone', 'email_address': 'email',
                            'qty': 'quantity', 'unit_price_ngn': 'unit_price'})

    # Trim text and turn missing markers into real NA
    for c in df.columns:
        df[c] = df[c].astype('string').str.strip()
        df[c] = df[c].replace({m: pd.NA for m in MISSING_MARKERS})
    before = len(df)
    df = df.dropna(how='all')
    log['blank_rows_removed'] = before - len(df)

    # Names: "Last, First" -> "First Last", consistent casing
    df['customer_name'] = (df['customer_name']
                           .str.replace(r'^([^,]+),\s*(.+)$', r'\2 \1', regex=True)
                           .str.replace(r'\s+', ' ', regex=True)
                           .str.title())
    df['product_name'] = df['product_name'].str.title()

    # Lookup tables that fix typos and variants
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

    # Emails and phones
    df['email'] = df['email'].str.lower()
    bad_email = ~df['email'].fillna('a@b.com').str.match(r'^[^@\s]+@[^@\s]+\.[a-z]{2,}$')
    bad_email = bad_email | df['email'].fillna('').str.endswith('.con')
    log['invalid_emails_removed'] = int(bad_email.sum())
    df.loc[bad_email, 'email'] = pd.NA
    df['phone'] = df['phone'].apply(clean_phone).astype('string')

    # Numbers and dates
    df['unit_price'] = to_money(df['unit_price'])
    df['total_amount'] = to_money(df['total_amount'])
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
    df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
    # Discounts may be 0.1 or 10 or '10%'; store as percent
    d = pd.to_numeric(df['discount'].str.replace('%', '', regex=False), errors='coerce')
    df['discount'] = d.where(d > 1, d * 100)

    for c in ['date_of_birth', 'signup_date', 'order_date']:
        df[c] = parse_date(df[c])

    # Same order_id twice = duplicate, keep the first
    df['order_id'] = df['order_id'].str.upper()
    before = len(df)
    df = df.drop_duplicates(subset='order_id', keep='first')
    log['duplicates_removed'] = before - len(df)

    # Impossible values become missing
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

    # Totals that don't equal qty x price x discount get recalculated
    expected = (df['quantity'] * df['unit_price'] * (1 - df['discount'].fillna(0) / 100)).round(2)
    mismatch = ((expected - df['total_amount']).abs() > 1).fillna(False).astype(bool)
    log['totals_recalculated'] = int(mismatch.sum())

    # Fill gaps: price from product median, text with 'Unknown'
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

    # Final types
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


def get_data():
    # The ?v= bucket changes every minute so GitHub's cache never serves stale data
    bucket = int(time.time() // REFRESH_SECONDS)
    return load_and_clean(f'{DATA_URL}?v={bucket}')


def data_signature(df):
    # Cheap fingerprint used to spot when the GitHub file has changed
    return (len(df), round(float(df['total_amount'].sum()), 2))


def apply_filters(df, states, cats, statuses, pays, members_only, dates):
    d = df[df['state'].isin(states) & df['product_category'].isin(cats) &
           df['delivery_status'].isin(statuses) & df['payment_method'].isin(pays)]
    if members_only:
        d = d[d['is_member']]
    if len(dates) == 2:
        start, end = pd.Timestamp(dates[0]), pd.Timestamp(dates[1])
        # Orders with no date are kept so they are not silently dropped
        d = d[d['order_date'].isna() | d['order_date'].between(start, end)]
    return d


def summarise(d):
    revenue = d['total_amount'].sum()
    orders = d['order_id'].nunique()
    return {'revenue': revenue, 'orders': orders, 'avg_order': revenue / orders,
            'rating': d['rating'].mean(), 'delivered': (d['delivery_status'] == 'Delivered').mean() * 100}


# ---------- PDF slide report ----------

SLIDE_W, SLIDE_H = 13.33, 7.5   # 16:9 landscape, like a slide
NAVY, ACCENT, GREY = '#1f2a44', '#2a7de1', '#6b7280'


def new_slide(pdf, title, page):
    fig = plt.figure(figsize=(SLIDE_W, SLIDE_H))
    fig.text(0.05, 0.92, title, fontsize=26, fontweight='bold', color=NAVY, va='center')
    fig.add_artist(plt.Line2D([0.05, 0.95], [0.87, 0.87], color=ACCENT, lw=2))
    fig.text(0.05, 0.03, 'NovaMart Orders Report', fontsize=9, color=GREY)
    fig.text(0.95, 0.03, str(page), fontsize=9, color=GREY, ha='right')
    return fig


def style_axes(ax, title):
    ax.set_title(title, fontsize=14, color=NAVY, loc='left', pad=12)
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(labelsize=10)


def money_axis(ax):
    ax.yaxis.set_major_formatter(lambda v, _: f'₦{v / 1e6:.1f}M' if v >= 1e6 else f'₦{v:,.0f}')


@st.cache_data(max_entries=3, show_spinner=False)
def build_pdf(d, log, filter_lines):
    # Builds one PDF page per slide from the currently filtered data
    k = summarise(d)
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        page = 1

        # Title slide with the filters that were active
        fig = plt.figure(figsize=(SLIDE_W, SLIDE_H))
        fig.patch.set_facecolor(NAVY)
        fig.text(0.07, 0.62, 'NovaMart Orders', fontsize=44, fontweight='bold', color='white')
        fig.text(0.07, 0.53, 'Dashboard summary report', fontsize=22, color='#c7d2fe')
        fig.text(0.07, 0.40, 'Filters applied', fontsize=13, color='#93c5fd', fontweight='bold')
        for i, line in enumerate(filter_lines):
            fig.text(0.07, 0.36 - i * 0.04, line, fontsize=12, color='white')
        fig.text(0.07, 0.05, f'Generated {time.strftime("%d %b %Y, %H:%M", time.gmtime())} UTC',
                 fontsize=10, color='#c7d2fe')
        pdf.savefig(fig)
        plt.close(fig)

        # KPI slide
        page += 1
        fig = new_slide(pdf, 'Key numbers', page)
        tiles = [('Revenue', f'₦{k["revenue"]:,.0f}'), ('Orders', f'{k["orders"]:,}'),
                 ('Average order', f'₦{k["avg_order"]:,.0f}'),
                 ('Average rating', 'n/a' if pd.isna(k['rating']) else f'{k["rating"]:.2f}'),
                 ('Delivered', f'{k["delivered"]:.1f}%')]
        for i, (label, value) in enumerate(tiles):
            x = 0.05 + (i % 3) * 0.31
            y = 0.58 if i < 3 else 0.25
            fig.patches.append(plt.Rectangle((x, y), 0.28, 0.2, transform=fig.transFigure,
                                             facecolor='#f1f5f9', edgecolor='none'))
            fig.text(x + 0.02, y + 0.13, label, fontsize=13, color=GREY)
            fig.text(x + 0.02, y + 0.04, value, fontsize=26, fontweight='bold', color=NAVY)
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 3: revenue by month + revenue by category
        page += 1
        fig = new_slide(pdf, 'Revenue trends', page)
        ax1 = fig.add_axes([0.07, 0.20, 0.40, 0.58])
        dated = d.dropna(subset=['order_date'])
        if len(dated):
            month = dated['order_date'].dt.to_period('M').dt.to_timestamp()
            monthly = dated.groupby(month)['total_amount'].sum()
            ax1.plot(monthly.index, monthly.values, marker='o', color=ACCENT)
            ax1.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%b %y'))
            ax1.tick_params(axis='x', rotation=45)
        style_axes(ax1, 'Revenue by month')
        money_axis(ax1)
        ax2 = fig.add_axes([0.56, 0.20, 0.40, 0.58])
        by_cat = d.groupby('product_category')['total_amount'].sum().sort_values(ascending=False)
        ax2.bar(by_cat.index, by_cat.values, color=ACCENT)
        ax2.tick_params(axis='x', rotation=30)
        style_axes(ax2, 'Revenue by category')
        money_axis(ax2)
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 4: orders by state + payment method share
        page += 1
        fig = new_slide(pdf, 'Where and how customers buy', page)
        ax1 = fig.add_axes([0.07, 0.20, 0.40, 0.58])
        by_state = d.groupby('state').size().sort_values(ascending=False)
        ax1.bar(by_state.index, by_state.values, color=ACCENT)
        ax1.tick_params(axis='x', rotation=45)
        style_axes(ax1, 'Orders by state')
        ax2 = fig.add_axes([0.55, 0.14, 0.40, 0.58])
        by_pay = d.groupby('payment_method')['total_amount'].sum()
        ax2.pie(by_pay.values, labels=by_pay.index, autopct='%1.0f%%', startangle=90,
                textprops={'fontsize': 10})
        ax2.set_title('Revenue by payment method', fontsize=14, color=NAVY, loc='left', pad=12)
        pdf.savefig(fig)
        plt.close(fig)

        # Slide 5: delivery status + rating distribution
        page += 1
        fig = new_slide(pdf, 'Delivery and customer ratings', page)
        ax1 = fig.add_axes([0.07, 0.20, 0.40, 0.58])
        by_status = d.groupby('delivery_status').size().sort_values(ascending=False)
        ax1.bar(by_status.index, by_status.values, color=ACCENT)
        style_axes(ax1, 'Orders by delivery status')
        ax2 = fig.add_axes([0.56, 0.20, 0.40, 0.58])
        counts = d['rating'].dropna().astype(int).value_counts().reindex(range(1, 6), fill_value=0)
        ax2.bar(counts.index, counts.values, color=ACCENT)
        style_axes(ax2, 'Rating distribution')
        pdf.savefig(fig)
        plt.close(fig)

        # Last slide: what the cleaning step did
        page += 1
        fig = new_slide(pdf, 'Data cleaning summary', page)
        labels = [('raw_rows', 'Rows in the GitHub file'), ('blank_rows_removed', 'Blank rows removed'),
                  ('duplicates_removed', 'Duplicate orders removed'),
                  ('invalid_emails_removed', 'Invalid emails set to missing'),
                  ('impossible_values_removed', 'Impossible values set to missing'),
                  ('totals_recalculated', 'Totals recalculated'), ('clean_rows', 'Clean rows used')]
        for i, (key, text) in enumerate(labels):
            y = 0.76 - i * 0.09
            fig.text(0.08, y, text, fontsize=16, color=NAVY)
            fig.text(0.60, y, f'{log[key]:,}', fontsize=16, color=NAVY, fontweight='bold', ha='right')
        pdf.savefig(fig)
        plt.close(fig)
    return buf.getvalue()


def describe(picked, options):
    # Short text for the report: "All" or the chosen values
    return 'All' if len(picked) == len(options) else (', '.join(picked) or 'None')


# ---------- Page ----------

@st.fragment(run_every=REFRESH_SECONDS)
def dashboard(states, cats, statuses, pays, members_only, dates):
    # Only this block re-runs every minute; sidebar filters are passed in
    try:
        df, log = get_data()
    except Exception as error:
        st.error('Could not load the data from GitHub. Check DATA_URL at the top of app.py.')
        st.code(str(error))
        return

    # New data on GitHub: rerun the whole page so the sidebar options update too
    if data_signature(df) != st.session_state.get('data_sig'):
        st.rerun()

    st.caption(f'Last check: {time.strftime("%H:%M:%S", time.gmtime())} UTC. '
               f'The page checks GitHub for new data every {REFRESH_SECONDS} seconds.')

    d = apply_filters(df, states, cats, statuses, pays, members_only, dates)
    if d.empty:
        st.warning('No orders match these filters.')
        return

    k = summarise(d)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric('Revenue', f'₦{k["revenue"]:,.0f}')
    k2.metric('Orders', f'{k["orders"]:,}')
    k3.metric('Average order', f'₦{k["avg_order"]:,.0f}')
    k4.metric('Average rating', 'n/a' if pd.isna(k['rating']) else f'{k["rating"]:.2f}')
    k5.metric('Delivered', f'{k["delivered"]:.1f}%')

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

    # Downloads: CSV of the filtered rows and the PDF slide report
    filter_lines = (
        f'State: {describe(states, sorted(df["state"].unique()))}',
        f'Product category: {describe(cats, sorted(df["product_category"].unique()))}',
        f'Delivery status: {describe(statuses, sorted(df["delivery_status"].unique()))}',
        f'Payment method: {describe(pays, sorted(df["payment_method"].unique()))}',
        f'Members only: {"Yes" if members_only else "No"}',
        'Order date: ' + (f'{dates[0]} to {dates[1]}' if len(dates) == 2 else 'All'),
    )
    b1, b2 = st.columns(2)
    b1.download_button('Download the clean data (CSV)', d.to_csv(index=False),
                       'novamart_orders_clean.csv', 'text/csv')
    b2.download_button('Download summary report (PDF slides)', build_pdf(d, log, filter_lines),
                       'novamart_dashboard_report.pdf', 'application/pdf')


st.title('NovaMart Live Orders Dashboard')

try:
    data, _ = get_data()
except Exception as error:
    st.error('Could not load the data from GitHub. Check DATA_URL at the top of app.py.')
    st.code(str(error))
    st.stop()
st.session_state['data_sig'] = data_signature(data)

# Filters live in the left sidebar. They sit outside the fragment because
# Streamlit does not allow sidebar widgets inside one.
with st.sidebar:
    st.header('Filters')
    all_states = sorted(data['state'].unique())
    all_cats = sorted(data['product_category'].unique())
    all_statuses = sorted(data['delivery_status'].unique())
    all_pays = sorted(data['payment_method'].unique())
    f_states = st.multiselect('State', all_states, default=all_states)
    f_cats = st.multiselect('Product category', all_cats, default=all_cats)
    f_statuses = st.multiselect('Delivery status', all_statuses, default=all_statuses)
    f_pays = st.multiselect('Payment method', all_pays, default=all_pays)
    f_members = st.checkbox('Members only')
    if data['order_date'].notna().any():
        min_date = data['order_date'].min().date()
        max_date = data['order_date'].max().date()
        f_dates = st.date_input('Order date range', value=(min_date, max_date),
                                min_value=min_date, max_value=max_date)
    else:
        f_dates = ()

dashboard(f_states, f_cats, f_statuses, f_pays, f_members, f_dates)
