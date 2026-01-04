import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback

# 1. PAGE SETUP
st.set_page_config(page_title="Wealth Architect Pro", layout="wide")

# 2. DATA FETCHING (STRICT NATIVE)
@st.cache_data(ttl=600)
def fetch_data(ticker_str):
    t = yf.Ticker(ticker_str)
    try:
        info = t.info
        # TTM Data
        return {
            "ltp": info.get('currentPrice') or info.get('previousClose'),
            "info": info,
            "income": t.income_stmt,
            "cashflow": t.cashflow,
            "shares": info.get('sharesOutstanding')
        }
    except Exception as e:
        if "429" in str(e): st.error("🚀 Yahoo Rate Limit. Wait 2 mins.")
        raise e

# 3. SECTOR-WEIGHTED LOGIC
def run_valuation(data):
    info = data['info']
    income = data['income']
    cashflow = data['cashflow']
    shares = data['shares']
    ltp = data['ltp']
    sector = info.get('sector', 'Unknown')
    
    # --- MODEL 1: DCF (Normalized to Cr) ---
    try:
        fcf = cashflow.loc['Free Cash Flow'].iloc[0]
        dcf_val = (fcf * 15) / shares
        dcf_params = {
            "Input": ["Free Cash Flow", "Exit Multiple", "Shares (Cr)"],
            "Value": [f"₹{fcf/1e7:.2f} Cr", "15x", f"{shares/1e7:.2f}"],
            "Unit": ["Cr", "Ratio", "Cr"]
        }
    except: dcf_val, dcf_params = None, None

    # --- MODEL 2: EPV (Earnings Power) ---
    try:
        ebit = income.loc['EBIT'].iloc[0]
        epv_val = (ebit * 0.75 / 0.12) / shares
        epv_params = {
            "Input": ["EBIT (TTM)", "Tax Rate", "Cost of Capital"],
            "Value": [f"₹{ebit/1e7:.2f} Cr", "25%", "12%"],
            "Unit": ["Cr", "%", "%"]
        }
    except: epv_val, epv_params = None, None

    # --- MODEL 3: P/B Intrinsic (Asset Based) ---
    try:
        roe = info.get('returnOnEquity', 0.12)
        bv = info.get('bookValue', 0)
        pb_val = bv * (roe / 0.12)
        pb_params = {
            "Input": ["Return on Equity", "Book Value per Share"],
            "Value": [f"{roe*100:.2f}%", f"₹{bv:.2f}"],
            "Unit": ["%", "Price"]
        }
    except: pb_val, pb_params = None, None

    # --- INTELLIGENT WEIGHTING ENGINE ---
    # Banks rely on Assets (P/B), Tech relies on FCF (DCF)
    weights = {"DCF": 0.33, "EPV": 0.33, "P/B": 0.34} # Default
    
    if "Financial" in sector or "Bank" in sector:
        weights = {"DCF": 0.05, "EPV": 0.15, "P/B": 0.80}
    elif "Technology" in sector or "Software" in sector:
        weights = {"DCF": 0.60, "EPV": 0.30, "P/B": 0.10}

    # Calculate Weighted Average
    weighted_sum = 0
    total_weight = 0
    
    available_models = {"DCF": dcf_val, "EPV": epv_val, "P/B": pb_val}
    for m, val in available_models.items():
        if val is not None:
            weighted_sum += val * weights[m]
            total_weight += weights[m]
    
    fair_value = weighted_sum / total_weight if total_weight > 0 else ltp

    return {
        "DCF": {"value": dcf_val, "params": dcf_params, "weight": weights["DCF"]},
        "EPV": {"value": epv_val, "params": epv_params, "weight": weights["EPV"]},
        "P/B": {"value": pb_val, "params": pb_params, "weight": weights["P/B"]},
        "IFV": fair_value,
        "Sector": sector
    }

# 4. MAIN UI
def main():
    st.title("🏛️ Wealth Architect: Sector-Weighted Valuation")
    
    ticker_input = st.text_input("Enter NSE Ticker", "RELIANCE").upper().strip()
    ticker = f"{ticker_input}.NS" if not ticker_input.endswith((".NS", ".BO")) else ticker_input

    with st.sidebar:
        st.header("Risk Settings")
        mos = st.slider("Margin of Safety (%)", 5, 50, 20)
        st.info("Weighted Logic: Banks use Asset-Heavy weights, Tech uses Cash-Heavy weights.")

    if st.button("Run Intelligence Engine"):
        try:
            with st.spinner("Analyzing Financials..."):
                data = fetch_data(ticker)
                results = run_valuation(data)
                
                # --- TOP ROW: SUMMARY ---
                c1, c2, c3 = st.columns(3)
                c1.metric("Current Price", f"₹{data['ltp']:.2f}")
                
                if results['IFV']:
                    upside = (results['IFV']/data['ltp'] - 1) * 100
                    c2.metric("Intelligent Fair Value", f"₹{results['IFV']:.2f}", f"{upside:.1f}% Upside")
                    with c2: 
                        with st.popover("🛡️ Why this price?"):
                            st.write(f"**Sector Detected:** {results['Sector']}")
                            st.write("Weights applied based on business nature:")
                            st.write(f"- DCF: {results['DCF']['weight']*100}%")
                            st.write(f"- EPV: {results['EPV']['weight']*100}%")
                            st.write(f"- P/B: {results['P/B']['weight']*100}%")

                    mos_price = results['IFV'] * (1 - mos/100)
                    status = "✅ BUY" if data['ltp'] < mos_price else "❌ WAIT"
                    c3.metric(f"MoS Price ({status})", f"₹{mos_price:.2f}")

                st.divider()

                # --- DETAIL TABS ---
                st.subheader("📋 Audit Trail: Model Inputs")
                tabs = st.tabs(["DCF Analysis", "EPV Analysis", "P/B Analysis"])
                
                for i, key in enumerate(["DCF", "EPV", "P/B"]):
                    with tabs[i]:
                        if results[key]['value']:
                            col_l, col_r = st.columns([1, 2])
                            col_l.metric(f"{key} Fair Price", f"₹{results[key]['value']:.2f}")
                            col_l.write(f"**Influence:** {results[key]['weight']*100}%")
                            
                            col_r.write("**Raw Data Points (Normalized to Cr)**")
                            st.table(pd.DataFrame(results[key]['params']))
                        else:
                            st.warning(f"Insufficient data for {key} model.")

        except Exception:
            st.error("Technical Error during analysis.")
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
