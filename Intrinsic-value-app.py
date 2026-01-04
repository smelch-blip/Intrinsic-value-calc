import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback

# ============================================================
# SYSTEM CONFIG
# ============================================================
st.set_page_config(page_title="Wealth Architect Pro", layout="wide")

# Styling for a clean, professional dashboard
st.markdown("""
<style>
    .stMetric { background: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; }
    .stApp { background-color: #f8fafc; }
    h1 { color: #1e293b; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HELPERS
# ============================================================
def _sf(x):
    try:
        if x is None or pd.isna(x): return None
        return float(x)
    except: return None

# ============================================================
# DATA FETCHING (FIXED VERSION)
# ============================================================
@st.cache_data(ttl=600)
def fetch_data(ticker_str):
    """
    Fetches data using the latest yfinance logic. 
    Note: yfinance now handles browser impersonation automatically via curl_cffi.
    """
    t = yf.Ticker(ticker_str)
    
    try:
        # Fetching .info is the most comprehensive handshake
        raw_info = t.info
        
        # Build a clean data bundle
        return {
            "ltp": raw_info.get('currentPrice') or raw_info.get('previousClose'),
            "info": raw_info,
            "income": t.income_stmt,
            "balance": t.balance_sheet,
            "cashflow": t.cashflow,
            "shares": raw_info.get('sharesOutstanding')
        }
    except Exception as e:
        # Check for rate limit issues specifically
        if "Rate Limit" in str(e) or "429" in str(e):
            st.error("⏳ Yahoo is rate-limiting the Streamlit server. Please wait 2 minutes.")
        raise e

# ============================================================
# VALUATION ENGINE
# ============================================================
def run_valuation(data):
    # 1. Classification
    info = data['info']
    industry = info.get('industry', '').lower()
    sector = info.get('sector', '').lower()
    
    if "bank" in industry or "financial" in sector:
        biz = "FINANCIAL"
    elif any(x in sector for x in ["energy", "materials", "utilities"]):
        biz = "CYCLICAL"
    else:
        biz = "GENERAL"

    # 2. Extract Values
    shares = _sf(data['shares'])
    ltp = _sf(data['ltp'])
    
    # 3. Models
    models = {}
    
    # DCF (Growth based)
    try:
        # Get latest Free Cash Flow
        fcf = data['cashflow'].loc['Free Cash Flow'].iloc[0]
        if fcf and shares:
            # Simple 2-stage logic: 15x multiple exit
            models["DCF (Growth)"] = (fcf * 15) / shares
    except: models["DCF (Growth)"] = None
    
    # EPV (Earnings Power Value)
    try:
        ebit = data['income'].loc['EBIT'].iloc[0]
        if ebit and shares:
            # Assuming 12% cost of capital and 25% tax
            models["EPV (Earnings Power)"] = (ebit * 0.75 / 0.12) / shares
    except: models["EPV (Earnings Power)"] = None

    # PB Intrinsic (Asset based)
    try:
        roe = info.get('returnOnEquity', 0.12)
        bv = info.get('bookValue')
        if bv:
            # Justified P/B multiple
            models["P/B Intrinsic"] = bv * (roe / 0.12)
    except: models["P/B Intrinsic"] = None

    # 4. Intelligent Weighted Blend
    weights = {
        "FINANCIAL": {"P/B Intrinsic": 0.8, "EPV (Earnings Power)": 0.2, "DCF (Growth)": 0.0},
        "CYCLICAL": {"EPV (Earnings Power)": 0.6, "DCF (Growth)": 0.2, "P/B Intrinsic": 0.2},
        "GENERAL": {"DCF (Growth)": 0.4, "EPV (Earnings Power)": 0.4, "P/B Intrinsic": 0.2}
    }.get(biz)

    weighted_val = 0
    total_w = 0
    for m, val in models.items():
        if val is not None and m in weights:
            weighted_val += val * weights[m]
            total_w += weights[m]
    
    fair_value = weighted_val / total_w if total_w > 0 else None
    
    return biz, models, fair_value

# ============================================================
# USER INTERFACE
# ============================================================
def main():
    st.title("🏛️ Intelligent Valuation Deep-Dive")
    st.caption("Professional-grade intrinsic valuation for NSE stocks.")

    with st.sidebar:
        st.header("Parameters")
        mos = st.slider("Margin of Safety (%)", 0, 50, 20)
        st.info("The Margin of Safety (MoS) protects you from errors in estimation.")

    ticker_input = st.text_input("Enter NSE Ticker (e.g. RELIANCE, TCS, HDFCBANK)", "TCS").upper().strip()
    
    if ticker_input:
        # Auto-append .NS for NSE stocks
        ticker = ticker_input if ticker_input.endswith((".NS", ".BO")) else f"{ticker_input}.NS"
        
        if st.button("Run Valuation Analysis"):
            try:
                with st.spinner(f"Fetching financial statements for {ticker}..."):
                    # Step 1: Fetch
                    data = fetch_data(ticker)
                    
                    # Step 2: Calculate
                    biz, results, fair_value = run_valuation(data)
                    
                    # Step 3: Display Metrics
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Current Price", f"₹{round(data['ltp'], 2)}")
                    
                    if fair_value:
                        upside = (fair_value / data['ltp'] - 1) * 100
                        c2.metric("Intelligent Fair Value", f"₹{round(fair_value, 2)}", f"{round(upside, 1)}% Upside")
                        
                        mos_price = fair_value * (1 - mos/100)
                        c3.metric(f"MoS Buy Price ({mos}%)", f"₹{round(mos_price, 2)}")
                    
                    st.divider()
                    
                    # Step 4: Model Breakdown
                    st.subheader("Model Outputs")
                    m_cols = st.columns(3)
                    for i, (name, val) in enumerate(results.items()):
                        with m_cols[i]:
                            if val:
                                st.write(f"**{name}**")
                                st.title(f"₹{round(val, 2)}")
                            else:
                                st.write(f"**{name}**")
                                st.write("Data missing in Yahoo reports.")

            except Exception:
                st.error("A critical data error occurred. This is often due to Yahoo Finance rate limits.")
                st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
