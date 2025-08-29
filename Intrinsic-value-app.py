
import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf
import requests

# Helper function to get ticker from name
def get_ticker_from_name(query):
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=1&newsCount=0"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        result = response.json()
        if result.get("quotes"):
            quote = result["quotes"][0]
            return quote["symbol"], quote.get("exchange", ""), quote.get("shortname", "")
    return None, None, None

# DCF Calculation
def calculate_dcf(fcf, growth, discount, terminal_growth, years=5):
    projected_fcf = [(fcf * (1 + growth) ** i) / (1 + discount) ** i for i in range(1, years + 1)]
    terminal_value = (projected_fcf[-1] * (1 + terminal_growth)) / (discount - terminal_growth)
    terminal_value /= (1 + discount) ** years
    return sum(projected_fcf) + terminal_value

# UI Setup
st.set_page_config(page_title="Stock Intrinsic Value Calculator", layout="wide")
st.title("📊 Stock Intrinsic Value Calculator")
st.markdown("Use DCF, PE, and DDM to assess a stock's true worth — now with sector-based valuation weights and recommendations.")

# Sidebar Inputs
st.sidebar.header("⚙️ Options")
input_method = st.sidebar.radio("Choose input method:", ["Auto-fetch (Yahoo Finance)", "Manual Input"])
sector = st.sidebar.selectbox("Select Sector", ["Tech", "Finance", "Industrial", "Consumer", "Other"])

st.sidebar.markdown("### ⚖️ Customize Weights")
dcf_weight = st.sidebar.slider("DCF Weight", 0.0, 1.0, 0.6)
pe_weight = st.sidebar.slider("PE Weight", 0.0, 1.0 - dcf_weight, 0.3)
ddm_weight = 1.0 - (dcf_weight + pe_weight)
st.sidebar.markdown(f"**DDM Weight:** {ddm_weight:.2f}")

st.sidebar.markdown("### 📘 Methods")
st.sidebar.markdown("""
- **DCF**: Discounted Cash Flow
- **PE**: Forward earnings with PE ratio
- **DDM**: Dividend growth-based valuation
""")

st.sidebar.warning("This tool is for educational use only.")

# Start main logic
if input_method == "Auto-fetch (Yahoo Finance)":
    stock_name = st.text_input("Enter Stock Name (e.g., Apple, Tata Motors):", value="Apple")

    if st.button("Fetch & Calculate"):
        ticker, exchange, full_name = get_ticker_from_name(stock_name.strip())

        if ticker:
            currency = "₹" if exchange == "NSI" else "$"
            stock = yf.Ticker(ticker)
            info = stock.info
            cashflow = stock.cashflow

            st.subheader(f"{full_name} ({ticker})")
            col1, col2, col3 = st.columns(3)
            col1.metric("Price", f"{currency}{info.get('currentPrice', 'N/A')}")
            col2.metric("Market Cap", f"{currency}{info.get('marketCap', 0):,}")
            col3.metric("P/E Ratio", info.get("trailingPE", "N/A"))

            # Parameters
            st.subheader("⚙️ Valuation Parameters")
            g_rate = st.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
            d_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 12.0) / 100
            t_growth = st.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100

            # DCF
            intrinsic_dcf = None
            fcf = None
            if "Free Cash Flow" in cashflow.index:
                fcf_data = cashflow.loc["Free Cash Flow"].dropna()
                if not fcf_data.empty:
                    fcf = fcf_data.iloc[0]
                    intrinsic_dcf = calculate_dcf(fcf, g_rate, d_rate, t_growth)

            # PE
            eps = info.get("trailingEps")
            pe = info.get("trailingPE")
            intrinsic_pe = eps * (1 + g_rate) * pe if eps and pe else None

            # DDM
            div_yield = info.get("dividendYield")
            current_price = info.get("currentPrice", 0)
            intrinsic_ddm = None
            if div_yield:
                dividend = current_price * div_yield
                intrinsic_ddm = dividend * (1 + t_growth) / (d_rate - t_growth)

            # Weighted value
            all_vals = [v for v in [intrinsic_dcf, intrinsic_pe, intrinsic_ddm] if v is not None]
            if not all_vals:
                st.error("Not enough data available to calculate intrinsic value.")
            else:
                final_value = 0
                if intrinsic_dcf: final_value += intrinsic_dcf * dcf_weight
                if intrinsic_pe: final_value += intrinsic_pe * pe_weight
                if intrinsic_ddm: final_value += intrinsic_ddm * ddm_weight

                final_value = round(final_value, 2)

                st.subheader("📌 Valuation Summary")
                st.metric("Weighted Intrinsic Value", f"{currency}{final_value}")
                st.metric("Current Price", f"{currency}{current_price}")

                diff = final_value - current_price
                perc = (diff / current_price) * 100 if current_price else 0
                direction = "UP" if perc > 0 else "DOWN"
                st.info(f"Expected movement: **{abs(perc):.1f}% {direction}**")
        else:
            st.error("Stock name not found. Try a different one.")
