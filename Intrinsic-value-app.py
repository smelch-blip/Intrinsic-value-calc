
import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Stock Valuation Tool", layout="wide")
st.title("📊 Stock Intrinsic Value Calculator")
st.markdown("Use DCF, PE, and DDM to assess a stock's intrinsic value with sector-based weights.")

# Sidebar
st.sidebar.header("🔧 Input Options")
input_method = st.sidebar.radio("Choose input mode:", ["Auto-fetch (Yahoo Finance)", "Manual Input"])

# Sector-based weight selector (optional expansion later)
sectors = {
    "Tech": (0.6, 0.3, 0.1),
    "Finance": (0.5, 0.4, 0.1),
    "Consumer": (0.4, 0.3, 0.3),
    "Industrial": (0.5, 0.3, 0.2)
}
selected_sector = st.sidebar.selectbox("Select Sector", sectors.keys())
dcf_weight, pe_weight, ddm_weight = sectors[selected_sector]

st.sidebar.markdown("🎛️ Customize Weights")
dcf_weight = st.sidebar.slider("DCF Weight", 0.0, 1.0, dcf_weight)
pe_weight = st.sidebar.slider("PE Weight", 0.0, 1.0, pe_weight)
ddm_weight = st.sidebar.slider("DDM Weight", 0.0, 1.0, ddm_weight)
total_weight = dcf_weight + pe_weight + ddm_weight

if total_weight == 0:
    st.error("All weights are zero. Please adjust at least one weight to proceed.")
    st.stop()

def calculate_dcf(fcf, growth, discount, terminal_growth, years=5):
    projected_fcf = [(fcf * (1 + growth) ** i) / (1 + discount) ** i for i in range(1, years+1)]
    terminal_value = (projected_fcf[-1] * (1 + terminal_growth)) / (discount - terminal_growth)
    terminal_value /= (1 + discount) ** years
    return sum(projected_fcf) + terminal_value

# Auto-fetch mode
if input_method == "Auto-fetch (Yahoo Finance)":
    ticker_input = st.text_input("Enter Stock Name or Ticker (e.g., Tata Motors or TATAMOTORS.NS)", "TATAMOTORS.NS")
    if st.button("Fetch & Calculate"):
        try:
            stock = yf.Ticker(ticker_input)
            info = stock.info
            cashflow = stock.cashflow

            long_name = info.get("longName", "Unknown Company")
            current_price = info.get("currentPrice", 0.0)
            market_cap = info.get("marketCap", 0)
            trailing_pe = info.get("trailingPE", "N/A")
            shares_outstanding = info.get("sharesOutstanding", 1)

            st.header(f"{long_name} ({ticker_input.upper()})")
            col1, col2, col3 = st.columns(3)
            col1.metric("Price", f"₹{current_price:,.2f}")
            col2.metric("Market Cap", f"₹{market_cap:,.2f}")
            col3.metric("P/E Ratio", f"{trailing_pe}")

            st.subheader("⚙️ Valuation Parameters")
            g_rate = st.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
            d_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 12.0) / 100
            t_growth = st.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100

            dcf_value = pe_value = ddm_value = 0.0

            # DCF
            if "Free Cash Flow" in cashflow.index:
                fcf_data = cashflow.loc["Free Cash Flow"].dropna()
                if not fcf_data.empty:
                    fcf = fcf_data.iloc[0]
                    dcf_total = calculate_dcf(fcf, g_rate, d_rate, t_growth)
                    dcf_value = dcf_total / shares_outstanding
                    st.success(f"DCF Value: ₹{dcf_value:.2f}")
                else:
                    st.warning("No recent FCF data for DCF calculation.")

            # PE
            eps = info.get("trailingEps")
            if trailing_pe and eps:
                forward_eps = eps * (1 + g_rate)
                pe_value = forward_eps * trailing_pe
                st.info(f"PE-based Value: ₹{pe_value:.2f}")

            # DDM
            dividend_yield = info.get("dividendYield")
            if dividend_yield:
                dividend = current_price * dividend_yield
                ddm_value = dividend * (1 + t_growth) / (d_rate - t_growth)
                st.info(f"DDM Value: ₹{ddm_value:.2f}")

            # Weighted Average Intrinsic Value
            weighted_val = (
                dcf_value * dcf_weight +
                pe_value * pe_weight +
                ddm_value * ddm_weight
            ) / total_weight

            upside = ((weighted_val - current_price) / current_price) * 100

            st.subheader("📌 Valuation Summary")
            st.metric("Weighted Intrinsic Value", f"₹{weighted_val:.2f}")
            st.metric("Current Price", f"₹{current_price:.2f}")
            st.metric("Expected Movement", f"{upside:.2f}%")

            # Recommendation
            if upside > 15:
                st.success("✅ Recommendation: BUY — Stock is significantly undervalued.")
            elif upside < -15:
                st.error("🚫 Recommendation: SELL — Stock appears overvalued.")
            else:
                st.warning("⚖️ Recommendation: HOLD — Stock is fairly valued.")

        except Exception as e:
            st.error(f"Error fetching data: {e}")
