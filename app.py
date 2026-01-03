import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback

# =========================
# VALUATION ENGINE
# =========================
class SmartValuer:
    def __init__(self, ticker):
        self.ticker = ticker if ticker.endswith((".NS", ".BO")) else f"{ticker}.NS"
        try:
            self.t = yf.Ticker(self.ticker)
            # Use a fast fetch for basic info
            self.info = self.t.info
            self.ltp = self.info.get('currentPrice') or self.info.get('previousClose')
            self.shares = self.info.get('sharesOutstanding')
            
            # These can be slow/empty for some NSE stocks
            self.income = self.t.income_stmt
            self.balance = self.t.balance_sheet
            self.cashflow = self.t.cashflow
        except Exception as e:
            st.error(f"Data Fetch Error: {e}")
            self.info = {}
            self.ltp = None

    def classify_business(self):
        industry = str(self.info.get('industry', '')).lower()
        sector = str(self.info.get('sector', '')).lower()
        if "bank" in industry or "financial" in sector: return "FINANCIAL"
        if any(x in sector for x in ["energy", "basic materials", "metal"]): return "CYCLICAL"
        if "technology" in sector or "software" in industry: return "ASSET_LIGHT"
        return "GENERAL"

    def run_models(self):
        models = {}
        # 1. DCF (Growth)
        try:
            if self.cashflow is not None and 'Free Cash Flow' in self.cashflow.index:
                fcf = self.cashflow.loc['Free Cash Flow'].iloc[0]
                if fcf and self.shares:
                    models["DCF (Growth)"] = (fcf * 18) / self.shares
            else: models["DCF (Growth)"] = None
        except: models["DCF (Growth)"] = None

        # 2. EPV (Earnings Power)
        try:
            if self.income is not None and 'EBIT' in self.income.index:
                ebit = self.income.loc['EBIT'].iloc[0]
                if ebit and self.shares:
                    models["EPV (Earnings Power)"] = (ebit * 0.75 / 0.12) / self.shares
            else: models["EPV (Earnings Power)"] = None
        except: models["EPV (Earnings Power)"] = None

        # 3. P/B Intrinsic (Asset Based)
        try:
            roe = self.info.get('returnOnEquity')
            bv = self.info.get('bookValue')
            if roe and bv:
                models["P/B Intrinsic"] = bv * (roe / 0.12)
            else: models["P/B Intrinsic"] = None
        except: models["P/B Intrinsic"] = None

        return models

    def get_blend(self, models, biz):
        weights = {
            "FINANCIAL": {"P/B Intrinsic": 0.8, "EPV (Earnings Power)": 0.2, "DCF (Growth)": 0.0},
            "ASSET_LIGHT": {"DCF (Growth)": 0.6, "EPV (Earnings Power)": 0.3, "P/B Intrinsic": 0.1},
            "CYCLICAL": {"EPV (Earnings Power)": 0.7, "DCF (Growth)": 0.1, "P/B Intrinsic": 0.2},
            "GENERAL": {"DCF (Growth)": 0.4, "EPV (Earnings Power)": 0.4, "P/B Intrinsic": 0.2}
        }.get(biz)

        weighted_val, total_weight = 0, 0
        for m, val in models.items():
            if val is not None:
                weighted_val += val * weights[m]
                total_weight += weights[m]
        
        return weighted_val / total_weight if total_weight > 0 else None

# =========================
# UI LAYOUT
# =========================
def main():
    st.set_page_config(page_title="Valuation Router", layout="wide")
    st.title("🏛️ Intelligent Valuation Deep-Dive")

    symbol = st.text_input("Enter Ticker (e.g., RELIANCE, HDFCBANK, TCS)", "RELIANCE").strip().upper()

    if symbol:
        try:
            with st.spinner("Analyzing business type and data availability..."):
                sv = SmartValuer(symbol)
                
                if not sv.ltp:
                    st.warning("Data error: Yahoo Finance didn't return a price. This is common if you ping them too fast. Wait 5s and try again.")
                else:
                    biz = sv.classify_business()
                    models = sv.run_models()
                    fair = sv.get_blend(models, biz)

                    # Top Metrics
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Current Price", f"₹{sv.ltp}")
                    if fair:
                        upside = (fair/sv.ltp - 1) * 100
                        c2.metric("Intelligent Fair Value", f"₹{round(fair, 2)}", f"{round(upside, 1)}% {'Upside' if upside > 0 else 'Downside'}")
                    c3.metric("Classification", biz)

                    st.divider()

                    # Model Breakdown Table
                    st.subheader("Model Level Breakdown")
                    
                    m_cols = st.columns(len(models))
                    for i, (name, val
