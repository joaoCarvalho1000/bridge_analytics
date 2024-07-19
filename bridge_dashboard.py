import streamlit as st
import pandas as pd
import requests
import plotly.express as px

WALLET_ADDRESS = "DAG4pUWtEvkf98AcpwFHSfdCYxT6pikKjwHvBHK8"
BRIDGE_FEES_ADDRESS = "DAG0UKDmEqkMfXcWUpWc2S4LwbuFa7vfv3ZKFqJ2"

# Fetch the data from the API with pagination
def fetch_data():
    url = f"https://be-mainnet.constellationnetwork.io/addresses/{WALLET_ADDRESS}/transactions?limit=50"
    all_data = []
    while True:
        response = requests.get(url)
        if response.status_code != 200:
            st.error(f"Failed to fetch data: {response.status_code}")
            break
        data = response.json()
        if 'data' not in data:
            st.error("Unexpected response format: 'data' key not found.")
            break
        transactions = data['data']
        all_data.extend(transactions)
        if 'meta' not in data or 'next' not in data['meta']:
            break
        next_page_token = data['meta']['next']
        url = f"https://be-mainnet.constellationnetwork.io/addresses/{WALLET_ADDRESS}/transactions?limit=50&next={next_page_token}"
    return all_data

# Fetch DAG price in USD
def fetch_dag_price():
    url = "https://d2a4s9vrrsa9d4.cloudfront.net/coin-prices?ids=constellation-labs&vs_currencies=usd&include_market_cap=false&include_24hr_vol=false&include_24hr_change=false&include_last_updated_at=false&token=dagExplorer"
    response = requests.get(url)
    data = response.json()
    return data['data']['constellation-labs']['usd']

# Fetch the balance of the bridge fees address
def fetch_bridge_fees_balance():
    url = f"https://be-mainnet.constellationnetwork.io/addresses/{BRIDGE_FEES_ADDRESS}/balance"
    response = requests.get(url)
    data = response.json()
    balance = data['data']['balance'] / 1e8  # Convert to DAG
    return balance

# Process the data to create a DataFrame
def process_data(transactions):
    df = pd.DataFrame(transactions)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce').dt.tz_convert('UTC')
    df['dag'] = df['amount'] / 1e8  # Assuming amount is in the smallest unit, convert to DAG
    df['dag'] = df['dag'].astype(int)  # Remove decimals
    df['direction'] = df.apply(lambda x: 'ethereum' if x['destination'] == WALLET_ADDRESS else 'dag', axis=1)
    df['counterparty'] = df.apply(lambda x: x['source'] if x['direction'] == 'ethereum' else x['destination'], axis=1)
    # Filter out transactions related to the bridge fees address
    df = df[(df['source'] != BRIDGE_FEES_ADDRESS) & (df['destination'] != BRIDGE_FEES_ADDRESS)]
    return df

# Fetch and process data
st.title("Bridge Activity Dashboard")

transactions = fetch_data()
df = process_data(transactions)
dag_price_usd = fetch_dag_price()
bridge_fees_balance = fetch_bridge_fees_balance()
bridge_fees_balance = int(bridge_fees_balance)  # Remove decimals

# Add USD amount
df['USD'] = (df['dag'] * dag_price_usd).astype(int)

# Display the raw data
if st.checkbox("Show raw data"):
    st.write(df)

# Calculate metrics
total_ethereum = df[df['direction'] == 'ethereum']['dag'].sum()
total_dag = df[df['direction'] == 'dag']['dag'].sum()
net_flow = total_dag - total_ethereum

total_ethereum_usd = df[df['direction'] == 'ethereum']['USD'].sum()
total_dag_usd = df[df['direction'] == 'dag']['USD'].sum()
net_flow_usd = total_dag_usd - total_ethereum_usd

# Creative Key Metrics Representation
st.header("Key Metrics")

html_content = f"""
<style>
  .metrics-container {{
    display: flex;
    align-items: center;
    justify-content: space-around;
    padding: 20px;
  }}
  .metric {{
    text-align: center;
    padding: 10px;
    border: 2px solid #ccc;
    border-radius: 10px;
  }}
  .metric h2 {{
    font-size: x-large;
  }}
  .metric p {{
    margin: 0;
    font-size: 18px;
  }}
  .colorGreen {{
    color: green;
  }}
</style>
<div class="metrics-container">
  <div class="metric">
    <p>DAG to Ethereum</p>
    <h2>{total_ethereum:,} DAG</h2>
    <p class="colorGreen" >${total_ethereum_usd:,}</p>
  </div>
  <div class="metric">
    <p>Ethereum to DAG</p>
    <h2>{total_dag:,} DAG</h2>
    <p class="colorGreen" >${total_dag_usd:,}</p>
  </div>
  <div class="metric">
    <p>Bridge Fees Balance</p>
    <h2>{bridge_fees_balance:,} DAG</h2>
    <p class="colorGreen" >${int(bridge_fees_balance * dag_price_usd):,}</p>
  </div>
</div>
"""

st.markdown(html_content, unsafe_allow_html=True)

# Top addresses involved in transactions
top_sources_dag = df[df['direction'] == 'ethereum'].groupby('counterparty')[['dag', 'USD']].sum().sort_values(by='dag', ascending=False).head(10)
top_destinations_dag = df[df['direction'] == 'dag'].groupby('counterparty')[['dag', 'USD']].sum().sort_values(by='dag', ascending=False).head(10)

st.header("Top 10 Addresses for DAG -> Ethereum")
st.write(top_sources_dag)

st.header("Top 10 Addresses for Ethereum -> DAG")
st.write(top_destinations_dag)

# Calculate daily volume
df['date'] = df['timestamp'].dt.date
daily_volume_dag = df.groupby(['date', 'direction'])['dag'].sum().reset_index()
daily_volume_usd = df.groupby(['date', 'direction'])['USD'].sum().reset_index()

# Plot daily volume in DAG
fig_dag = px.bar(daily_volume_dag, x='date', y='dag', color='direction', barmode='group', title='Daily Volume in DAG', labels={'dag': 'Volume (DAG)'})
st.plotly_chart(fig_dag)

# Plot daily volume in USD
fig_usd = px.bar(daily_volume_usd, x='date', y='USD', color='direction', barmode='group', title='Daily Volume in USD', labels={'USD': 'Volume (USD)'})
st.plotly_chart(fig_usd)

# Display recent transactions
recent_transactions = df[['timestamp', 'hash', 'dag', 'USD', 'direction', 'counterparty']].sort_values(by='timestamp', ascending=False)
st.header("Recent Transactions")
st.write(recent_transactions)
