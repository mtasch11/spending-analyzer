import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# --- Database Setup ---
conn = sqlite3.connect('transactions.db', check_same_thread=False)
c = conn.cursor()

# Create tables if they don't exist
c.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    date TEXT,
    description TEXT,
    category TEXT,
    amount REAL
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS removed_merchants (
    merchant TEXT PRIMARY KEY
)
''')
conn.commit()

# --- Auto-categorization rules ---
CATEGORY_RULES = {
    'Starbucks': 'Coffee',
    'McDonald': 'Fast Food',
    'Uber': 'Transportation',
    'Lyft': 'Transportation',
    'Amazon': 'Shopping',
    'Target': 'Shopping',
    'Costco': 'Groceries',
    'Walmart': 'Shopping',
    # Add more as needed
}

def categorize(description):
    for keyword, category in CATEGORY_RULES.items():
        if keyword.lower() in description.lower():
            return category
    return 'Other'

# --- Functions ---
def add_transactions(df):
    expected_cols = ['Date', 'Description', 'Category', 'Amount']
    for col in expected_cols:
        if col not in df.columns:
            st.warning(f"Column '{col}' missing from uploaded file. Filling with blanks.")
            df[col] = ''

    df = df[expected_cols]
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['Category'] = df['Category'].fillna(df['Description'].apply(categorize))
    df.to_sql('transactions', conn, if_exists='append', index=False)

def get_transactions():
    df = pd.read_sql('SELECT * FROM transactions', conn, parse_dates=['date'])
    return df

def get_removed_merchants():
    removed = pd.read_sql('SELECT merchant FROM removed_merchants', conn)
    return removed['merchant'].tolist()

def remove_merchant(merchant):
    c.execute('INSERT OR IGNORE INTO removed_merchants (merchant) VALUES (?)', (merchant,))
    conn.commit()

def reinstate_merchants():
    c.execute('DELETE FROM removed_merchants')
    conn.commit()

# --- Streamlit App ---
st.title("💳 Credit Card Transaction Analyzer with Dashboard")

# Upload CSVs
uploaded_files = st.file_uploader("Upload CSV transactions", type="csv", accept_multiple_files=True)
if uploaded_files:
    for file in uploaded_files:
        df = pd.read_csv(file)
        add_transactions(df)
    st.success("Transactions added!")

# Load data
data = get_transactions()
removed_merchants = get_removed_merchants()
filtered_data = data[~data['description'].isin(removed_merchants)]
filtered_data['Month'] = pd.to_datetime(filtered_data['date'], errors='coerce').dt.to_period('M')

# --- Dashboard ---
st.header("📈 Dashboard Overview")

# Top 5 merchants
top_merchants = filtered_data.groupby('description')['amount'].sum().sort_values(ascending=False).head(5)
st.subheader("Top 5 Merchants")
st.dataframe(top_merchants)

# Top categories
top_categories = filtered_data.groupby('category')['amount'].sum().sort_values(ascending=False)
st.subheader("Top Categories")
fig_cat = px.pie(top_categories, values='amount', names=top_categories.index, title="Spending by Category")
st.plotly_chart(fig_cat, use_container_width=True)

# Monthly spending summary
monthly_summary = filtered_data.groupby('Month')['amount'].sum().reset_index()
monthly_summary['Month'] = monthly_summary['Month'].astype(str)
st.subheader("Monthly Spending Trend")
fig_month = px.line(monthly_summary, x='Month', y='amount', title="Monthly Spending Trend")
st.plotly_chart(fig_month, use_container_width=True)

# --- Merchant Search ---
st.header("🔍 Search Merchant")
search = st.text_input("Enter merchant name")
if search:
    merchant_data = data[data['description'].str.contains(search, case=False)]
    total_merchant = merchant_data['amount'].sum()
    avg_merchant = merchant_data.groupby(pd.to_datetime(merchant_data['date'], errors='coerce').dt.to_period('M'))['amount'].sum().mean()
    st.write(f"**Total Spending at {search}:** ${total_merchant:,.2f}")
    st.write(f"**Average Monthly Spending at {search}:** ${avg_merchant:,.2f}")
    st.dataframe(merchant_data)

    # Merchant trend chart
    if not merchant_data.empty:
        merchant_monthly = merchant_data.groupby(pd.to_datetime(merchant_data['date'], errors='coerce').dt.to_period('M'))['amount'].sum().reset_index()
        merchant_monthly['date'] = merchant_monthly['date'].astype(str)
        fig_merchant = px.line(merchant_monthly, x='date', y='amount', title=f"{search} Monthly Spending Trend")
        st.plotly_chart(fig_merchant, use_container_width=True)

    if st.button(f"Remove {search} from metrics"):
        remove_merchant(search)
        st.success(f"{search} removed from metrics")
        st.experimental_rerun()

# --- Removed Merchants ---
if removed_merchants:
    st.header("🛑 Removed Merchants")
    st.write(removed_merchants)
    if st.button("Re-add all removed merchants"):
        reinstate_merchants()
        st.success("All merchants reinstated")
        st.experimental_rerun()

# --- Export Filtered Data ---
if st.button("Export filtered transactions as CSV"):
    filtered_data.to_csv("filtered_transactions.csv", index=False)
    st.success("Filtered transactions exported!")
