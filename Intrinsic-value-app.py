import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback

# 1. DATA FETCHING (NATIVE)
@st.cache_data(ttl=600)
def fetch_data(ticker_str):
    t = yf.Ticker(ticker_str)
    try:
        info = t.info
        return {
            "ltp": info.get('currentPrice') or info.get('previousClose'),
            "info": info,
            "income": t.income_stmt,
            "cashflow": t.cashflow,
            "shares": info.get('sharesOutstanding')
        }
    except Exception as e:
        if "429" in str(e): st.error("🚀 Rate limit. Wait 2 min.")
        raise e

# 2. SECTOR-BASED VALUATION ENGINE
def run_valuation(data):
    info, income, cashflow = data['info'], data['income'], data['cashflow']
    shares = data['shares']
    ltp = data['ltp']
    sector = info.get('sector', 'Unknown')
    
    # --- MODEL 1: DCF (5-Year + Terminal Value) ---
    # Logic: 5 years of cash + a 'Terminal Value' (selling the business in yr 5)
    try:
        fcf = cashflow.loc['Free Cash Flow'].iloc[0]
        pv_factor = 3.7908 # Your 5-year 10% factor
        terminal_multiple = 10 # Industry standard 'exit' multiple
        
        pv_5yr = fcf * pv_factor
        tv_discounted = (fcf * terminal_multiple) / (1.10**5) # Discounting the sale price back to today
        
        dcf_val = (pv_5yr + tv_discounted) / shares
        dcf_params = {
            "5-Yr Cash (Cr)": f"₹{pv_5yr/1e7:.0f}",
            "Terminal Value (Cr)": f"₹{tv_discounted/1e7:.0f}",
            "Total PV": f"₹{(pv_5yr + tv_discounted)/1e7:.0f}"
        }
    except: dcf_val, dcf_params = None, None

    # --- MODEL 2: EPV (Earnings Power Value) ---
    try:
        ebit = income.loc['EBIT'].iloc[0]
        epv_val = (ebit * 0.75 / 0.12) / shares # 25% tax, 12% WACC
        epv_params = {"EBIT (Cr)": f"₹{ebit/1e7:.0f}", "WACC": "12%", "Tax": "25%"}
    except: epv_val, epv_params = None, None

    # --- MODEL 3: P/B Intrinsic (Benjamin Graham Style) ---
    try:
        roe = info.get('returnOnEquity', 0.12)
        bv = info.get('bookValue', 0)
        pb_val = bv * (roe / 0.12)
        pb_params = {"ROE": f"{roe*100:.1f}%", "Book Value": f"₹{bv:.0f}", "Ke": "12%"}
    except: pb_val, pb_params = None, None

    # --- INTELLIGENT WEIGHTING ENGINE ---
    weights = {"DCF": 0.33, "EPV": 0.33, "P/B": 0.34} # Default
    if "Financial" in sector: weights = {"DCF": 0.10, "EPV": 0.20, "P/B": 0.70}
    elif "Technology" in sector: weights = {"DCF": 0.60, "EPV": 0.30, "P/B": 0.10}
    elif "Consumer" in sector: weights = {"DCF": 0.40, "EPV": 0.40, "P/B": 0.20}

    # Final Calculation
    models = {"DCF": dcf_val, "EPV": epv_val, "P/B": pb_val}
    weighted_sum = sum(val * weights[m] for m, val in models.items() if val)
    total_w = sum(weights[m] for m, val in models.items() if val)
    
    ifv = weighted_sum / total_w if total_w > 0 else ltp

    return {
        "IFV": ifv, "Sector": sector, "Weights": weights,
        "Models": {
            "DCF": {"val": dcf_val, "p": dcf_params, "f": "5-Yr Cash + Terminal Multiplier"},
            "EPV": {"val": epv_val, "p": epv_params, "f": "EBIT * (1-T) / WACC"},
            "P/B": {"val": pb_val, "p": pb_params, "f": "Book Value * (ROE / Cost of Equity)"}
        }
    }

# 3. UI RENDERING
def main():
    st.title("🏛️ Intelligent Sector-Weighted Valuation")
    ticker = st.text_input("Enter NSE Ticker", "RELIANCE").upper().strip()
    ticker = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker

    if st.button("Deep-Dive Valuation"):
        data = fetch_data(ticker)
        res = run_valuation(data)
        
        # Dashboard
        c1, c2, c3 = st.columns(3)
        c1.metric("Current Price", f"₹{data['ltp']:.2f}")
        c2.metric("Intelligent Fair Value", f"₹{res['IFV']:.2f}")
        c3.metric("Industry", res['Sector'])
        
        st.divider()
        
        # Tabs for Audit Trail
        tabs = st.tabs(["DCF", "EPV", "P/B", "Weights Engine"])
        
        for i, m in enumerate(["DCF", "EPV", "P/B"]):
            with tabs[i]:
                st.subheader(f"{m} Calculation Details")
                st.write(f"**Formula:** {res['Models'][m]['f']}")
                st.table(pd.DataFrame([res['Models'][m]['p']]))
                st.metric("Model Specific Value", f"₹{res['Models'][m]['val']:.2f}")
        
        with tabs[3]:
            st.write("### How the IFV was weighted:")
            st.json(res['Weights'])

if __name__ == "__main__":
    main()
