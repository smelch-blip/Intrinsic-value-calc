import streamlit as st
import yfinance as yf
import pandas as pd

# ------------------------- CONFIGURATION -------------------------
st.set_page_config(page_title="📊 Stock Intrinsic Value Calculator", layout="wide")

st.title("📊 Stock Intrinsic Value Calculator")
st.markdown("Use DCF, PE, and DDM to assess a stock's intrinsic value with sector-based weights.")

# ------------------------- SIDEBAR -------------------------
st.sidebar.header("🛠️ Input Options")

input_method = st.sidebar.radio("Choose input mode:", ["Auto-fetch (Yahoo Finance)", "Manual Input"])
sector = st.sidebar.selectbox("Select Sector", ["Tech", "Consumer", "Industrial", "Finance", "Other"])

st.sidebar.markdown("⚖️ **Customize Weights**")
dcf_weight = st.sidebar.slider("DCF Weight", 0.0, 1.0, 0.6)
pe_weight = st.sidebar.slider("PE Weight", 0.0, 1.0, 0.3)
ddm_weight = 1.0 - (dcf_weight + pe_weight)
st.sidebar.markdown(f"**DDM Weight:** {ddm_weight:.2f}")

st.sidebar.markdown("📘 **Methods**")
st.sidebar.markdown("""
- **DCF**: Future cash flow projection  
- **PE**: Forward earnings & market multiple  
- **DDM**: Dividend growth valuation  
""")
st.sidebar.warning("This tool is for educational use only.")

# ------------------------- FUNCTIONS -------------------------
def calculate_dcf(fcf, growth, discount, terminal_growth, years=5):
    projected = [(fcf * (1 + growth) ** i) / (1 + discount) ** i for i in range(1, years + 1)]
    terminal = (projected[-1] * (1 + terminal_growth)) / (discount - terminal_growth)
    terminal /= (1 + discount) ** years
    return sum(projected) + terminal

def format_number(value, is_inr=False):
    if value is None: return "N/A"
    if is_inr:
        return f"₹{value/1e7:,.2f} Cr"
    return f"${value/1e6:,.2f} M"

def get_currency_symbol(ticker):
    return "₹" if ticker.endswith(".NS") or ticker.endswith(".BO") else "$"

# ------------------------- MAIN -------------------------
if input_method == "Auto-fetch (Yahoo Finance)":
    st.subheader("🧠 Valuation Parameters")
    growth_rate = st.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
    discount_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 12.0) / 100
    terminal_growth = st.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100

    stock_input = st.text_input("Enter Stock Name or Ticker (e.g., Tata Motors or TATAMOTORS.NS)", "TATAMOTORS.NS")

    if st.button("Fetch & Calculate"):
        try:
            stock = yf.Ticker(stock_input)
            info = stock.info

            if not isinstance(info, dict) or 'currentPrice' not in info:
                st.error("Could not fetch data. Please check the name or ticker.")
            else:
                is_inr = stock_input.endswith(".NS") or stock_input.endswith(".BO")
                currency = get_currency_symbol(stock_input)

                st.subheader(f"{info.get('longName', 'Unknown Company')} ({stock_input.upper()})")

                col1, col2, col3 = st.columns(3)
                col1.metric("Price", f"{currency}{info.get('currentPrice', 0):,.2f}")
                col2.metric("Market Cap", format_number(info.get('marketCap', 0), is_inr))
                col3.metric("P/E Ratio", f"{info.get('trailingPE', 'N/A')}")

                fcf = None
                if 'Free Cash Flow' in stock.cashflow.index:
                    fcf_series = stock.cashflow.loc['Free Cash Flow'].dropna()
                    if not fcf_series.empty:
                        fcf = fcf_series.iloc[0]

                eps = info.get('trailingEps')
                pe = info.get('trailingPE')
                price = info.get('currentPrice', 0)
                shares = info.get('sharesOutstanding', 1)

                div_yield = info.get('dividendYield')
                div_per_share = price * div_yield if div_yield else 0

                # ------------------ Valuations ------------------
                dcf_val = calculate_dcf(fcf, growth_rate, discount_rate, terminal_growth) / shares if fcf else None
                pe_val = eps * (1 + growth_rate) * pe if pe and eps else None
                ddm_val = div_per_share * (1 + terminal_growth) / (discount_rate - terminal_growth) if div_yield else None

                # ------------------ Output ------------------
                if dcf_val:
                    st.success(f"**DCF Value:** {currency}{dcf_val:.2f}")
                else:
                    st.info("DCF not available")

                if pe_val:
                    st.info(f"**PE-based Value:** {currency}{pe_val:.2f}")
                else:
                    st.info("PE data not available")

                if ddm_val:
                    st.info(f"**DDM Value:** {currency}{ddm_val:.2f}")
                else:
                    st.info("DDM not available")

                # ------------------ Final Weighted ------------------
                available = [(dcf_val, dcf_weight), (pe_val, pe_weight), (ddm_val, ddm_weight)]
                weighted_values = [val * wt for val, wt in available if val is not None]
                total_weight = sum(wt for val, wt in available if val is not None)

                if weighted_values:
                    final_value = sum(weighted_values) / total_weight
                    movement = ((final_value / price) - 1) * 100 if price else 0

                    st.subheader("📌 Valuation Summary")
                    col1, col2 = st.columns(2)
                    col1.metric("Weighted Intrinsic Value", f"{currency}{final_value:.2f}")
                    col2.metric("Current Price", f"{currency}{price:.2f}")

                    if movement > 5:
                        st.success(f"Expected movement: {movement:.2f}% UP")
                    elif movement < -5:
                        st.error(f"Expected movement: {movement:.2f}% DOWN")
                    else:
                        st.info(f"Expected movement: {movement:.2f}% - Fairly Priced")

        except Exception as e:
            st.error(f"Something went wrong while fetching stock data: {e}")

# ------------------------- MANUAL MODE -------------------------
else:
    st.subheader("✍️ Manual Data Input")

    name = st.text_input("Company Name", "Sample Inc")
    col1, col2 = st.columns(2)

    with col1:
        price = st.number_input("Current Price", value=100.0)
        eps = st.number_input("EPS", value=5.0)
        fcf = st.number_input("Free Cash Flow (M)", value=100.0) * 1e6
        shares = st.number_input("Shares Outstanding (M)", value=100.0) * 1e6
        div = st.number_input("Dividend/share", value=2.0)

    with col2:
        pe = st.number_input("P/E Ratio", value=20.0)
        growth_rate = st.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
        discount_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 12.0) / 100
        terminal_growth = st.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100

    if st.button("Calculate"):
        dcf_val = calculate_dcf(fcf, growth_rate, discount_rate, terminal_growth) / shares
        pe_val = eps * (1 + growth_rate) * pe
        ddm_val = div * (1 + terminal_growth) / (discount_rate - terminal_growth)

        final_value = (
            dcf_val * dcf_weight +
            pe_val * pe_weight +
            ddm_val * ddm_weight
        )
        movement = ((final_value / price) - 1) * 100 if price else 0

        st.subheader("📌 Valuation Summary")
        col1, col2 = st.columns(2)
        col1.metric("Weighted Intrinsic Value", f"${final_value:.2f}")
        col2.metric("Current Price", f"${price:.2f}")

        if movement > 5:
            st.success(f"Expected movement: {movement:.2f}% UP")
        elif movement < -5:
            st.error(f"Expected movement: {movement:.2f}% DOWN")
        else:
            st.info(f"Expected movement: {movement:.2f}% - Fairly Priced")
