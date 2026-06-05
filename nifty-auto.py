# =========================================================
# REAL AUTO TRADING NIFTY OPTIONS BOT
# ZERODHA KITE API
# LIVE AUTO BUY + AUTO SELL
# GOOGLE COLAB READY
# =========================================================

# WARNING:
# THIS IS REAL AUTO TRADING
# REAL MONEY WILL BE USED
# TEST WITH 1 LOT ONLY

# =========================================================
# INSTALL LIBRARIES
# =========================================================

!pip install kiteconnect pandas ta pytz -q

# =========================================================
# IMPORTS
# =========================================================

from kiteconnect import KiteConnect
import pandas as pd

from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator

from datetime import datetime, timedelta

import pytz
import os
import time

# =========================================================
# INDIA TIMEZONE
# =========================================================

os.environ['TZ'] = 'Asia/Kolkata'

india = pytz.timezone('Asia/Kolkata')

def get_indian_time():

    return datetime.now(india)

# =========================================================
# API DETAILS
# =========================================================

API_KEY = "o6z9vadhlia8llh1"

API_SECRET = "q7ierqpe1lv6b2lgmic58230iax2g22g"

# =========================================================
# LOGIN
# =========================================================

kite = KiteConnect(api_key=API_KEY)

print("\nLOGIN URL:")
print(kite.login_url())

request_token = input(
    "\nENTER REQUEST TOKEN: "
).strip()

data = kite.generate_session(
    request_token=request_token,
    api_secret=API_SECRET
)

kite.set_access_token(
    data["access_token"]
)

print("\n✅ LOGIN SUCCESSFUL")

# =========================================================
# SETTINGS
# =========================================================

INTERVAL = "3minute"

REFRESH_TIME = 5

LOT_SIZE = 65

TARGET_POINTS = 8

STOPLOSS_POINTS = 4

TRAIL_TRIGGER = 4

MAX_TRADES_PER_DAY = 10

MAX_DAILY_LOSS = -3000

# =========================================================
# VARIABLES
# =========================================================

position = None

trade_side = None

entry_price = 0

target_price = 0

stoploss_price = 0

trade_count = 0

wins = 0

losses = 0

total_pnl = 0

current_option_symbol = None

instrument_token = 256265

# =========================================================
# FETCH NIFTY DATA
# =========================================================

def get_data():

    to_date = get_indian_time()

    from_date = (
        to_date - timedelta(days=3)
    )

    data = kite.historical_data(

        instrument_token=instrument_token,

        from_date=from_date,

        to_date=to_date,

        interval=INTERVAL
    )

    df = pd.DataFrame(data)

    return df

# =========================================================
# APPLY INDICATORS
# =========================================================

def apply_indicators(df):

    ema9 = EMAIndicator(
        close=df['close'],
        window=9
    )

    ema21 = EMAIndicator(
        close=df['close'],
        window=21
    )

    df['EMA9'] = ema9.ema_indicator()

    df['EMA21'] = ema21.ema_indicator()

    macd = MACD(close=df['close'])

    df['MACD'] = macd.macd()

    df['SIGNAL'] = macd.macd_signal()

    rsi = RSIIndicator(close=df['close'])

    df['RSI'] = rsi.rsi()

    return df

# =========================================================
# SIGNAL
# =========================================================

def generate_signal(df):

    latest = df.iloc[-1]

    bullish = (

        latest['EMA9']
        > latest['EMA21']

        and (
            latest['MACD']
            - latest['SIGNAL']
        ) > -0.5

        and latest['RSI'] > 48
    )

    bearish = (

        latest['EMA9']
        < latest['EMA21']

        and (
            latest['MACD']
            - latest['SIGNAL']
        ) < 0.5

        and latest['RSI'] < 52
    )

    if bullish:

        return "CALL"

    elif bearish:

        return "PUT"

    else:

        return "HOLD"

# =========================================================
# GET ATM OPTION
# =========================================================

def get_option_symbol(signal):

    ltp = kite.ltp("NSE:NIFTY 50")

    nifty_price = ltp[
        "NSE:NIFTY 50"
    ]['last_price']

    strike = round(
        nifty_price / 50
    ) * 50

    instruments = kite.instruments("NFO")

    expiry = None

    for item in instruments:

        if (
            item['name'] == 'NIFTY'
            and item['segment'] == 'NFO-OPT'
        ):

            expiry = item['expiry']

            break

    option_type = "CE"

    if signal == "PUT":

        option_type = "PE"

    option_symbol = None

    for item in instruments:

        if (
            item['name'] == 'NIFTY'
            and item['segment'] == 'NFO-OPT'
            and item['strike'] == strike
            and item['instrument_type'] == option_type
            and item['expiry'] == expiry
        ):

            option_symbol = item['tradingsymbol']

            break

    return option_symbol

# =========================================================
# PLACE BUY ORDER
# =========================================================

def place_buy_order(symbol):

    order_id = kite.place_order(

        variety=kite.VARIETY_REGULAR,

        exchange=kite.EXCHANGE_NFO,

        tradingsymbol=symbol,

        transaction_type=kite.TRANSACTION_TYPE_BUY,

        quantity=LOT_SIZE,

        order_type=kite.ORDER_TYPE_MARKET,

        product=kite.PRODUCT_MIS
    )

    return order_id

# =========================================================
# PLACE SELL ORDER
# =========================================================

def place_sell_order(symbol):

    order_id = kite.place_order(

        variety=kite.VARIETY_REGULAR,

        exchange=kite.EXCHANGE_NFO,

        tradingsymbol=symbol,

        transaction_type=kite.TRANSACTION_TYPE_SELL,

        quantity=LOT_SIZE,

        order_type=kite.ORDER_TYPE_MARKET,

        product=kite.PRODUCT_MIS
    )

    return order_id

# =========================================================
# START BOT
# =========================================================

print("\n======================================")
print(" REAL AUTO TRADING BOT STARTED ")
print("======================================")

while True:

    try:

        if total_pnl <= MAX_DAILY_LOSS:

            print("\n❌ MAX DAILY LOSS HIT")

            break

        if trade_count >= MAX_TRADES_PER_DAY:

            print("\n✅ MAX TRADES REACHED")

            break

        # LIVE NIFTY PRICE
        ltp_data = kite.ltp(
            "NSE:NIFTY 50"
        )

        current_price = ltp_data[
            "NSE:NIFTY 50"
        ]['last_price']

        # FETCH DATA
        df = get_data()

        df = apply_indicators(df)

        latest = df.iloc[-1]

        signal = generate_signal(df)

        print("\n======================================")

        print("TIME:",
              get_indian_time())

        print("NIFTY:",
              current_price)

        print("EMA9:",
              round(latest['EMA9'], 2))

        print("EMA21:",
              round(latest['EMA21'], 2))

        print("MACD:",
              round(latest['MACD'], 2))

        print("SIGNAL:",
              round(latest['SIGNAL'], 2))

        print("RSI:",
              round(latest['RSI'], 2))

        print("BOT SIGNAL:",
              signal)

        # =================================================
        # ENTRY
        # =================================================

        if position is None:

            if signal in ["CALL", "PUT"]:

                option_symbol = get_option_symbol(signal)

                if option_symbol:

                    current_option_symbol = option_symbol

                    order_id = place_buy_order(
                        option_symbol
                    )

                    option_ltp = kite.ltp(
                        f"NFO:{option_symbol}"
                    )

                    entry_price = option_ltp[
                        f"NFO:{option_symbol}"
                    ]['last_price']

                    position = "OPEN"

                    trade_side = signal

                    target_price = (
                        entry_price
                        + TARGET_POINTS
                    )

                    stoploss_price = (
                        entry_price
                        - STOPLOSS_POINTS
                    )

                    trade_count += 1

                    print("\n🟢 BUY ORDER EXECUTED")

                    print("OPTION:",
                          option_symbol)

                    print("ENTRY:",
                          entry_price)

                    print("TARGET:",
                          target_price)

                    print("STOPLOSS:",
                          stoploss_price)

        # =================================================
        # POSITION MANAGEMENT
        # =================================================

        else:

            option_ltp = kite.ltp(
                f"NFO:{current_option_symbol}"
            )

            live_option_price = option_ltp[
                f"NFO:{current_option_symbol}"
            ]['last_price']

            pnl_points = (
                live_option_price
                - entry_price
            )

            pnl = pnl_points * LOT_SIZE

            print("\nLIVE OPTION PRICE:",
                  live_option_price)

            print("LIVE PnL:",
                  round(pnl, 2))

            # TRAILING SL
            if pnl_points >= TRAIL_TRIGGER:

                stoploss_price = entry_price

            if pnl_points >= 6:

                stoploss_price = (
                    entry_price + 3
                )

            print("TRAIL SL:",
                  round(stoploss_price, 2))

            # TARGET
            if live_option_price >= target_price:

                order_id = place_sell_order(
                    current_option_symbol
                )

                wins += 1

                total_pnl += pnl

                print("\n✅ TARGET HIT")

                print("SELL ORDER:",
                      order_id)

                print("BOOKED PnL:",
                      round(pnl, 2))

                position = None

            # STOPLOSS
            elif live_option_price <= stoploss_price:

                order_id = place_sell_order(
                    current_option_symbol
                )

                losses += 1

                total_pnl += pnl

                print("\n❌ STOPLOSS HIT")

                print("SELL ORDER:",
                      order_id)

                print("BOOKED PnL:",
                      round(pnl, 2))

                position = None

        # =================================================
        # SUMMARY
        # =================================================

        print("\n======================================")

        print("TOTAL TRADES:",
              trade_count)

        print("WINS:",
              wins)

        print("LOSSES:",
              losses)

        if trade_count > 0:

            win_rate = (
                wins / trade_count
            ) * 100

            print("WIN RATE:",
                  round(win_rate, 2),
                  "%")

        print("TOTAL PnL:",
              round(total_pnl, 2))

        print("======================================")

        time.sleep(REFRESH_TIME)

    except Exception as e:

        print("\nERROR:", e)

        time.sleep(10)