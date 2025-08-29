
import streamlit as st
import pandas as pd
import numpy as np
from yahooquery import Ticker
import re

st.set_page_config(page_title="Stock Intrinsic Value Calculator", layout="wide")
st.title("📊 Stock Intrinsic Value Calculator")
st.markdown("Use DCF, PE, and DDM to assess a stock's intrinsic value with sector-based weights.")

# Sector weight defaults
SECTOR_WEIGHTS = {
    "Tech": {"DCF": 0.6, "PE": 0.3, "DDM": 0.1},
    "Finance": {"DCF": 0.3, "PE": 0.3, "DDM": 0.4},
    "Consumer": {"DCF": 0.4, "PE": 0.4, "DDM": 0.2},
    "Industrial": {"DCF": 0.5, "PE": 0.4, "DDM": 0.1},
}

# Helper for Indian numbering
def format_inr(value):
    return f"₹{value:,.2f}".replace(",", "_").replace("_", ",")

def format_usd(value):
    return f"${value:,.2f}"

# Calculate DCF Value
def calculate_dcf(fcf, growth, discount, terminal, years=5):
    projected = [(fcf * ((1 + growth) ** i)) / ((1 + discount) ** i) for i in range(1, years + 1)]
    terminal_value = (projected[-1] * (1 + terminal)) / (discount - terminal)
    terminal_value /= (1 + discount) ** years
    return sum(projected) + terminal_value

# Input Panel
st.sidebar.header("🛠️ Input Options")
mode = st.sidebar.radio("Choose input mode:", ["Auto-fetch (Yahoo Finance)", "Manual Input"])
sector = st.sidebar.selectbox("Select Sector", list(SECTOR_WEIGHTS.keys()))
weights = SECTOR_WEIGHTS[sector]

st.sidebar.subheader("⚖️ Customize Weights")
weights["DCF"] = st.sidebar.slider("DCF Weight", 0.0, 1.0, weights["DCF"])
weights["PE"] = st.sidebar.slider("PE Weight", 0.0, 1.0, weights["PE"])
weights["DDM"] = round(1.0 - weights["DCF"] - weights["PE"], 2)
st.sidebar.markdown(f"**DDM Weight:** {weights['DDM']:.2f}")

st.sidebar.subheader("📘 Methods")
st.sidebar.markdown("""
- **DCF**: Future cash flow projection  
- **PE**: Forward earnings & market multiple  
- **DDM**: Dividend growth valuation  
""")
st.sidebar.warning("This tool is for educational use only.")

# Parameters
st.subheader("🧮 Valuation Parameters")
col1, col2, col3 = st.columns(3)
growth_rate = col1.slider("Growth Rate (%)", 0.0, 20.0, 8.0) / 100
discount_rate = col2.slider("Discount Rate (%)", 5.0, 20.0, 12.0) / 100
terminal_growth = col3.slider("Terminal Growth (%)", 0.0, 5.0, 3.0) / 100

# Auto Fetch Mode
if mode == "Auto-fetch (Yahoo Finance)":
    stock_name = st.text_input("Enter Stock Name or Ticker (e.g., Tata Motors or TATAMOTORS.NS)", value="Tata Motors")
    if st.button("Fetch & Calculate"):
        try:
            query = Ticker(stock_name)
            symbol = list(query.symbols)[0]
            info = query.summary_detail[symbol]
            profile = query.asset_profile.get(symbol, {})
            price_info = query.price.get(symbol, {})

            # Extract data
            name = price_info.get("longName", stock_name).upper()
            price = price_info.get("regularMarketPrice", 0)
            mcap = price_info.get("marketCap", 0)
            currency = price_info.get("currency", "INR")
            shares = price_info.get("sharesOutstanding", 1)
            eps = price_info.get("epsTrailingTwelveMonths", None)
            pe_ratio = price_info.get("trailingPE", None)
            dividend_yield = info.get("dividendYield", 0)

            # Free Cash Flow fallback
            cf = query.cash_flow_statement(symbol)
            fcf = cf["freeCashFlow"].dropna().iloc[0] if "freeCashFlow" in cf and not cf["freeCashFlow"].dropna().empty else None

            # Format Currency
            format_currency = format_inr if currency == "INR" else format_usd

            st.subheader(f"{name} ({symbol})")
            col1, col2, col3 = st.columns(3)
            col1.metric("Price", format_currency(price))
            col2.metric("Market Cap", format_currency(mcap))
            col3.metric("P/E Ratio", f"{pe_ratio:.2f}" if pe_ratio else "N/A")

            dcf_val = calculate_dcf(fcf, growth_rate, discount_rate, terminal_growth) / shares if fcf else None
            pe_val = eps * (1 + growth_rate) * pe_ratio if eps and pe_ratio else None
            ddm_val = (price * dividend_yield * (1 + terminal_growth)) / (discount_rate - terminal_growth) if dividend_yield else None

            # Display Individual Models
            if dcf_val:
                st.success(f"✅ DCF Value: {format_currency(dcf_val)}")
            if pe_val:
                st.info(f"📊 PE-based Value: {format_currency(pe_val)}")
            if ddm_val:
                st.info(f"💵 DDM Value: {format_currency(ddm_val)}")

            # Weighted Value
            weighted_val = 0
            divisor = 0
            if dcf_val:
                weighted_val += dcf_val * weights["DCF"]
                divisor += weights["DCF"]
            if pe_val:
                weighted_val += pe_val * weights["PE"]
                divisor += weights["PE"]
            if ddm_val:
                weighted_val += ddm_val * weights["DDM"]
                divisor += weights["DDM"]

            final_val = weighted_val / divisor if divisor > 0 else None
            st.subheader("📌 Valuation Summary")
            if final_val:
                col1, col2 = st.columns(2)
                col1.metric("Weighted Intrinsic Value", format_currency(final_val))
                col2.metric("Current Price", format_currency(price))
                movement = ((final_val / price - 1) * 100) if price else 0
                st.info(f"📈 Expected movement: **{movement:.2f}% {'UP' if movement > 0 else 'DOWN'}**")

        except Exception as e:
            st.error(f"Something went wrong while fetching stock data: {e}")

else:
    st.write("Manual input mode coming soon.")
