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
import yfinance as yahooFinance
from streamlit_option_menu import option_menu
exchange_df = pd.read_csv("stock_exchange.csv", index_col=0).to_dict('index')

load_dotenv()
client_id = os.environ["GOOGLE_CLIENT_ID"]
client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
redirect_uri = os.environ["GOOGLE_REDIRECT_URI"]

def scrape_google_data(ticker, interval):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36"
    }

    html = requests.get(f"https://www.google.com/finance/quote/{ticker}:{exchange_df[stock_ticker]['Exchange']}", headers=headers, timeout=30)

    soup = BeautifulSoup(html.text, 'html.parser')

    max_length = float("-inf")
    max_script = None
    replaced_max_script = None
    for script in soup.find_all("script"):
        if ("USD" in str(script) and ticker in str(script)):
            if len(str(script)) > max_length:
                replaced_max_script = max_script
                max_script = str(script)
                max_length = len(str(script))

    if interval == "one month":
        #months is the script tag with the second longest length
        max_script = replaced_max_script

    data = json.loads(max_script[int(max_script.index("[")):int(max_script.rfind("]")+1)])[0][0][3][0][1:][0]
    return data

def get_stock_value(ticker):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36"
    }

    html = requests.get(f"https://www.google.com/finance/quote/{ticker}:{exchange_df[ticker]['Exchange']}", headers=headers, timeout=30)

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

def create_price_dataframe(data, interval):
    if interval == "one day":
    # Convert your data to a DataFrame
        df = pd.DataFrame({
            'datetime': [pd.Timestamp(year=d[0][0], month=d[0][1], day=d[0][2], hour=d[0][3], minute=d[0][4]) for d in data],
            'price': [d[1][0] for d in data],
        })
    elif interval == "one month":
        df = pd.DataFrame({
            'datetime': [pd.Timestamp(year=d[0][0], month=d[0][1], day=d[0][2]) for d in data],
            'price': [d[1][0] for d in data],
        })
        
    df['datetime'] = pd.to_datetime(df['datetime'])
    #df['datetime'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
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

def buy_stock(user_email, stock_ticker, num_buy_shares):
    num_buy_shares = int(num_buy_shares)
    user_file = open(f"./user_assets/{user_email}", "r")
    user_file_json = json.loads(user_file.read())
    total_cash = user_file_json["total_cash"]
    stock_value = get_stock_value(stock_ticker) * num_buy_shares
    if stock_value >= total_cash:
        st.session_state["not_enough_cash"] = True
    else:
        st.session_state["not_enough_cash"] = False
        total_cash -= stock_value
        user_file_json["total_cash"] = total_cash
        if stock_ticker in user_file_json["stocks"]:
            user_file_json["stocks"][stock_ticker] += num_buy_shares
        else:
            user_file_json["stocks"][stock_ticker] = num_buy_shares
        user_file.close()
        user_file = open(f"./user_assets/{user_email}", "w+")
        user_file.write(json.dumps(user_file_json))
        user_file.close()

def sell_stock(user_email, stock_ticker, num_sell_shares):
    num_sell_shares = int(num_sell_shares)
    user_file = open(f"./user_assets/{user_email}", "r")
    user_file_json = json.loads(user_file.read())
    total_cash = user_file_json["total_cash"]
    stock_value = get_stock_value(stock_ticker) * num_sell_shares
    if stock_ticker in user_file_json["stocks"] and user_file_json["stocks"][stock_ticker] >= num_sell_shares:
        st.session_state["not_enough_stock"] = False
        total_cash += stock_value
        user_file_json["total_cash"] = total_cash
        user_file_json["stocks"][stock_ticker] -= num_sell_shares
        user_file.close()
        user_file = open(f"./user_assets/{user_email}", "w+")
        user_file.write(json.dumps(user_file_json))
    else:
        st.session_state["not_enough_stock"] = True


def get_total_assets(email):
    total_assets = {}
    
    for email in os.listdir("./user_assets"):
        total_assets[email] = calculate_total_assets(email)
    return total_assets.get(email, 0)


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
    
    selected = option_menu(
        menu_title="InvestSimulator",
        options=["Home", "Leaderboard"],
        icons=["house", "clipboard-data-fill"],
        menu_icon="currency-exchange",
        default_index=0,
        orientation="horizontal",
    )
    
    if selected == "Home":
        st.write(f"Welcome {user_email}. Total cash: {user_file_parsed['total_cash']}.")
        st.subheader("Buy and sell stock on demand")
        stock_ticker = st.text_input('Enter your stock ticker', '')

        if stock_ticker!="":
            if stock_ticker not in exchange_df:
                st.warning("Stock ticker does not exist in NYSE or NASDAQ")
            else:
                with st.sidebar:
                    st.subheader("Stock Statistics")
                    st.markdown(f'''
                    <style>
                        section[data-testid="stSidebar"] .css-ng1t4o {{width: 14rem;}}
                        section[data-testid="stSidebar"] .css-1d391kg {{width: 14rem;}}
                    </style>
                    ''',unsafe_allow_html=True)
                    ticker_data = yahooFinance.Ticker(stock_ticker).info
                    st.text(f"Market Cap: {ticker_data['marketCap']}")
                    st.divider()
                    st.text(f"PE ratio: (TTM): {round(float(ticker_data['trailingPE']), 2)}")
                    st.divider()
                    st.text(f"Beta (5Y Monthly): {round(float(ticker_data['beta']), 2)}")
                    st.divider()
                    st.text(f"Open: {round(float(ticker_data['open']), 2)}")
                    st.divider()
                    st.text(f"Previous Close: {round(float(ticker_data['previousClose']), 2)}")
                    st.divider()
                    st.text(f"Volume: {ticker_data['volume']}")
                    st.divider()
                    st.text(f"Average Volume: {ticker_data['averageVolume']}")

                interval = st.selectbox('Pick time interval',
                ('one day', 'one month'))
                df = create_price_dataframe(scrape_google_data(stock_ticker, interval), interval)

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
                st.subheader(stock_ticker)

                # Display the chart in Streamlit
                st.altair_chart(chart, use_container_width=True)

                col1, col2, col3, col4, col5 = st.columns(5)
                with col2:
                    num_buy_shares = st.text_input('Shares', "1", key="buy_shares")
                    buy_disable = not num_buy_shares.isdigit()

                with col1:
                    st.button(f"Buy {stock_ticker}", type="primary", on_click=buy_stock, args=(user_email, stock_ticker,num_buy_shares,), disabled=buy_disable)
                if buy_disable:
                    st.warning("Please enter a valid share number for buying")

                with col5:
                    num_sell_shares = st.text_input('Shares', "1", key="sell_shares")
                    sell_disable = not num_sell_shares.isdigit()
                
                if stock_ticker in user_file_parsed["stocks"].keys():
                    with col4:
                        st.button(f"Sell {stock_ticker}", type="primary", on_click=sell_stock, args=(user_email, stock_ticker, num_sell_shares,), disabled=sell_disable)
                if sell_disable:
                    st.warning("Please enter a valid share number for selling")
                    


                if "not_enough_cash" in st.session_state and st.session_state["not_enough_cash"] == True:
                    st.warning("You do not have enough cash to buy this stock.")

                if "not_enough_stock" in st.session_state and st.session_state["not_enough_stock"] == True:
                    st.warning("You don't have any stock, so you cannot sell")

        st.text("")
        st.text("")
        st.button("Calculate total assets", on_click=calculate_total_assets, args=(user_email,))

        if "total_assets" in st.session_state:
            st.write(f"Total assets: {st.session_state['total_assets']}")
            
    if selected == "Leaderboard":
    
        st.title(f"Leaderboard")
        emails = []
     
        for email in os.listdir("./user_assets"):
            print(calculate_total_assets(email))
        #     # emails.append(email)
            
        # # sorted_emails = sorted(emails, key=get_total_assets)
        # # print(sorted_emails)
        
        
        st.subheader(f"Leaderboard 🎉")
    
