import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

# Set page configuration
st.set_page_config(page_title="📊 Stock Intrinsic Value App", layout="wide")
st.title("📊 Stock Intrinsic Value Calculator")
st.markdown("Use DCF, PE, and DDM to assess a stock's true worth — now with sector-based valuation weights and recommendations.")

# Define sector-specific default weights
default_weights = {
    "Tech": {"DCF": 0.6, "PE": 0.3, "DDM": 0.1},
    "FMCG": {"DCF": 0.4, "PE": 0.5, "DDM": 0.1},
    "Utilities": {"DCF": 0.2, "PE": 0.4, "DDM": 0.4},
    "Startups": {"DCF": 0.8, "PE": 0.1, "DDM": 0.1},
    "Banking": {"DCF": 0.3, "PE": 0.5, "DDM": 0.2},
    "Retail": {"DCF": 0.5, "PE": 0.4, "DDM": 0.1}
}

# Sidebar - input method and sector
st.sidebar.header("🛠️ Options")
input_method = st.sidebar.radio("Choose input method:", ["Auto-fetch (Yahoo Finance)", "Manual Input"])
selected_sector = st.sidebar.selectbox("Select Sector", list(default_weights.keys()))

st.sidebar.markdown("### ⚖️ Customize Weights")
dcf_weight = st.sidebar.slider("DCF Weight", 0.0, 1.0, default_weights[selected_sector]["DCF"])
pe_weight = st.sidebar.slider("PE Weight", 0.0, 1.0, default_weights[selected_sector]["PE"])
ddm_weight = st.sidebar.slider("DDM Weight", 0.0, 1.0, default_weights[selected_sector]["DDM"])

# Normalize weights
total_weight = dcf_weight + pe_weight + ddm_weight
if total_weight == 0:
    dcf_weight, pe_weight, ddm_weight = 1, 0, 0
else:
    dcf_weight /= total_weight
    pe_weight /= total_weight
    ddm_weight /= total_weight

# Function to calculate DCF
def calculate_dcf(fcf, growth, discount, terminal_growth, years=5):
    projected_fcf = [(fcf * (1 + growth) ** i) / (1 + discount) ** i for i in range(1, years + 1)]
    terminal_value = (projected_fcf[-1] * (1 + terminal_growth)) / (discount - terminal_growth)
    terminal_value /= (1 + discount) ** years
    return sum(projected_fcf) + terminal_value

# --------- MAIN LOGIC ---------
if input_method == "Auto-fetch (Yahoo Finance)":
    ticker = st.text_input("Enter Stock Ticker (e.g., AAPL, INFY):", "AAPL")

    if st.button("Fetch & Calculate"):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            cashflow = stock.cashflow

            st.subheader(f"{info.get('longName', ticker)} ({ticker})")
            col1, col2, col3 = st.columns(3)
            col1.metric("Price", f"${info.get('currentPrice', 'N/A')}")
            col2.metric("Market Cap", f"${info.get('marketCap', 0):,}")
            col3.metric("P/E Ratio", info.get("trailingPE", "N/A"))

            st.subheader("⚙️ Valuation Parameters")
            col1, col2, col3 = st.columns(3)
            with col1:
                g_rate = st.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
            with col2:
                d_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 12.0) / 100
            with col3:
                t_growth = st.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100

            # DCF
            dcf_value = None
            if "Free Cash Flow" in cashflow.index:
                fcf_data = cashflow.loc["Free Cash Flow"].dropna()
                if not fcf_data.empty:
                    fcf = fcf_data.iloc[0]
                    dcf_total = calculate_dcf(fcf, g_rate, d_rate, t_growth)
                    shares = info.get("sharesOutstanding", 1)
                    dcf_value = dcf_total / shares

            # PE
            pe_value = None
            if info.get("trailingPE") and info.get("trailingEps"):
                forward_eps = info["trailingEps"] * (1 + g_rate)
                pe_value = forward_eps * info["trailingPE"]

            # DDM
            ddm_value = None
            if info.get("dividendYield"):
                div_per_share = info.get("currentPrice", 0) * info["dividendYield"]
                ddm_value = div_per_share * (1 + t_growth) / (d_rate - t_growth)

            # Compute Weighted Average
            weighted_intrinsic = 0
            value_count = 0

            if dcf_value:
                weighted_intrinsic += dcf_weight * dcf_value
                value_count += 1
            if pe_value:
                weighted_intrinsic += pe_weight * pe_value
                value_count += 1
            if ddm_value:
                weighted_intrinsic += ddm_weight * ddm_value
                value_count += 1

            if value_count > 0:
                current_price = info.get("currentPrice", 0)
                upside = ((weighted_intrinsic - current_price) / current_price) * 100

                st.header("📊 Final Summary")
                st.write(f"**Weighted Intrinsic Value:** ${weighted_intrinsic:.2f}")
                st.write(f"**Current Market Price:** ${current_price:.2f}")
                st.write(f"**Upside/Downside:** {upside:.1f}%")

                if upside >= 20:
                    st.success("✅ Recommendation: BUY (Stock appears undervalued)")
                else:
                    st.warning("⚠️ Recommendation: HOLD or RESEARCH FURTHER")
            else:
                st.error("Not enough data available to calculate intrinsic value.")

        except Exception as e:
            st.error(f"Error fetching data: {e}")

else:
    # Manual Input
    st.subheader("✏️ Manual Data Input")
    name = st.text_input("Company Name", "Example Corp")
    current_price = st.number_input("Current Price", value=100.0)
    fcf = st.number_input("Free Cash Flow (millions)", value=100.0) * 1e6
    shares = st.number_input("Shares Outstanding (millions)", value=100.0) * 1e6
    eps = st.number_input("EPS", value=5.0)
    dividend = st.number_input("Dividend Per Share", value=2.0)
    pe_ratio = st.number_input("PE Ratio", value=20.0)

    g_rate = st.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
    d_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 12.0) / 100
    t_growth = st.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100

    if st.button("Calculate Intrinsic Value"):
        dcf_val = calculate_dcf(fcf, g_rate, d_rate, t_growth) / shares
        pe_val = eps * (1 + g_rate) * pe_ratio
        ddm_val = dividend * (1 + t_growth) / (d_rate - t_growth) if dividend > 0 else None

        weighted_intrinsic = (
            (dcf_val * dcf_weight if dcf_val else 0) +
            (pe_val * pe_weight if pe_val else 0) +
            (ddm_val * ddm_weight if ddm_val else 0)
        )

        upside = ((weighted_intrinsic - current_price) / current_price) * 100

        st.subheader("📊 Results")
        st.write(f"Weighted Intrinsic Value: ${weighted_intrinsic:.2f}")
        st.write(f"Current Price: ${current_price:.2f}")
        st.write(f"Upside/Downside: {upside:.1f}%")

        if upside >= 20:
            st.success("✅ Recommendation: BUY")
        else:
            st.warning("⚠️ Recommendation: HOLD")

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.markdown("""
### 📘 Methods
- **DCF**: Discounted Cash Flow  
- **PE**: Forward earnings with PE ratio  
- **DDM**: Dividend growth-based model
""")
st.sidebar.warning("This tool is for educational purposes only. Not financial advice.")
