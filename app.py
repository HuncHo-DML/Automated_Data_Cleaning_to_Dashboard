# Streamlit dashboard for the clean NovaMart orders file
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title='NovaMart Dashboard', layout='wide')


@st.cache_data
def load_data():
    df = pd.read_csv('novamart_orders_clean.csv',
                     parse_dates=['date_of_birth', 'signup_date', 'order_date'])
    df['product_category'] = df['product_category'].fillna('Unknown')
    df['is_member'] = df['is_member'].astype(str).str.lower().eq('true')
    return df


df = load_data()

st.title('NovaMart Orders Dashboard')
st.sidebar.header('Filters')


def pick(label, column):
    options = sorted(df[column].dropna().unique().tolist())
    return st.sidebar.multiselect(label, options, default=options)


states = pick('State', 'state')
categories = pick('Product category', 'product_category')
statuses = pick('Delivery status', 'delivery_status')
payments = pick('Payment method', 'payment_method')
members_only = st.sidebar.checkbox('Members only')

min_date = df['order_date'].min().date()
max_date = df['order_date'].max().date()
dates = st.sidebar.date_input('Order date range', value=(min_date, max_date),
                              min_value=min_date, max_value=max_date)

d = df[df['state'].isin(states) & df['product_category'].isin(categories) &
       df['delivery_status'].isin(statuses) & df['payment_method'].isin(payments)]
if members_only:
    d = d[d['is_member']]
if len(dates) == 2:
    start, end = pd.Timestamp(dates[0]), pd.Timestamp(dates[1])
    d = d[d['order_date'].isna() | d['order_date'].between(start, end)]

if d.empty:
    st.warning('No orders match these filters.')
    st.stop()

revenue = d['total_amount'].sum()
orders = d['order_id'].nunique()
rating = d['rating'].mean()
delivered = (d['delivery_status'] == 'Delivered').mean() * 100

k1, k2, k3, k4 = st.columns(4)
k1.metric('Revenue', f'₦{revenue:,.0f}')
k2.metric('Orders', f'{orders:,}')
k3.metric('Average order', f'₦{revenue / orders:,.0f}')
k4.metric('Average rating', 'n/a' if pd.isna(rating) else f'{rating:.2f}')
st.caption(f'Delivered orders: {delivered:.1f}%')

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

with st.expander('Show the data table'):
    st.dataframe(d)
st.download_button('Download filtered data (CSV)', d.to_csv(index=False),
                   'filtered_orders.csv', 'text/csv')
