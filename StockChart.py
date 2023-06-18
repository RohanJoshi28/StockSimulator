import altair as alt
import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import requests
import json
import numpy as np
from dotenv import load_dotenv
import streamlit_google_oauth as oauth
import os

exchange_df = pd.read_csv("stock_exchange.csv", index_col=0).to_dict('index')

load_dotenv()
client_id = os.environ["GOOGLE_CLIENT_ID"]
client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
redirect_uri = os.environ["GOOGLE_REDIRECT_URI"]

def scrape_google_data(ticker):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36"
    }

    html = requests.get(f"https://www.google.com/finance/quote/{ticker}:{exchange_df[stock_ticker]['Exchange']}", headers=headers, timeout=30)

    soup = BeautifulSoup(html.text, 'html.parser')

    max_length = float("-inf")
    max_script = None
    for script in soup.find_all("script"):
        if ("USD" in str(script) and ticker in str(script)):
            if len(str(script)) > max_length:
                max_script = str(script)
                max_length = len(str(script))

    data = json.loads(max_script[int(max_script.index("[")):int(max_script.rfind("]")+1)])[0][0][3][0][1:][0]
    return data

def get_stock_value(ticker):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36"
    }

    html = requests.get(f"https://www.google.com/finance/quote/{ticker}:{exchange_df[stock_ticker]['Exchange']}", headers=headers, timeout=30)

    soup = BeautifulSoup(html.text, 'html.parser')

    max_length = float("-inf")
    max_script = None
    for script in soup.find_all("script"):
        if ("USD" in str(script) and ticker in str(script)):
            if len(str(script)) > max_length:
                max_script = str(script)
                max_length = len(str(script))

    price = json.loads(max_script[int(max_script.index("[")):int(max_script.rfind("]")+1)])[0][0][3][0][1:][0][-1][1][0]
    return float(price)

def create_price_dataframe(data):
    # Convert your data to a DataFrame
    df = pd.DataFrame({
        'datetime': [pd.Timestamp(year=d[0][0], month=d[0][1], day=d[0][2], hour=d[0][3], minute=d[0][4]) for d in data],
        'price': [d[1][0] for d in data],
    })

    df['datetime'] = pd.to_datetime(df['datetime'])
    df['datetime'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
    return df

def calculate_total_assets(email):
    total_assets = None
    user_file = open(f"./user_assets/{email}", "r")
    user_file_json = json.loads(user_file.read())
    total_assets = user_file_json["total_cash"]
    stock_dictionary = user_file_json["stocks"]
    for key in stock_dictionary.keys():
        total_assets += float(stock_dictionary[key]) * get_stock_value(key)
    if total_assets is not None:
        st.session_state["total_assets"] = str(total_assets)
    return total_assets

def buy_stock(user_email, stock_ticker):
    user_file = open(f"./user_assets/{user_email}", "r")
    user_file_json = json.loads(user_file.read())
    total_cash = user_file_json["total_cash"]
    stock_value = get_stock_value(stock_ticker)
    if stock_value > total_cash:
        st.session_state["not_enough_cash"] = True
    else:
        st.session_state["not_enough_cash"] = False
        total_cash -= stock_value
        user_file_json["total_cash"] = total_cash
        if stock_ticker in user_file_json["stocks"]:
            user_file_json["stocks"][stock_ticker] += 1
        else:
            user_file_json["stocks"][stock_ticker] = 1
        user_file.close()
        user_file = open(f"./user_assets/{user_email}", "w+")
        user_file.write(json.dumps(user_file_json))
        user_file.close()

def sell_stock(user_email, stock_ticker):
    user_file = open(f"./user_assets/{user_email}", "r")
    user_file_json = json.loads(user_file.read())
    total_cash = user_file_json["total_cash"]
    stock_value = get_stock_value(stock_ticker)
    if stock_ticker in user_file_json["stocks"] and user_file_json["stocks"][stock_ticker] > 0:
        st.session_state["not_enough_stock"] = False
        total_cash += stock_value
        user_file_json["total_cash"] = total_cash
        user_file_json["stocks"][stock_ticker] -= 1
        user_file.close()
        user_file = open(f"./user_assets/{user_email}", "w+")
        user_file.write(json.dumps(user_file_json))
    else:
        st.session_state["not_enough_stock"] = True


login_info = oauth.login(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    logout_button_text="Logout",
)
if login_info:
    user_id, user_email = login_info
    try:
        user_file = open(f"./user_assets/{user_email}", "r")
    except:
        user_file = open(f"./user_assets/{user_email}", "w+")
        user_info = {}
        user_info["total_cash"] = 100000
        user_info["stocks"] = {}
        user_file.write(json.dumps(user_info))
        user_file.close()
        user_file = open(f"./user_assets/{user_email}", "r")

    user_file_parsed = json.loads(user_file.read())
    st.write(f"Welcome {user_email}. Total cash: {user_file_parsed['total_cash']}.")
    st.title("Buy and sell stock on demand")
    stock_ticker = st.text_input('Enter your stock ticker', '')

    if stock_ticker!="":
        if stock_ticker not in exchange_df:
            st.warning("Stock ticker does not exist in NYSE or NASDAQ")
        else:
            df = create_price_dataframe(scrape_google_data(stock_ticker))

            # Define the lower and upper y bounds
            ymin = np.floor(df['price'].min())
            ymax = np.ceil(df['price'].max())

            # Create the chart
            chart = alt.Chart(df).mark_line().encode(
                x='datetime:T',
                y=alt.Y('price:Q', scale=alt.Scale(domain=(ymin, ymax))),
                tooltip=['datetime:T', 'price:Q']
            ).interactive()

            #streamlit title
            st.title(stock_ticker)

            # Display the chart in Streamlit
            st.altair_chart(chart, use_container_width=True)

            col1, col2, col3, col4 = st.columns(4)
            with col2:
                pass
            with col1:
                st.button(f"Buy {stock_ticker}", type="primary", on_click=buy_stock, args=(user_email, stock_ticker,))
            
            if stock_ticker in user_file_parsed["stocks"].keys():
                with col4:
                    st.button(f"Sell {stock_ticker}", type="primary", on_click=sell_stock, args=(user_email, stock_ticker))
            with col3:
                pass

            if "not_enough_cash" in st.session_state and st.session_state["not_enough_cash"] == True:
                st.warning("You do not have enough cash to buy this stock.")

            if "not_enough_stock" in st.session_state and st.session_state["not_enough_stock"] == True:
                st.warning("You don't have any stock, so you cannot sell")

    st.button("Calculate total assets", on_click=calculate_total_assets, args=(user_email,))

    if "total_assets" in st.session_state:
        st.write(f"Total assets: {st.session_state['total_assets']}")
