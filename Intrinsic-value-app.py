import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Stock Valuation Tool", layout="wide")
st.title("📊 Stock Intrinsic Value Calculator")
st.markdown("Use DCF, PE, and DDM to assess a stock's intrinsic value.")

# Sidebar
st.sidebar.header("🔧 Input Options")
input_method = st.sidebar.radio("Choose input mode:", ["Auto-fetch (Yahoo Finance)", "Manual Input"])

def format_currency(value, currency_symbol):
    return f"{currency_symbol}{value:,.2f}"

def calculate_dcf(fcf, growth, discount, terminal_growth, years=5):
    projected_fcf = [(fcf * (1 + growth) ** i) / (1 + discount) ** i for i in range(1, years+1)]
    terminal_value = (projected_fcf[-1] * (1 + terminal_growth)) / (discount - terminal_growth)
    terminal_value /= (1 + discount) ** years
    return sum(projected_fcf) + terminal_value

if input_method == "Auto-fetch (Yahoo Finance)":
    ticker_input = st.text_input("Enter Stock Ticker or Company Name (e.g., AAPL, TATA MOTORS):", "TATA MOTORS")

    # Name to Ticker Mapping (can be expanded)
    name_to_ticker = {
        "tata motors": "TATAMOTORS.NS",
        "reliance": "RELIANCE.NS",
        "infosys": "INFY.NS",
        "arrow greentech": "ARROW.NS",
        "apple": "AAPL",
        "tesla": "TSLA"
    }

    ticker = name_to_ticker.get(ticker_input.lower().strip(), ticker_input.strip().upper())

    if st.button("Fetch & Calculate"):
        if not ticker:
            st.warning("Please enter a valid ticker.")
        else:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                cashflow = stock.cashflow

                currency = info.get("currency", "USD")
                symbol = "₹" if currency == "INR" else "$"

                if cashflow.empty:
                    st.error("Cash flow data not available.")
                else:
                    st.subheader(f"{info.get('longName', ticker)} ({ticker})")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Price", format_currency(info.get("currentPrice", 0), symbol))
                    col2.metric("Market Cap", format_currency(info.get("marketCap", 0), symbol))
                    col3.metric("P/E Ratio", info.get("trailingPE", "N/A"))

                    st.subheader("⚙️ Valuation Parameters")
                    g_rate = st.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
                    d_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 12.0) / 100
                    t_growth = st.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100

                    # Free Cash Flow
                    fcf = None
                    if 'Free Cash Flow' in cashflow.index:
                        fcf_data = cashflow.loc['Free Cash Flow'].dropna()
                        if not fcf_data.empty:
                            fcf = fcf_data.iloc[0]

                    if fcf:
                        intrinsic_dcf = calculate_dcf(fcf, g_rate, d_rate, t_growth)
                        shares = info.get('sharesOutstanding', 1)
                        dcf_value = intrinsic_dcf / shares
                        st.success(f"DCF Value: {format_currency(dcf_value, symbol)}")
                    else:
                        st.warning("FCF data unavailable.")

                    # PE-based Valuation
                    pe = info.get("trailingPE")
                    eps = info.get("trailingEps")
                    if pe and eps:
                        forward_eps = eps * (1 + g_rate)
                        pe_val = forward_eps * pe
                        st.info(f"PE-based Value: {format_currency(pe_val, symbol)}")

                    # DDM
                    div_yield = info.get("dividendYield")
                    if div_yield:
                        div_per_share = info.get("currentPrice", 0) * div_yield
                        ddm_val = div_per_share * (1 + t_growth) / (d_rate - t_growth)
                        st.info(f"DDM Value: {format_currency(ddm_val, symbol)}")
                    else:
                        st.warning("DDM not applicable – no dividend yield found.")

            except Exception as e:
                st.error(f"Error fetching data: {e}")

# Sidebar Info
st.sidebar.markdown("""
**Valuation Methods:**

- DCF: Future cash flow projection
- PE: Forward earnings & market multiple
- DDM: Dividend growth valuation
""")

st.sidebar.warning("This tool is for educational use only.")
