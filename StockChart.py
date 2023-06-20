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
import pyrebase
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

exchange_df = pd.read_csv("stock_exchange.csv", index_col=0).to_dict('index')

load_dotenv()
api_key = os.environ["FIREBASE_API_KEY"]
auth_domain = os.environ["FIREBASE_AUTH_DOMAIN"]
database_url = os.environ["FIREBASE_DATABASE_URL"]
storage_bucket = os.environ["FIREBASE_STORAGE_BUCKET"]

firebase_config = {
  "apiKey": api_key,
  "authDomain": auth_domain,
  "databaseURL": database_url,
  "storageBucket": storage_bucket
}
firebase = pyrebase.initialize_app(firebase_config)
storage = firebase.storage()

storage.child(f"/fake_stocks/stock_dir.txt").download(path='gs://stock-storage-54197.appspot.com/', filename=f"fake_stocks/stock_dir.txt")
fake_stocks = open("fake_stocks/stock_dir.txt", "r").read().split("\n")

storage.child(f"config.yaml").download(path="gs://stock-storage-54197.appspot.com/", filename=f"config.yaml")
with open('./config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

total_assets = {}

def scrape_google_data(ticker, interval):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36"
    }

    if interval == "one month":
        html = requests.get(f"https://www.google.com/finance/quote/{ticker}:{exchange_df[ticker]['Exchange']}?window=1M", headers=headers, timeout=30)
    else:
        html = requests.get(f"https://www.google.com/finance/quote/{ticker}:{exchange_df[ticker]['Exchange']}", headers=headers, timeout=30)

    soup = BeautifulSoup(html.text, 'html.parser')

    valid_scripts = []
    for script in soup.find_all("script"):
        str_script = str(script)
        if ("USD" in str_script and ((f'[[[["{ticker}","{exchange_df[ticker]["Exchange"]}"]' in str_script) or (f"[[[['{ticker}','{exchange_df[ticker]['Exchange']}']" in str(script)) or (f"[[[['{ticker}', '{exchange_df[ticker]['Exchange']}']" in str_script) or (f'[[[["{ticker}", "{exchange_df[ticker]["Exchange"]}"]' in str_script))):
            valid_scripts.append(str_script)
    valid_scripts.sort(key=len)
    if interval == "one month":
        #months is the script tag with the second longest length
        max_script = valid_scripts[-2]
    elif interval == "one day":
        max_script = valid_scripts[-1]
    data = json.loads(max_script[int(max_script.index("[")):int(max_script.rfind("]")+1)])[0][0][3][0][1:][0]
    return data

def get_stock_value(ticker):
    if ticker in fake_stocks:
        return get_fake_stock_prices(ticker)[-1]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36"
    }

    html = requests.get(f"https://www.google.com/finance/quote/{ticker}:{exchange_df[ticker]['Exchange']}", headers=headers, timeout=30)

    soup = BeautifulSoup(html.text, 'html.parser')

    max_length = float("-inf")
    max_script = None
    for script in soup.find_all("script"):
        if ("USD" in str(script) and ((f'[[[["{ticker}","{exchange_df[ticker]["Exchange"]}"]' in str(script)) or (f"[[[['{ticker}','{exchange_df[ticker]['Exchange']}']" in str(script)) or (f"[[[['{ticker}', '{exchange_df[ticker]['Exchange']}']" in str(script)) or (f'[[[["{ticker}", "{exchange_df[ticker]["Exchange"]}"]' in str(script)))):
            if len(str(script)) > max_length:
                max_script = str(script)
                max_length = len(str(script))

    price = json.loads(max_script[int(max_script.index("[")):int(max_script.rfind("]")+1)])[0][0][3][0][1:][0][-1][1][0]
    return float(price)

def get_fake_stock_prices(ticker):
    storage.child(f"/fake_stocks/{ticker}.txt").download(path='gs://stock-storage-54197.appspot.com/', filename=f"./fake_stocks/{ticker}.txt")
    stock_prices = [float(i) for i in open(f"./fake_stocks/{ticker}.txt", "r").read().split(" ")[-100:]]
    return stock_prices

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
    df['datetime'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
    return df

def calculate_total_assets(email):
    total_assets = None
    storage.child(f"user_assets/{email}").download(path="gs://stock-storage-54197.appspot.com/user_assets", filename=f"./user_assets/{email}")
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
    storage.child(f"user_assets/{user_email}").download(path="gs://stock-storage-54197.appspot.com/user_assets", filename=f"./user_assets/{user_email}")
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
        storage.child(f"user_assets/{user_email}").put(f"./user_assets/{user_email}")

def sell_stock(user_email, stock_ticker, num_sell_shares):
    num_sell_shares = int(num_sell_shares)
    storage.child(f"user_assets/{user_email}").download(path="gs://stock-storage-54197.appspot.com/user_assets", filename=f"./user_assets/{user_email}")
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
        user_file.close()
        storage.child(f"user_assets/{user_email}").put(f"./user_assets/{user_email}")
    else:
        st.session_state["not_enough_stock"] = True


def get_total_assets(email):


    for email in os.listdir("./user_assets"):
        total_assets[email] = calculate_total_assets(email)
       
    return total_assets.get(email, 0)


def load_data(rank, email, total_assets):

    return pd.DataFrame(
        {
            "Rank 🏅": rank,
            "Email 📧": email,
            "Total Assets 💵": total_assets,
        }
    )


placeholder = st.empty()
if ("authentication_status" not in st.session_state) or (st.session_state["authentication_status"] is None):
    login_type = placeholder.selectbox('Login or Register', ('Login', 'Register'))
    st.session_state["login_type"] = login_type

if "login_type" not in st.session_state:
    st.session_state["login_type"] = "Login"
    
if st.session_state["login_type"] == "Register":
    authentication_status = None
    if authenticator.register_user('Register user', preauthorization=False):
        st.success('User registered successfully')
        with open('./config.yaml', 'w') as file:
            yaml.dump(config, file, default_flow_style=False)
        storage.child(f"config.yaml").put(f"./config.yaml")

else:
    name, authentication_status, username = authenticator.login('Login', 'main') 
    st.session_state["authentication_status"] = authentication_status

if authentication_status:
    placeholder.empty()
    user_id, user_email = name, username
    authenticator.logout('Logout', 'main', key='unique_key')
    try:
        storage.child(f"user_assets/{user_email}").download(path="gs://stock-storage-54197.appspot.com/user_assets", filename=f"./user_assets/{user_email}")
        user_file = open(f"./user_assets/{user_email}", "r")
    except:
        user_file = open(f"./user_assets/{user_email}", "w+")
        user_info = {}
        user_info["total_cash"] = 100000
        user_info["stocks"] = {}
        user_file.write(json.dumps(user_info))
        user_file.close()
        storage.child(f"user_assets/{user_email}").put(f"./user_assets/{user_email}")
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
        st.write(f"Welcome {user_id}. Total cash: {user_file_parsed['total_cash']}.")
        st.subheader("Buy and sell stock on demand")
        stock_ticker = st.text_input('Enter your stock ticker', '')

        if stock_ticker!="":
            if stock_ticker in fake_stocks:
                fake_stock = True
            else:
                fake_stock = False

            if (stock_ticker not in exchange_df) and (stock_ticker not in fake_stocks):
                st.warning("Stock ticker does not exist in NYSE or NASDAQ")
            else:
                if fake_stock == False:
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
                else:
                    stock_prices = get_fake_stock_prices(stock_ticker)
                    df = pd.DataFrame({'price': stock_prices, 'time': range(1, len(stock_prices)+1)})
                    ymin = np.floor(df['price'].min())
                    ymax = np.ceil(df['price'].max())
                    chart = alt.Chart(df).mark_line().encode(
                        x='time',
                        y=alt.Y('price', scale=alt.Scale(domain=(ymin, ymax))),
                        tooltip=['time', 'price']
                    ).interactive()
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

        storage.child(f"config.yaml").download(path="gs://stock-storage-54197.appspot.com/", filename=f"config.yaml")
        with open('./config.yaml') as file:
            config = yaml.load(file, Loader=SafeLoader)
        
        usernames = list(config["credentials"]["usernames"].keys())
        user_assets = []
        for username in usernames:
            try:    
                storage.child(f"user_assets/{username}").download(path="gs://stock-storage-54197.appspot.com/user_assets", filename=f"./user_assets/{username}")
                assets = calculate_total_assets(f"./user_assets/{username}")
                user_assets.append([username, assets])
            except Exception as e:
                user_assets.append([username, 100000])

        sorted_user_assets = sorted(user_assets, key=lambda user_asset: user_asset[1])

        ranked_usernames = []
        ranked_assets = []
        for user_asset in sorted_user_assets:
            ranked_usernames.append(user_asset[0])
            ranked_assets.append(user_asset[1])

        rank = list(range(1, len(sorted_user_assets) + 1))
        st.subheader(f"Leaderboard 🎉")
        df = load_data(rank, ranked_usernames, ranked_assets)
        st.dataframe(
            df, 
            use_container_width=True,
            hide_index=True
        )
        
elif authentication_status == False:
    st.error("Username/password is incorrect")


    
