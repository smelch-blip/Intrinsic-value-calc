import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# =========================
# VALUATION ENGINE CLASS
# =========================
class SmartValuer:
    def __init__(self, ticker):
        self.ticker = ticker
        self.t = yf.Ticker(ticker)
        try:
            self.info = self.t.info
            self.income = self.t.income_stmt
            self.balance = self.t.balance_sheet
            self.cashflow = self.t.cashflow
        except:
            self.info = {}
        
        self.ltp = self.info.get('currentPrice') or self.info.get('previousClose')
        self.shares = self.info.get('sharesOutstanding')
        self.confidence = 0
        self.model_outputs = {}

    def classify_business(self):
        industry = str(self.info.get('industry', '')).lower()
        sector = str(self.info.get('sector', '')).lower()
        if "bank" in industry or "financial" in sector: return "FINANCIAL"
        if any(x in sector for x in ["energy", "basic materials"]): return "CYCLICAL"
        if "technology" in sector or "software" in industry: return "ASSET_LIGHT"
        return "GENERAL"

    def run_dcf(self):
        """Discounted Cash Flow (Growth Model)"""
        try:
            fcf = self.cashflow.loc['Free Cash Flow'].iloc[0]
            wacc, growth = 0.12, 0.05
            if fcf and self.shares:
                val = (fcf * 15) / self.shares # Simplified 15x FCF Multiple
                self.confidence += 35
                return val
        except: return None

    def run_epv(self):
        """Earnings Power Value (Stability Model)"""
        try:
            ebit = self.income.loc['EBIT'].iloc[0]
            if ebit and self.shares:
                val = (ebit * 0.75 / 0.12) / self.shares
                self.confidence += 30
                return val
        except: return None

    def run_pb_intrinsic(self):
        """Justified P/B (Financial Model)"""
        try:
            roe = self.info.get('returnOnEquity')
            bv = self.info.get('bookValue')
            if roe and bv:
                val = bv * (roe / 0.12)
                self.confidence += 35
                return val
        except: return None

    def get_intelligent_valuation(self):
        biz = self.classify_business()
        self.model_outputs = {
            "DCF (Growth)": self.run_dcf(),
            "EPV (Earnings Power)": self.run_epv(),
            "P/B Intrinsic": self.run_pb_intrinsic()
        }
        
        # Sector Weighting Logic
        weights = {
            "FINANCIAL": {"P/B Intrinsic": 0.8, "EPV (Earnings Power)": 0.2, "DCF (Growth)": 0.0},
            "ASSET_LIGHT": {"DCF (Growth)": 0.6, "EPV (Earnings Power)": 0.3, "P/B Intrinsic": 0.1},
            "CYCLICAL": {"EPV (Earnings Power)": 0.7, "DCF (Growth)": 0.1, "P/B Intrinsic": 0.2},
            "GENERAL": {"DCF (Growth)": 0.4, "EPV (Earnings Power)": 0.4, "P/B Intrinsic": 0.2}
        }.get(biz)

        weighted_val, total_weight = 0, 0
        for model, val in self.model_outputs.items():
            if val:
                weighted_val += val * weights[model]
                total_weight += weights[model]
        
        final_fair = weighted_val / total_weight if total_weight > 0 else None
        return final_fair, biz

# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="Valuation Deep-Dive", layout="centered")

st.title("🏛️ Intelligent Stock Valuation")
symbol = st.text_input("Enter NSE Ticker (e.g., RELIANCE, HDFCBANK)", "RELIANCE").strip().upper()

if symbol:
    ticker_sym = f"{symbol}.NS"
    with st.spinner(f"Analyzing {ticker_sym}..."):
        valuer = SmartValuer(ticker_sym)
        
        if not valuer.ltp:
            st.error("Could not fetch data. Please check the ticker symbol.")
        else:
            fair_value, biz_type = valuer.get_intelligent_valuation()
            
            # --- TOP LEVEL METRICS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Price", f"₹{valuer.ltp}")
            if fair_value:
                upside = (fair_value / valuer.ltp - 1) * 100
                col2.metric("Intelligent Fair Value", f"₹{round(fair_value, 2)}", f"{round(upside, 1)}% Upside")
            col3.metric("Confidence Score", f"{valuer.confidence}%")

            st.divider()

            # --- INDIVIDUAL MODEL BREAKDOWN ---
            st.subheader("Model Level Breakdown")
            st.caption(f"Business Classification: **{biz_type}**")
            
            m_col1, m_col2, m_col3 = st.columns(3)
            cols = [m_col1, m_col2, m_col3]
            
            for i, (model_name, value) in enumerate(valuer.model_outputs.items()):
                with cols[i]:
                    st.write(f"**{model_name}**")
                    if value:
                        st.write(f"₹{round(value, 2)}")
                        gap = (value / valuer.ltp - 1) * 100
                        st.caption(f"{'+' if gap >0 else ''}{round(gap,1)}% vs LTP")
                    else:
                        st.write("Unavailable")
                        st.caption("Missing financial data")

            st.divider()
            
            # --- FINAL VERDICT ---
            if fair_value:
                if valuer.ltp < fair_value * 0.8:
                    st.success(f"🌟 **UNDERVALUED**: {symbol} is trading at a significant discount to its intelligent fair value.")
                elif valuer.ltp > fair_value * 1.2:
                    st.error(f"⚠️ **OVERVALUED**: The market price is significantly higher than the estimated intrinsic value.")
                else:
                    st.warning(f"⚖️ **FAIRLY VALUED**: The stock is trading within a reasonable range of its fair value.")
