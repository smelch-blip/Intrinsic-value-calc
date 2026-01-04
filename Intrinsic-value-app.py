import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback

# 1. PAGE SETUP
st.set_page_config(page_title="Wealth Architect Pro", layout="wide")

# Styling
st.markdown("""
<style>
    .stMetric { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; }
    .stApp { background-color: #f8fafc; }
    .formula-box { background-color: #f1f5f9; padding: 10px; border-radius: 5px; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# 2. DATA FETCHING (NATIVE YFINANCE - NO SESSION)
@st.cache_data(ttl=600)
def fetch_data(ticker_str):
    # CRITICAL: No session=session here. Let yfinance handle it.
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
        if "429" in str(e): st.error("🚀 Rate limit hit. Wait 1 min.")
        raise e

# 3. VALUATION CALCULATIONS & INPUT TRACKING
def run_valuation(data):
    info = data['info']
    income = data['income']
    cashflow = data['cashflow']
    shares = data['shares']
    ltp = data['ltp']
    
    # --- MODEL 1: DCF (Growth) ---
    try:
        fcf = cashflow.loc['Free Cash Flow'].iloc[0]
        dcf_val = (fcf * 15) / shares
        dcf_params = {
            "Parameter": ["Latest Free Cash Flow", "Exit Multiple", "Shares Outstanding"],
            "Value": [f"₹{fcf:,.0f}", "15x", f"{shares:,.0f}"],
            "Source": ["Cashflow Statement", "Assumed Standard", "Company Info"]
        }
    except: dcf_val, dcf_params = None, None

    # --- MODEL 2: EPV (Earnings Power) ---
    try:
        ebit = income.loc['EBIT'].iloc[0]
        tax_rate = 0.25
        wacc = 0.12
        epv_val = (ebit * (1 - tax_rate) / wacc) / shares
        epv_params = {
            "Parameter": ["EBIT", "Tax Rate", "WACC (Discount)", "Shares Outstanding"],
            "Value": [f"₹{ebit:,.0f}", f"{tax_rate*100}%", f"{wacc*100}%", f"{shares:,.0f}"],
            "Source": ["Income Statement", "Standard Corporate", "Equity Risk Premium", "Company Info"]
        }
    except: epv_val, epv_params = None, None

    # --- MODEL 3: P/B Intrinsic ---
    try:
        roe = info.get('returnOnEquity', 0.12)
        bv = info.get('bookValue', 0)
        ke = 0.12 # Cost of Equity
        pb_val = bv * (roe / ke)
        pb_params = {
            "Parameter": ["Return on Equity (ROE)", "Book Value Per Share", "Cost of Equity (Ke)"],
            "Value": [f"{roe*100:.2f}%", f"₹{bv:.2f}", f"{ke*100}%"],
            "Source": ["Company Info", "Balance Sheet", "Risk-Free Rate + Beta"]
        }
    except: pb_val, pb_params = None, None

    # --- INTELLIGENT FAIR VALUE ---
    vals = [v for v in [dcf_val, epv_val, pb_val] if v is not None]
    fair_value = sum(vals) / len(vals) if vals else ltp
    
    return {
        "DCF": {"value": dcf_val, "params": dcf_params, "formula": "FV = (FCF * 15) / Shares"},
        "EPV": {"value": epv_val, "params": epv_params, "formula": "FV = [EBIT * (1 - Tax) / WACC] / Shares"},
        "P/B": {"value": pb_val, "params": pb_params, "formula": "FV = Book Value * (ROE / Ke)"},
        "IFV": fair_value
    }

# 4. MAIN UI
def main():
    st.title("🏛️ Intelligent Valuation Deep-Dive")
    ticker_input = st.text_input("Enter NSE Ticker", "TCS").upper().strip()
    ticker = f"{ticker_input}.NS" if not ticker_input.endswith((".NS", ".BO")) else ticker_input

    with st.sidebar:
        mos = st.slider("Margin of Safety (%)", 5, 50, 20)
        st.write("---")
        st.info("Calculations use Yahoo Finance TTM data.")

    if st.button("Analyze Stock"):
        try:
            with st.spinner(f"Retrieving data for {ticker}..."):
                data = fetch_data(ticker)
                results = run_valuation(data)
                
                # --- TOP METRICS ---
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Current Price", f"₹{data['ltp']:.2f}")
                
                if results['IFV']:
                    upside = (results['IFV']/data['ltp'] - 1) * 100
                    c2.metric("Intelligent Fair Value", f"₹{results['IFV']:.2f}", f"{upside:.1f}% Upside")
                    with c2: 
                        with st.popover("ℹ️ IFV Logic"):
                            st.write("**Intelligent Fair Value Calculation:**")
                            st.latex(r"IFV = \frac{DCF + EPV + PB}{n}")
                            st.caption("Averaging multiple models reduces individual model bias.")

                    mos_price = results['IFV'] * (1 - mos/100)
                    c3.metric(f"MoS Buy Price ({mos}%)", f"₹{mos_price:.2f}")

                st.divider()

                # --- MODEL BREAKDOWN ---
                st.subheader("📊 Model Breakdown & Input Trace")
                
                tabs = st.tabs(["DCF (Growth)", "EPV (Earnings)", "P/B Intrinsic"])
                
                model_keys = ["DCF", "EPV", "P/B"]
                for i, tab in enumerate(tabs):
                    key = model_keys[i]
                    with tab:
                        col_a, col_b = st.columns([1, 2])
                        with col_a:
                            st.metric(f"{key} Value", f"₹{results[key]['value']:.2f}" if results[key]['value'] else "N/A")
                            with st.popover("ℹ️ View Formula"):
                                st.write(f"**{key} Formula:**")
                                st.code(results[key]['formula'])
                        
                        with col_b:
                            if results[key]['params']:
                                st.write("**Input Parameters Used:**")
                                st.table(pd.DataFrame(results[key]['params']))
                            else:
                                st.warning("Insufficient data from Yahoo to populate parameters.")

        except Exception:
            st.error("Error detected. Reboot app if code was recently updated.")
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
