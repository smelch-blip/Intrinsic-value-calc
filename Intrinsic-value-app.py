import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# SYSTEM CONFIG
# ============================================================
st.set_page_config(page_title="Intelligent Valuation Pro", layout="wide")

# Custom CSS for a professional look
st.markdown("""
<style>
    .reportview-container { background: #f0f2f6; }
    .stMetric { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; }
    .stAlert { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HELPER FUNCTIONS & SESSION FIX
# ============================================================
def get_session():
    """Create a session with headers to avoid Yahoo Rate Limiting"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    })
    # Add retries for stability
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    return session

def _sf(x):
    try:
        if x is None or pd.isna(x): return None
        return float(x)
    except: return None

# ============================================================
# DATA FETCHING (THE FIX)
# ============================================================
@st.cache_data(ttl=600) # 10 minute cache
def fetch_data(ticker_str):
    session = get_session()
    t = yf.Ticker(ticker_str, session=session)
    
    try:
        # Get basic info first (Fast)
        fast = t.fast_info
        ltp = fast.get('last_price')
        
        # Fetch dataframes with fallback
        income = t.income_stmt
        balance = t.balance_sheet
        cashflow = t.cashflow
        info = t.info # This is where rate limits usually happen
        
        return {
            "ltp": ltp,
            "info": info,
            "income": income,
            "balance": balance,
            "cashflow": cashflow,
            "shares": fast.get('shares_outstanding')
        }
    except Exception as e:
        if "Rate Limit" in str(e) or "429" in str(e):
            st.error("🚀 Yahoo Finance Rate Limit hit. Streamlit's IP is temporarily blocked. Please wait 2-3 minutes or try a different ticker.")
        raise e

# ============================================================
# CORE VALUATION MODELS
# ============================================================
def run_valuation(data):
    # 1. Classification
    industry = data['info'].get('industry', '').lower()
    if "bank" in industry or "financial" in industry:
        biz = "FINANCIAL"
    elif any(x in industry for x in ["oil", "steel", "mining", "energy"]):
        biz = "CYCLICAL"
    else:
        biz = "GENERAL"

    # 2. Extract Values
    shares = _sf(data['shares'])
    ltp = _sf(data['ltp'])
    
    # 3. Individual Models
    models = {}
    
    # DCF (Simplified)
    try:
        fcf = data['cashflow'].loc['Free Cash Flow'].iloc[0]
        models["DCF (Growth)"] = (fcf * 15) / shares
    except: models["DCF (Growth)"] = None
    
    # EPV
    try:
        ebit = data['income'].loc['EBIT'].iloc[0]
        models["EPV (Earnings Power)"] = (ebit * 0.75 / 0.12) / shares
    except: models["EPV (Earnings Power)"] = None

    # PB Intrinsic
    try:
        roe = data['info'].get('returnOnEquity', 0.12)
        bv = data['info'].get('bookValue')
        models["P/B Intrinsic"] = bv * (roe / 0.12)
    except: models["P/B Intrinsic"] = None

    # 4. Intelligent Blend (Weighted)
    weights = {
        "FINANCIAL": {"P/B Intrinsic": 0.8, "EPV (Earnings Power)": 0.2, "DCF (Growth)": 0.0},
        "GENERAL": {"DCF (Growth)": 0.4, "EPV (Earnings Power)": 0.4, "P/B Intrinsic": 0.2}
    }.get(biz, {"DCF (Growth)": 0.33, "EPV (Earnings Power)": 0.33, "P/B Intrinsic": 0.33})

    weighted_val = 0
    total_w = 0
    for m, val in models.items():
        if val:
            weighted_val += val * weights[m]
            total_w += weights[m]
    
    fair_value = weighted_val / total_w if total_w > 0 else None
    
    return biz, models, fair_value

# ============================================================
# MAIN UI
# ============================================================
st.title("🏛️ Intelligent Valuation Deep-Dive")
ticker_input = st.text_input("Enter NSE Ticker (e.g. RELIANCE, TCS)", "ITC").upper()
ticker = f"{ticker_input}.NS"

if st.button("Analyze Stock"):
    try:
        with st.spinner(f"Requesting data for {ticker}..."):
            data = fetch_data(ticker)
            biz, model_results, fair_value = run_valuation(data)
            
            # --- Results Header ---
            c1, c2, c3 = st.columns(3)
            c1.metric("Current Price", f"₹{round(data['ltp'], 2)}")
            if fair_value:
                upside = (fair_value/data['ltp'] - 1) * 100
                c2.metric("Intelligent Fair Value", f"₹{round(fair_value, 2)}", f"{round(upside, 1)}% Upside")
            c3.metric("Business Type", biz)
            
            st.divider()
            
            # --- Individual Model Results ---
            st.subheader("Individual Model Outputs")
            
            m_cols = st.columns(3)
            for i, (name, val) in enumerate(model_results.items()):
                with m_cols[i]:
                    st.write(f"**{name}**")
                    st.write(f"₹{round(val, 2)}" if val else "Data Unavailable")

    except Exception:
        st.error("App encountered a data error.")
        st.code(traceback.format_exc())
