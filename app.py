import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="System Check")
st.title("🔍 System Diagnostic")

# Step 1: Check if libraries are loaded
st.write("✅ Libraries loaded successfully.")

ticker_input = st.text_input("Enter Ticker (e.g. ITC.NS)", "ITC.NS")

if st.button("Run Diagnostic"):
    try:
        # Step 2: Test Network & yfinance
        st.write(f"Attempting to fetch data for: {ticker_input}...")
        data = yf.Ticker(ticker_input)
        
        # Step 3: Test Price Fetch (The most common fail point)
        price = data.fast_info.get('last_price') or data.info.get('currentPrice')
        
        if price:
            st.success(f"Connection Successful! Current Price: ₹{price}")
            
            # Step 4: Test Financial Statements
            st.write("Testing Financial Statements fetch...")
            df = data.income_stmt
            if df is not None and not df.empty:
                st.success("Financial Statements fetched!")
                st.dataframe(df.head())
            else:
                st.warning("Price works, but Financial Statements are empty (Yahoo limit).")
        else:
            st.error("Could not fetch price. Yahoo might be blocking your IP.")
            
    except Exception as e:
        st.error(f"CRITICAL ERROR: {str(e)}")
        st.exception(e)
