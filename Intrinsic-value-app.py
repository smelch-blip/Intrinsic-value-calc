import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

st.title("📊 Stock Intrinsic Value Calculator")
st.markdown("Calculate DCF, DDM, and PE-based intrinsic values for any stock")

# Sidebar for input method selection
st.sidebar.header("Data Input Method")
input_method = st.sidebar.radio(
    "Choose data source:",
    ["Auto-fetch (Yahoo Finance)", "Manual Input"]
)

if input_method == "Auto-fetch (Yahoo Finance)":
    # Auto-fetch section
    st.header("🔍 Stock Selection")
    ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA):", value="AAPL")

    if st.button("Fetch Data & Calculate"):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            cash_flow = stock.cashflow
            financials = stock.financials

            # Display basic info
            st.subheader(f"📈 {info.get('longName', ticker)} ({ticker})")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Current Price", f"${info.get('currentPrice', 'N/A')}")
            with col2:
                st.metric("Market Cap", f"${info.get('marketCap', 'N/A'):,}")
            with col3:
                st.metric("P/E Ratio", f"{info.get('trailingPE', 'N/A')}")

            # Intrinsic Value Parameters
            st.header("💰 Intrinsic Value Calculations")
            st.subheader("DCF Parameters")
            col1, col2, col3 = st.columns(3)
            with col1:
                growth_rate = st.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
            with col2:
                discount_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 12.0) / 100
            with col3:
                terminal_growth = st.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100

            # DCF Calculation
            try:
                if 'Free Cash Flow' in cash_flow.index:
                    fcf_data = cash_flow.loc['Free Cash Flow'].dropna()
                    if len(fcf_data) > 0:
                        latest_fcf = fcf_data.iloc[0]
                        years = 5
                        projected_fcf = []
                        fcf = latest_fcf

                        for i in range(years):
                            fcf *= (1 + growth_rate)
                            projected_fcf.append(fcf)

                        terminal_value = projected_fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
                        pv_fcf = [fcf / (1 + discount_rate) ** (i + 1) for i, fcf in enumerate(projected_fcf)]
                        pv_terminal = terminal_value / (1 + discount_rate) ** years
                        enterprise_value = sum(pv_fcf) + pv_terminal

                        shares_outstanding = info.get('sharesOutstanding', info.get('impliedSharesOutstanding', 1))
                        dcf_value = enterprise_value / shares_outstanding

                        st.subheader("📊 DCF Results")
                        st.write(f"**DCF Intrinsic Value:** ${dcf_value:.2f}")
                        st.write(f"**Current Price:** ${info.get('currentPrice', 0):.2f}")
                        if dcf_value > info.get('currentPrice', 0):
                            st.success("Stock appears UNDERVALUED based on DCF")
                        else:
                            st.error("Stock appears OVERVALUED based on DCF")
            except Exception as e:
                st.error(f"Error in DCF Calculation: {e}")

            # PE Multiple
            current_pe = info.get('trailingPE')
            eps = info.get('trailingEps')
            if current_pe and eps:
                forward_eps = eps * (1 + growth_rate)
                pe_value = forward_eps * current_pe

                st.subheader("📊 PE Multiple Results")
                st.write(f"**PE-based Value:** ${pe_value:.2f}")
                st.write(f"**Current Price:** ${info.get('currentPrice', 0):.2f}")
                if pe_value > info.get('currentPrice', 0):
                    st.success("Stock appears UNDERVALUED based on PE")
                else:
                    st.error("Stock appears OVERVALUED based on PE")

            # DDM Model
            dividend_yield = info.get('dividendYield')
            if dividend_yield and dividend_yield > 0:
                dividend_per_share = info.get('currentPrice', 0) * dividend_yield
                ddm_value = dividend_per_share * (1 + terminal_growth) / (discount_rate - terminal_growth)

                st.subheader("📊 DDM Results")
                st.write(f"**DDM Intrinsic Value:** ${ddm_value:.2f}")
                st.write(f"**Current Price:** ${info.get('currentPrice', 0):.2f}")
                if ddm_value > info.get('currentPrice', 0):
                    st.success("Stock appears UNDERVALUED based on DDM")
                else:
                    st.error("Stock appears OVERVALUED based on DDM")
            else:
                st.info("DDM not applicable - stock doesn't pay dividends or data unavailable")

        except Exception as e:
            st.error(f"Error fetching data: {str(e)}")

else:
    # Manual Input Mode
    st.header("✏️ Manual Data Input")
    company_name = st.text_input("Company Name:", value="Example Corp")
    col1, col2 = st.columns(2)

    with col1:
        current_price = st.number_input("Current Stock Price ($):", value=100.0)
        free_cash_flow = st.number_input("Latest Free Cash Flow (millions $):", value=1000.0)
        shares_outstanding = st.number_input("Shares Outstanding (millions):", value=100.0)
        eps = st.number_input("Earnings Per Share ($):", value=5.0)
        dividend_per_share = st.number_input("Dividend Per Share ($):", value=2.0)

    with col2:
        growth_rate = st.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
        discount_rate = st.slider("Discount Rate/WACC (%)", 5.0, 20.0, 12.0) / 100
        terminal_growth = st.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100
        pe_ratio = st.number_input("Current P/E Ratio:", value=20.0)

    if st.button("Calculate Intrinsic Values"):
        years = 5
        projected_fcf = []
        fcf = free_cash_flow * 1e6
        for i in range(years):
            fcf *= (1 + growth_rate)
            projected_fcf.append(fcf)

        terminal_value = projected_fcf[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
        pv_fcf = [fcf / (1 + discount_rate) ** (i + 1) for i, fcf in enumerate(projected_fcf)]
        pv_terminal = terminal_value / (1 + discount_rate) ** years
        enterprise_value = sum(pv_fcf) + pv_terminal
        dcf_value = enterprise_value / (shares_outstanding * 1e6)

        forward_eps = eps * (1 + growth_rate)
        pe_value = forward_eps * pe_ratio

        if dividend_per_share > 0:
            ddm_value = dividend_per_share * (1 + terminal_growth) / (discount_rate - terminal_growth)
        else:
            ddm_value = None

        col1, col2, col3 = st.columns(3)
        col1.metric("DCF Value", f"${dcf_value:.2f}")
        col2.metric("PE-based", f"${pe_value:.2f}")
        col3.metric("DDM Value", f"${ddm_value:.2f}" if ddm_value else "N/A")

# Sidebar
st.sidebar.header("ℹ️ About")
st.sidebar.info("""
This calculator uses three valuation methods:

**DCF (Discounted Cash Flow)**  
Projects future free cash flows and discounts them to present value.

**PE Multiple**  
Uses earnings and a market multiple to arrive at fair value.

**DDM (Dividend Discount Model)**  
Applies to dividend-paying stocks using growth-adjusted dividends.
""")

st.sidebar.header("⚠️ Disclaimer")
st.sidebar.warning("This tool is for educational purposes only. Not financial advice.")
