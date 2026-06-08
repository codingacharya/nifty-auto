# =========================================================
# PART 1: STREAMLIT APP CONFIGURATION & AUTHENTICATION
# =========================================================
import streamlit as st
import pandas as pd
from kiteconnect import KiteConnect
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta
import pytz
import os
import time

# --- Page configuration ---
st.set_page_config(
    page_title="Nifty Options Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- India Timezone Setup ---
os.environ['TZ'] = 'Asia/Kolkata'
india = pytz.timezone('Asia/Kolkata')

def get_indian_time():
    return datetime.now(india)

# --- Initialize Session State ---
if "kite" not in st.session_state:
    st.session_state.kite = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "bot_running" not in st.session_state:
    st.session_state.bot_running = False
if "logs" not in st.session_state:
    st.session_state.logs = []

# Persistent variables for trading state
trading_metrics = [
    "position", "trade_side", "entry_price", "target_price",
    "stoploss_price", "trade_count", "wins", "losses", 
    "total_pnl", "current_option_symbol"
]
for metric in trading_metrics:
    if metric not in st.session_state:
        if metric in ["entry_price", "target_price", "stoploss_price", "total_pnl"]:
            st.session_state[metric] = 0.0
        elif metric in ["trade_count", "wins", "losses"]:
            st.session_state[metric] = 0
        else:
            st.session_state[metric] = None

# --- Static API Details ---
API_KEY = "o6z9vadhlia8llh1"
API_SECRET = "q7ierqpe1lv6b2lgmic58230iax2g22g"

# Helper function to append application logs
def add_log(message):
    timestamp = get_indian_time().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    if len(st.session_state.logs) > 100:  # Keep last 100 entries
        st.session_state.logs.pop(0)

# --- Layout Structure ---
st.title("🤖 Nifty Options Auto-Trading Bot")
st.caption("Zerodha Kite API Live Auto Buy + Auto Sell Dashboard")

# --- Sidebar: Authentication & Configuration Parameters ---
with st.sidebar:
    st.header("🔑 Authentication")
    
    if not st.session_state.logged_in:
        try:
            temporary_kite = KiteConnect(api_key=API_KEY)
            login_url = temporary_kite.login_url()
            
            st.markdown(f"[🔗 Click Here to Generate Request Token]({login_url})", unsafe_allow_html=True)
            req_token = st.text_input("Enter Request Token:", type="password")
            
            if st.button("Authenticate & Log In", use_container_width=True):
                if req_token:
                    try:
                        data = temporary_kite.generate_session(request_token=req_token.strip(), api_secret=API_SECRET)
                        temporary_kite.set_access_token(data["access_token"])
                        
                        st.session_state.kite = temporary_kite
                        st.session_state.logged_in = True
                        add_log("✅ Login successful and authenticated.")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Authentication Failed: {err}")
                else:
                    st.warning("Please enter a valid request token.")
        except Exception as e:
            st.error(f"Error initializing Kite API: {e}")
    else:
        st.success("🔒 Authenticated & Connected")
        if st.button("Log Out & Clear Session"):
            st.session_state.logged_in = False
            st.session_state.kite = None
            st.session_state.bot_running = False
            st.rerun()

    st.markdown("---")
    st.header("⚙️ Strategy Parameters")
    
    INTERVAL = st.selectbox("Historical Data Interval", ["minute", "3minute", "5minute", "15minute"], index=1)
    REFRESH_TIME = st.slider("Refresh Rate (seconds)", min_value=2, max_value=30, value=5)
    LOT_SIZE = st.number_input("Lot Size (Qty)", min_value=1, value=65, step=1)
    
    col_param1, col_param2 = st.columns(2)
    with col_param1:
        TARGET_POINTS = st.number_input("Target (Pts)", min_value=1, value=8)
        TRAIL_TRIGGER = st.number_input("Trail Trigger (Pts)", min_value=1, value=4)
    with col_param2:
        STOPLOSS_POINTS = st.number_input("Stoploss (Pts)", min_value=1, value=4)
        MAX_TRADES_PER_DAY = st.number_input("Max Daily Trades", min_value=1, value=10)
        
    MAX_DAILY_LOSS = st.number_input("Max Daily Loss Limit (₹)", value=-3000, max_value=0, step=250)
    SLIPPAGE_POINTS = st.number_input("Market Protection Limit Slippage (Pts)", value=2.0, step=0.5)
    INSTRUMENT_TOKEN = 256265
    # =========================================================
# PART 2: TRADING FUNCTIONS, DASHBOARD UI, & RUNTIME LOOP
# =========================================================

# --- Fetch Nifty Historical Data ---
def get_data():
    try:
        to_date = get_indian_time()
        from_date = to_date - timedelta(days=3)
        
        data = st.session_state.kite.historical_data(
            instrument_token=INSTRUMENT_TOKEN,
            from_date=from_date,
            to_date=to_date,
            interval=INTERVAL
        )
        return pd.DataFrame(data)
    except Exception as e:
        add_log(f"⚠️ Error fetching historical data (Likely API overload): {e}")
        return pd.DataFrame()

# --- Apply Indicators ---
def apply_indicators(df):
    if df.empty:
        return df
    try:
        ema9 = EMAIndicator(close=df['close'], window=9)
        ema21 = EMAIndicator(close=df['close'], window=21)
        df['EMA9'] = ema9.ema_indicator()
        df['EMA21'] = ema21.ema_indicator()

        macd = MACD(close=df['close'])
        df['MACD'] = macd.macd()
        df['SIGNAL'] = macd.macd_signal()

        rsi = RSIIndicator(close=df['close'])
        df['RSI'] = rsi.rsi()
    except Exception as e:
        add_log(f"⚠️ Error applying indicators: {e}")
    return df

# --- Signal Generator ---
def generate_signal(df):
    if df.empty or len(df) < 2:
        return "HOLD"
    
    latest = df.iloc[-1]
    bullish = (
        latest['EMA9'] > latest['EMA21'] and 
        (latest['MACD'] - latest['SIGNAL']) > -0.5 and 
        latest['RSI'] > 48
    )
    bearish = (
        latest['EMA9'] < latest['EMA21'] and 
        (latest['MACD'] - latest['SIGNAL']) < 0.5 and 
        latest['RSI'] < 52
    )

    if bullish:
        return "CALL"
    elif bearish:
        return "PUT"
    return "HOLD"

# --- Dynamic ATM Option Selector ---
def get_option_symbol(signal):
    try:
        ltp = st.session_state.kite.ltp("NSE:NIFTY 50")
        if not ltp or "NSE:NIFTY 50" not in ltp:
            return None
            
        nifty_price = ltp["NSE:NIFTY 50"]['last_price']
        strike = round(nifty_price / 50) * 50

        instruments = st.session_state.kite.instruments("NFO")
        
        expiry = None
        for item in instruments:
            if item['name'] == 'NIFTY' and item['segment'] == 'NFO-OPT':
                expiry = item['expiry']
                break

        option_type = "CE" if signal == "CALL" else "PE"
        
        for item in instruments:
            if (item['name'] == 'NIFTY' and 
                item['segment'] == 'NFO-OPT' and 
                item['strike'] == strike and 
                item['instrument_type'] == option_type and 
                item['expiry'] == expiry):
                return item['tradingsymbol']
    except Exception as e:
        add_log(f"⚠️ Error parsing option contract: {e}")
    return None

# --- Fixed Limit Order Execution (Acts like Market Protection) ---
def place_order(symbol, transaction_type, live_price):
    try:
        # Calculate localized execution protection buffer
        if transaction_type == st.session_state.kite.TRANSACTION_TYPE_BUY:
            execution_price = round(live_price + float(SLIPPAGE_POINTS), 1)
        else:
            execution_price = round(live_price - float(SLIPPAGE_POINTS), 1)
            if execution_price <= 0:
                execution_price = 0.5 # Avoid zero/negative edge conditions

        order_id = st.session_state.kite.place_order(
            variety=st.session_state.kite.VARIETY_REGULAR,
            exchange=st.session_state.kite.EXCHANGE_NFO,
            tradingsymbol=symbol,
            transaction_type=transaction_type,
            quantity=int(LOT_SIZE),
            order_type=st.session_state.kite.ORDER_TYPE_LIMIT, # Replaced pure MARKET type
            price=execution_price,                             # Set defined slippage edge limit
            product=st.session_state.kite.PRODUCT_MIS
        )
        return order_id
    except Exception as e:
        add_log(f"❌ Order Placement Error ({transaction_type}): {e}")
        return None

# =========================================================
# MAIN DASHBOARD INTERFACE LAYOUT
# =========================================================

col_ctrl1, col_ctrl2 = st.columns(2)
with col_ctrl1:
    if st.button("▶️ START BOT", key="start_btn", disabled=not st.session_state.logged_in or st.session_state.bot_running, use_container_width=True):
        st.session_state.bot_running = True
        add_log("🤖 Algo Engine Started.")
        st.rerun()

with col_ctrl2:
    if st.button("⏸️ STOP BOT", key="stop_btn", disabled=not st.session_state.bot_running, use_container_width=True):
        st.session_state.bot_running = False
        add_log("🛑 Algo Engine Stopped Manually.")
        st.rerun()

st.markdown("### 📊 Live Performance Summary")
m_col1, m_col2, m_col3, m_col4 = st.columns(4)

win_rate = 0.0
if st.session_state.trade_count > 0:
    win_rate = round((st.session_state.wins / st.session_state.trade_count) * 100, 2)

m_col1.metric("Total Trades", st.session_state.trade_count)
m_col2.metric("Wins / Losses", f"🟢 {st.session_state.wins} / 🔴 {st.session_state.losses}")
m_col3.metric("Win Rate", f"{win_rate}%")
m_col4.metric("Total Realized PnL", f"₹ {round(st.session_state.total_pnl, 2)}")

left_view, right_view = st.columns([2, 1])

with left_view:
    st.markdown("### 📈 Live Telemetry & Open Positions")
    active_pos_container = st.empty()
    technical_container = st.empty()

with right_view:
    st.markdown("### 📜 Application Logs")
    log_container = st.empty()

# =========================================================
# BACKGROUND LIVE EXECUTION ENGINE LOOP
# =========================================================
if st.session_state.bot_running and st.session_state.logged_in:
    try:
        if st.session_state.total_pnl <= MAX_DAILY_LOSS:
            add_log("🛑 Critical: MAX DAILY LOSS LIMIT HIT. Halting systems.")
            st.session_state.bot_running = False
            st.rerun()

        if st.session_state.trade_count >= MAX_TRADES_PER_DAY:
            add_log("🛑 Alert: Max daily targeted trade limits satisfied.")
            st.session_state.bot_running = False
            st.rerun()

        # Gather Pipeline Telemetry with Safe Server Network Error Boundaries
        ltp_data = st.session_state.kite.ltp("NSE:NIFTY 50")
        
        if ltp_data and "NSE:NIFTY 50" in ltp_data:
            current_price = ltp_data["NSE:NIFTY 50"]['last_price']
            df_raw = get_data()
            df_ind = apply_indicators(df_raw)
            
            bot_signal = "HOLD"
            latest_row = {}
            if not df_ind.empty:
                latest_row = df_ind.iloc[-1]
                bot_signal = generate_signal(df_ind)

            # 1. Update Dashboard Indicators
            with technical_container.container():
                st.write(f"**Spot Index Price (NIFTY 50):** `{current_price}`")
                if len(latest_row) > 0:
                    t_col1, t_col2, t_col3 = st.columns(3)
                    t_col1.metric("EMA 9 / 21", f"{round(latest_row['EMA9'], 2)} / {round(latest_row['EMA21'],2)}")
                    t_col2.metric("MACD / Signal Line", f"{round(latest_row['MACD'], 2)} / {round(latest_row['SIGNAL'],2)}")
                    t_col3.metric("RSI Value", round(latest_row['RSI'], 2))
                st.info(f"⚡ Current Strategy Matrix Engine Signal: **{bot_signal}**")

            # 2. Position Engine Core State Machine Flow
            if st.session_state.position is None:
                with active_pos_container.container():
                    st.warning("⚠️ No Active Position Open.")
                
                # Entry Handler
                if bot_signal in ["CALL", "PUT"]:
                    opt_sym = get_option_symbol(bot_signal)
                    if opt_sym:
                        opt_ltp_raw = st.session_state.kite.ltp(f"NFO:{opt_sym}")
                        if opt_ltp_raw and f"NFO:{opt_sym}" in opt_ltp_raw:
                            approx_ltp = opt_ltp_raw[f"NFO:{opt_sym}"]['last_price']
                            
                            order_id = place_order(opt_sym, st.session_state.kite.TRANSACTION_TYPE_BUY, approx_ltp)
                            if order_id:
                                st.session_state.current_option_symbol = opt_sym
                                st.session_state.entry_price = approx_ltp
                                st.session_state.target_price = approx_ltp + TARGET_POINTS
                                st.session_state.stoploss_price = approx_ltp - STOPLOSS_POINTS
                                st.session_state.trade_side = bot_signal
                                st.session_state.position = "OPEN"
                                st.session_state.trade_count += 1
                                
                                add_log(f"🟢 Long Entry Open: Bought Limit Protected {opt_sym} near ₹{approx_ltp}")
                                st.rerun()
            else:
                # Inside Active Position Management State
                opt_symbol = st.session_state.current_option_symbol
                opt_ltp_data = st.session_state.kite.ltp(f"NFO:{opt_symbol}")
                
                if opt_ltp_data and f"NFO:{opt_symbol}" in opt_ltp_data:
                    live_opt_price = opt_ltp_data[f"NFO:{opt_symbol}"]['last_price']
                    
                    pnl_points = live_opt_price - st.session_state.entry_price
                    current_pnl = pnl_points * LOT_SIZE

                    # Dynamic Trailing SL Logic Adjustments
                    if pnl_points >= TRAIL_TRIGGER:
                        if st.session_state.stoploss_price < st.session_state.entry_price:
                            st.session_state.stoploss_price = st.session_state.entry_price
                            add_log(f"🔄 Trailing SL moved to entry price: ₹{st.session_state.entry_price}")
                    
                    if pnl_points >= 6:
                        if st.session_state.stoploss_price < (st.session_state.entry_price + 3):
                            st.session_state.stoploss_price = st.session_state.entry_price + 3
                            add_log(f"🔄 Trailing SL locked in green (+3 pts): ₹{st.session_state.stoploss_price}")

                    with active_pos_container.container():
                        st.success(f"📌 ACTIVE POSITION: {opt_symbol} ({st.session_state.trade_side})")
                        ap_col1, ap_col2, ap_col3 = st.columns(3)
                        ap_col1.write(f"**Entry Price:** ₹{st.session_state.entry_price}")
                        ap_col1.write(f"**Current Price:** ₹{live_opt_price}")
                        ap_col2.write(f"**Target Price:** ₹{st.session_state.target_price}")
                        ap_col2.write(f"**Stop Loss:** ₹{round(st.session_state.stoploss_price, 2)}")
                        ap_col3.metric("Unrealized PnL", f"₹ {round(current_pnl, 2)}", delta=f"{round(pnl_points, 2)} pts")

                    # Exit Engine Handling Block
                    if live_opt_price >= st.session_state.target_price:
                        order_id = place_order(opt_symbol, st.session_state.kite.TRANSACTION_TYPE_SELL, live_opt_price)
                        if order_id:
                            st.session_state.wins += 1
                            st.session_state.total_pnl += current_pnl
                            st.session_state.position = None
                            add_log(f"✅ TARGET HIT: Closed {opt_symbol} for profit of ₹{round(current_pnl, 2)}")
                            st.rerun()

                    elif live_opt_price <= st.session_state.stoploss_price:
                        order_id = place_order(opt_symbol, st.session_state.kite.TRANSACTION_TYPE_SELL, live_opt_price)
                        if order_id:
                            st.session_state.losses += 1
                            st.session_state.total_pnl += current_pnl
                            st.session_state.position = None
                            add_log(f"❌ STOPLOSS HIT: Closed {opt_symbol} with PnL of ₹{round(current_pnl, 2)}")
                            st.rerun()
        else:
            add_log("⚠️ Data synchronization warning. Zerodha servers unreachable or sluggish.")

    except Exception as loops_err:
        add_log(f"⚠️ Loop Exception Encountered (Handled): {loops_err}")

    with log_container.container():
        st.text_area("Live Event Ledger Log Window", value="\n".join(reversed(st.session_state.logs)), height=250, label_visibility="collapsed")

    time.sleep(REFRESH_TIME)
    st.rerun()
else:
    with technical_container.container():
        st.info("💡 Bot is idling. Connect session parameters and click 'START BOT' to begin live tracking.")
    with log_container.container():
        st.text_area("Live Event Ledger Log Window", value="\n".join(reversed(st.session_state.logs)), height=250, label_visibility="collapsed")
