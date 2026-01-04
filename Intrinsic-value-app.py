import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback

# ============================================================
# Wealth Architect Pro — Intelligent Valuation Deep-Dive (NSE)
# End-to-end Streamlit app (single-file: app.py)
# ============================================================

st.set_page_config(page_title="Intelligent Valuation Deep-Dive (NSE)", layout="wide")

# ---------- Styling ----------
st.markdown(
    """
<style>
.stApp { background-color: #ffffff; color: #0f172a; }
section[data-testid="stSidebar"] { background-color: #f8fafc !important; border-right: 1px solid #e2e8f0; }
.block-container { padding-top: 1.3rem; }
.small { color: #64748b; font-size: 0.9rem; }
.kpi { padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff; }
.kpi h4 { margin: 0 0 6px 0; font-size: 0.95rem; color: #334155; font-weight: 600; }
.kpi .val { font-size: 1.45rem; font-weight: 800; color: #0f172a; }
.kpi .sub { color: #64748b; font-size: 0.9rem; }
.tag { display:inline-block; padding: 3px 8px; border-radius: 999px; background:#eef2ff; color:#3730a3; font-size: 12px; margin-left: 6px;}
.warn { background:#fff7ed; border:1px solid #fed7aa; padding:12px; border-radius:12px; color:#9a3412;}
.ok { background:#f0fdf4; border:1px solid #bbf7d0; padding:12px; border-radius:12px; color:#166534;}
.bad { background:#fef2f2; border:1px solid #fecaca; padding:12px; border-radius:12px; color:#991b1b;}
.hr { height:1px; background:#e2e8f0; margin: 12px 0 16px 0;}
</style>
""",
    unsafe_allow_html=True,
)

# ---------- Helpers ----------
def _nse_symbol(sym: str) -> str:
    sym = (sym or "").strip().upper()
    if not sym:
        return ""
    if sym.endswith((".NS", ".BO")):
        return sym
    return f"{sym}.NS"

def _sf(x):
    try:
        if x is None:
            return None
        if isinstance(x, (np.floating, float, int)):
            return float(x)
        return float(str(x).replace(",", "").strip())
    except:
        return None

def _fmt_money_inr(x):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "NA"
    try:
        return f"₹{x:,.2f}"
    except:
        return str(x)

def _fmt_pct(x):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "NA"
    try:
        return f"{x:.1f}%"
    except:
        return str(x)

def _safe_div(a, b):
    a = _sf(a); b = _sf(b)
    if a is None or b is None or b == 0:
        return None
    return a / b

def _series_sort_newest_first(s: pd.Series) -> pd.Series:
    # yfinance statements are indexed by line items, columns by dates
    # We'll ensure the series is ordered newest -> oldest
    if s is None:
        return s
    try:
        # if index are dates, sort descending; if not, leave
        s = s.dropna()
        if s.empty:
            return s
        # series index is columns labels of statement (dates)
        # Try sorting by datetime
        idx = pd.to_datetime(s.index, errors="coerce")
        if idx.notna().any():
            s = s.iloc[np.argsort(idx)[::-1]]
        return s
    except:
        return s

def _latest(s: pd.Series):
    if s is None:
        return None
    s = _series_sort_newest_first(s).dropna()
    if s.empty:
        return None
    return _sf(s.iloc[0])

def _avg_last_n(s: pd.Series, n=3):
    if s is None:
        return None
    s = _series_sort_newest_first(s).dropna()
    if s.empty:
        return None
    return _sf(s.iloc[:n].mean())

def _winsorize(vals, lo=0.10, hi=0.90):
    """Winsorize numeric list to dampen model outliers."""
    v = [x for x in vals if x is not None and np.isfinite(x)]
    if len(v) < 2:
        return vals
    qlo = np.quantile(v, lo)
    qhi = np.quantile(v, hi)
    out = []
    for x in vals:
        if x is None or not np.isfinite(x):
            out.append(x)
        else:
            out.append(min(max(x, qlo), qhi))
    return out

# ---------- Business classification ----------
def classify_business(info: dict) -> str:
    sector = (info.get("sector") or "").lower()
    industry = (info.get("industry") or "").lower()
    longname = (info.get("longName") or info.get("shortName") or "").lower()

    fin_keywords = ["bank", "nbfc", "financial", "insurance", "lending", "capital markets"]
    cyc_keywords = ["energy", "oil", "gas", "coal", "metals", "mining", "steel", "basic materials", "materials"]
    asset_light_keywords = ["software", "it services", "technology", "internet", "services"]

    if any(k in industry for k in fin_keywords) or "financial" in sector or "bank" in longname:
        return "FINANCIAL"
    if any(k in sector for k in cyc_keywords) or any(k in industry for k in cyc_keywords):
        return "CYCLICAL"
    if any(k in sector for k in asset_light_keywords) or any(k in industry for k in asset_light_keywords):
        return "ASSET_LIGHT"
    return "GENERAL"

# ---------- Assumption defaults by business type ----------
def defaults_for_biz(biz: str):
    # These are "sane defaults" for a retail-grade intrinsic model.
    # You can override in sidebar.
    if biz == "ASSET_LIGHT":
        return {"r": 0.115, "g1": 0.10, "gT": 0.04, "years": 5, "tax": 0.25}
    if biz == "FINANCIAL":
        return {"r": 0.13, "g1": 0.07, "gT": 0.04, "years": 5, "tax": 0.25}
    if biz == "CYCLICAL":
        return {"r": 0.14, "g1": 0.06, "gT": 0.03, "years": 5, "tax": 0.25}
    return {"r": 0.13, "g1": 0.08, "gT": 0.03, "years": 5, "tax": 0.25}

# ---------- yfinance fetch ----------
@st.cache_data(ttl=30 * 60)
def fetch_yahoo_bundle(ticker: str):
    t = yf.Ticker(ticker)
    info = t.info or {}

    # price history (for fallback price and basic sanity)
    hist = t.history(period="2y", auto_adjust=False)

    # statements (often incomplete for NSE; we show NA instead of guessing)
    income = None
    balance = None
    cashflow = None
    try:
        income = t.income_stmt
    except:
        income = None
    try:
        balance = t.balance_sheet
    except:
        balance = None
    try:
        cashflow = t.cashflow
    except:
        cashflow = None

    return {"info": info, "hist": hist, "income": income, "balance": balance, "cashflow": cashflow}

# ============================================================
# Valuation Engine
# ============================================================
def compute_free_cash_flow_series(cashflow_df: pd.DataFrame):
    if cashflow_df is None or getattr(cashflow_df, "empty", True):
        return None, "cashflow_missing"
    # Prefer direct row
    if "Free Cash Flow" in cashflow_df.index:
        s = cashflow_df.loc["Free Cash Flow"]
        return s, "Free Cash Flow"
    # Fallback: CFO - Capex
    cfo_keys = ["Total Cash From Operating Activities", "Operating Cash Flow"]
    capex_keys = ["Capital Expenditures"]
    cfo = None
    capex = None
    for k in cfo_keys:
        if k in cashflow_df.index:
            cfo = cashflow_df.loc[k]
            break
    for k in capex_keys:
        if k in cashflow_df.index:
            capex = cashflow_df.loc[k]
            break
    if cfo is not None and capex is not None:
        # capex is usually negative; FCF = CFO + Capex (if Capex negative) OR CFO - abs(Capex)
        fcf = cfo + capex
        return fcf, "CFO + Capex"
    return None, "fcf_not_available"

def compute_ebit_series(income_df: pd.DataFrame):
    if income_df is None or getattr(income_df, "empty", True):
        return None, "income_missing"
    if "EBIT" in income_df.index:
        return income_df.loc["EBIT"], "EBIT"
    # Fallbacks
    for k in ["Operating Income", "Total Operating Income"]:
        if k in income_df.index:
            return income_df.loc[k], k
    return None, "ebit_not_available"

def compute_book_value_per_share(info: dict, balance_df: pd.DataFrame, shares: float):
    bv = _sf(info.get("bookValue"))
    if bv is not None and bv > 0:
        return bv, "info.bookValue"
    # fallback from balance sheet equity / shares
    if balance_df is None or getattr(balance_df, "empty", True) or shares is None or shares <= 0:
        return None, "book_missing"
    for k in ["Total Stockholder Equity", "Stockholders Equity", "Total Equity Gross Minority Interest"]:
        if k in balance_df.index:
            equity_series = balance_df.loc[k]
            equity_latest = _latest(equity_series)
            if equity_latest is not None:
                return equity_latest / shares, f"balance.{k}/shares"
    return None, "book_missing"

def dcf_two_stage_per_share(
    fcf_norm,
    shares,
    r,
    g1,
    gT,
    years,
    net_cash=None
):
    # PV of stage-1 + PV of terminal; then add net cash; divide by shares
    if fcf_norm is None or shares is None or shares <= 0:
        return None, {}
    if r <= gT:
        return None, {"error": "r_must_be_gt_gT"}

    pv_stage1 = 0.0
    fcf = float(fcf_norm)
    yearly_fcfs = []
    for t in range(1, years + 1):
        fcf *= (1.0 + g1)
        yearly_fcfs.append(fcf)
        pv_stage1 += fcf / ((1.0 + r) ** t)

    terminal = (fcf * (1.0 + gT)) / (r - gT)
    pv_terminal = terminal / ((1.0 + r) ** years)

    ev = pv_stage1 + pv_terminal
    eq = ev + (net_cash or 0.0)
    per_share = eq / shares

    details = {
        "fcf_norm": fcf_norm,
        "years": years,
        "r": r,
        "g1": g1,
        "gT": gT,
        "pv_stage1": pv_stage1,
        "terminal_value": terminal,
        "pv_terminal": pv_terminal,
        "enterprise_value": ev,
        "net_cash": net_cash,
        "equity_value": eq,
        "yearly_fcfs": yearly_fcfs,
    }
    return per_share, details

def epv_per_share(
    ebit_norm,
    shares,
    tax_rate,
    cap_rate,
    net_cash=None
):
    # EPV: NOPAT / cap_rate; add net cash; /shares
    if ebit_norm is None or shares is None or shares <= 0:
        return None, {}
    if cap_rate <= 0:
        return None, {"error": "cap_rate_must_be_positive"}

    nopat = ebit_norm * (1.0 - tax_rate)
    op_value = nopat / cap_rate
    eq_value = op_value + (net_cash or 0.0)
    per_share = eq_value / shares

    details = {
        "ebit_norm": ebit_norm,
        "tax_rate": tax_rate,
        "nopat": nopat,
        "cap_rate": cap_rate,
        "operating_value": op_value,
        "net_cash": net_cash,
        "equity_value": eq_value,
    }
    return per_share, details

def justified_pb_intrinsic_per_share(
    book_value_per_share,
    roe,
    r,
    g
):
    # Gordon/Justified P/B:
    # P/B* = (ROE - g) / (r - g)  [if ROE > g and r > g]
    if book_value_per_share is None:
        return None, {}
    if roe is None or r is None or g is None:
        return None, {}
    if r <= g:
        return None, {"error": "r_must_be_gt_g"}
    if roe <= g:
        # If ROE not above growth, justified P/B is not meaningful; return conservative floor 1x
        pb_star = 1.0
        per_share = book_value_per_share * pb_star
        return per_share, {"pb_star": pb_star, "note": "ROE<=g so P/B* floored to 1.0x"}
    pb_star = (roe - g) / (r - g)
    # Keep P/B* within reasonable bounds (prevents crazy outputs)
    pb_star = float(np.clip(pb_star, 0.5, 8.0))
    per_share = book_value_per_share * pb_star
    details = {"pb_star": pb_star, "book_value_per_share": book_value_per_share, "roe": roe, "r": r, "g": g}
    return per_share, details

def blended_fair_value(models: dict, biz: str, ltp: float):
    """
    Returns:
      - raw_weighted
      - winsorized_weighted (recommended)
      - weights_used
      - model_values_used (possibly winsorized)
    """
    # Base weights by business type (data-aware renormalization happens later)
    base = {
        "FINANCIAL": {"P/B Intrinsic": 0.75, "EPV (Earnings Power)": 0.25, "DCF (Growth)": 0.00},
        "ASSET_LIGHT": {"DCF (Growth)": 0.65, "EPV (Earnings Power)": 0.35, "P/B Intrinsic": 0.00},
        "CYCLICAL": {"EPV (Earnings Power)": 0.70, "DCF (Growth)": 0.20, "P/B Intrinsic": 0.10},
        "GENERAL": {"DCF (Growth)": 0.45, "EPV (Earnings Power)": 0.45, "P/B Intrinsic": 0.10},
    }.get(biz, {"DCF (Growth)": 0.4, "EPV (Earnings Power)": 0.4, "P/B Intrinsic": 0.2})

    # Prepare aligned arrays
    names = ["DCF (Growth)", "EPV (Earnings Power)", "P/B Intrinsic"]
    vals = [models.get(n) for n in names]
    wts = [base.get(n, 0.0) for n in names]

    # Remove missing models and renormalize
    valid = [(n, v, w) for n, v, w in zip(names, vals, wts) if v is not None and np.isfinite(v) and v > 0]
    if not valid:
        return None, None, {}, {}

    # Raw weighted average
    total_w = sum(w for _, _, w in valid)
    if total_w <= 0:
        return None, None, {}, {}
    raw = sum(v * w for _, v, w in valid) / total_w

    # Winsorize model values to reduce outliers
    v_only = [v for _, v, _ in valid]
    v_win = _winsorize(v_only, lo=0.10, hi=0.90)
    win = sum(v * w for v, (_, _, w) in zip(v_win, valid)) / total_w

    weights_used = {n: w for n, _, w in valid}
    values_used = {n: v for (n, v, _ ) in valid}
    values_wins = {n: v for (n, _old, _w), v in zip(valid, v_win)}

    # Optional sanity clamp vs LTP (don’t hide; just for final label)
    # We still show raw & wins. Final “Intelligent” uses wins but will warn if extreme.
    return raw, win, weights_used, {"raw": values_used, "winsorized": values_wins}

# ============================================================
# UI
# ============================================================
st.title("🏛️ Intelligent Valuation Deep-Dive (NSE)")
st.caption("Uses Yahoo Finance via yfinance (free). For many NSE stocks, fundamentals/statements may be missing — the app shows NA instead of guessing.")

with st.sidebar:
    st.header("Settings")
    mos = st.slider("Margin of Safety %", 5, 40, 20)
    st.markdown('<div class="small">MoS Buy = Intelligent Fair Value × (1 − MoS%)</div>', unsafe_allow_html=True)
    st.divider()
    advanced = st.toggle("Advanced overrides", value=False)
    st.markdown('<div class="small">If valuation looks odd, turn this on and tune discount/growth.</div>', unsafe_allow_html=True)

symbol_in = st.text_input("Enter Ticker (e.g., RELIANCE, HDFCBANK, TCS)", value="TCS").strip().upper()
ticker = _nse_symbol(symbol_in)

if not ticker:
    st.stop()

try:
    with st.spinner("Fetching Yahoo Finance data..."):
        bundle = fetch_yahoo_bundle(ticker)

    info = bundle["info"] or {}
    hist = bundle["hist"]
    income = bundle["income"]
    balance = bundle["balance"]
    cashflow = bundle["cashflow"]

    # Price
    ltp = _sf(info.get("currentPrice")) or _sf(info.get("previousClose"))
    if (ltp is None or ltp <= 0) and hist is not None and not hist.empty:
        ltp = _sf(hist["Close"].dropna().iloc[-1])

    shares = _sf(info.get("sharesOutstanding"))

    if ltp is None:
        st.markdown('<div class="warn">Yahoo did not return a usable price for this ticker right now. Try again in 10–20 seconds (Yahoo throttles sometimes).</div>', unsafe_allow_html=True)
        st.stop()

    biz = classify_business(info)
    dflt = defaults_for_biz(biz)

    if advanced:
        colA, colB, colC, colD = st.columns(4)
        with colA:
            r = st.number_input("Discount rate (r)", min_value=0.05, max_value=0.25, value=float(dflt["r"]), step=0.005, format="%.3f")
        with colB:
            g1 = st.number_input("Stage-1 growth (g1)", min_value=0.00, max_value=0.30, value=float(dflt["g1"]), step=0.01, format="%.3f")
        with colC:
            gT = st.number_input("Terminal growth (gT)", min_value=0.00, max_value=0.10, value=float(dflt["gT"]), step=0.005, format="%.3f")
        with colD:
            years = st.number_input("Stage-1 years", min_value=3, max_value=10, value=int(dflt["years"]), step=1)
        tax_rate = st.number_input("Tax rate (for EPV)", min_value=0.10, max_value=0.40, value=float(dflt["tax"]), step=0.01, format="%.2f")
    else:
        r, g1, gT, years, tax_rate = dflt["r"], dflt["g1"], dflt["gT"], dflt["years"], dflt["tax"]

    # Net cash
    total_debt = _sf(info.get("totalDebt"))
    total_cash = _sf(info.get("totalCash"))
    net_cash = None
    if total_debt is not None and total_cash is not None:
        net_cash = total_cash - total_debt

    # ROE from Yahoo is decimal (0.18 = 18%)
    roe_dec = _sf(info.get("returnOnEquity"))
    roe = roe_dec if roe_dec is not None else None  # keep as decimal for formulas
    # book value per share
    bvps, bv_src = compute_book_value_per_share(info, balance, shares)

    # Pull series for modeling
    fcf_series, fcf_src = compute_free_cash_flow_series(cashflow)
    ebit_series, ebit_src = compute_ebit_series(income)

    # Normalize (3y average) for stability
    fcf_norm = _avg_last_n(fcf_series, 3) if fcf_series is not None else None
    ebit_norm = _avg_last_n(ebit_series, 3) if ebit_series is not None else None

    # ---------------- Models ----------------
    model_values = {}
    model_details = {}
    model_inputs = {}

    # DCF
    dcf_val, dcf_det = dcf_two_stage_per_share(
        fcf_norm=fcf_norm,
        shares=shares,
        r=r,
        g1=g1,
        gT=gT,
        years=int(years),
        net_cash=net_cash
    )
    if dcf_val is not None and np.isfinite(dcf_val) and dcf_val > 0:
        model_values["DCF (Growth)"] = float(dcf_val)
    else:
        model_values["DCF (Growth)"] = None
    model_details["DCF (Growth)"] = dcf_det

    model_inputs["DCF (Growth)"] = pd.DataFrame([
        ["Ticker used", "input", ticker],
        ["FCF (normalized, 3y avg)", f"{fcf_src} → avg(last3)", fcf_norm],
        ["Stage-1 growth (g1)", "assumption", g1],
        ["Terminal growth (gT)", "assumption", gT],
        ["Discount rate (r)", "assumption", r],
        ["Stage-1 years", "assumption", int(years)],
        ["Net cash (cash - debt)", "info.totalCash - info.totalDebt", net_cash],
        ["Shares outstanding", "info.sharesOutstanding", shares],
    ], columns=["Parameter", "Source", "Value"])

    # EPV
    cap_rate = r  # simplest: use same r as capitalization rate
    epv_val, epv_det = epv_per_share(
        ebit_norm=ebit_norm,
        shares=shares,
        tax_rate=tax_rate,
        cap_rate=cap_rate,
        net_cash=net_cash
    )
    if epv_val is not None and np.isfinite(epv_val) and epv_val > 0:
        model_values["EPV (Earnings Power)"] = float(epv_val)
    else:
        model_values["EPV (Earnings Power)"] = None
    model_details["EPV (Earnings Power)"] = epv_det

    model_inputs["EPV (Earnings Power)"] = pd.DataFrame([
        ["Ticker used", "input", ticker],
        ["EBIT (normalized, 3y avg)", f"{ebit_src} → avg(last3)", ebit_norm],
        ["Tax rate", "assumption", tax_rate],
        ["Capitalization rate", "assumption (= r)", cap_rate],
        ["Net cash (cash - debt)", "info.totalCash - info.totalDebt", net_cash],
        ["Shares outstanding", "info.sharesOutstanding", shares],
    ], columns=["Parameter", "Source", "Value"])

    # P/B Intrinsic (Justified P/B)
    # Use g = min(gT, 6%) for stability; financials typically use a modest long-run growth
    g_pb = min(float(gT), 0.06)
    pb_val, pb_det = justified_pb_intrinsic_per_share(
        book_value_per_share=bvps,
        roe=roe,
        r=r,
        g=g_pb
    )
    if pb_val is not None and np.isfinite(pb_val) and pb_val > 0:
        model_values["P/B Intrinsic"] = float(pb_val)
    else:
        model_values["P/B Intrinsic"] = None
    model_details["P/B Intrinsic"] = pb_det

    model_inputs["P/B Intrinsic"] = pd.DataFrame([
        ["Ticker used", "input", ticker],
        ["Book value per share (BVPS)", bv_src, bvps],
        ["ROE (decimal)", "info.returnOnEquity", roe],
        ["Cost of equity (r)", "assumption", r],
        ["Sustainable growth (g)", "assumption (min(gT, 6%))", g_pb],
    ], columns=["Parameter", "Source", "Value"])

    # ---------------- Blend ----------------
    raw_blend, win_blend, weights_used, values_used = blended_fair_value(model_values, biz, ltp)

    intelligent_fair = win_blend if win_blend is not None else raw_blend
    mos_buy = intelligent_fair * (1 - mos / 100.0) if intelligent_fair is not None else None
    upside = ((intelligent_fair / ltp) - 1) * 100 if intelligent_fair is not None else None

    # ============================================================
    # TOP SUMMARY
    # ============================================================
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.1, 1.5])

    with c1:
        st.markdown('<div class="kpi"><h4>Current Price</h4><div class="val">{}</div><div class="sub">{}</div></div>'.format(
            _fmt_money_inr(ltp),
            ticker
        ), unsafe_allow_html=True)

    with c2:
        if intelligent_fair is None:
            st.markdown('<div class="kpi"><h4>Intelligent Fair Value</h4><div class="val">NA</div><div class="sub">Insufficient model data</div></div>', unsafe_allow_html=True)
        else:
            label = "Upside" if upside is not None and upside >= 0 else "Downside"
            st.markdown('<div class="kpi"><h4>Intelligent Fair Value <span class="tag">winsorized blend</span></h4><div class="val">{}</div><div class="sub">{} {}</div></div>'.format(
                _fmt_money_inr(intelligent_fair),
                _fmt_pct(abs(upside)),
                label
            ), unsafe_allow_html=True)

    with c3:
        st.markdown('<div class="kpi"><h4>Classification</h4><div class="val">{}</div><div class="sub">sector-aware routing</div></div>'.format(
            biz
        ), unsafe_allow_html=True)

    with c4:
        if mos_buy is None:
            st.markdown('<div class="kpi"><h4>MoS Buy ({}%)</h4><div class="val">NA</div><div class="sub">Needs fair value</div></div>'.format(mos), unsafe_allow_html=True)
        else:
            st.markdown('<div class="kpi"><h4>MoS Buy ({}%)</h4><div class="val">{}</div><div class="sub">fair × (1 − MoS)</div></div>'.format(
                mos, _fmt_money_inr(mos_buy)
            ), unsafe_allow_html=True)

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # ============================================================
    # MODEL CARDS + INFO POPOVERS
    # ============================================================
    st.subheader("Model Level Breakdown")

    mcols = st.columns(3)
    model_order = ["DCF (Growth)", "EPV (Earnings Power)", "P/B Intrinsic"]

    formula_text = {
        "DCF (Growth)": (
            "2-stage DCF (per share):\n\n"
            "1) FCFₙ = average of last 3 years (FCF)\n"
            "2) Forecast years 1..N: FCFₜ = FCFₜ₋₁ × (1+g1)\n"
            "3) PV(stage1) = Σ FCFₜ / (1+r)^t\n"
            "4) Terminal = FCF_N × (1+gT) / (r−gT)\n"
            "5) PV(terminal) = Terminal / (1+r)^N\n"
            "6) Equity Value = PV(stage1)+PV(terminal) + NetCash\n"
            "7) Per-share = Equity Value / Shares\n"
        ),
        "EPV (Earnings Power)": (
            "EPV (per share):\n\n"
            "1) EBITₙ = average of last 3 years (EBIT)\n"
            "2) NOPAT = EBITₙ × (1 − tax)\n"
            "3) Operating Value = NOPAT / cap_rate\n"
            "4) Equity Value = Operating Value + NetCash\n"
            "5) Per-share = Equity Value / Shares\n"
        ),
        "P/B Intrinsic": (
            "Justified P/B intrinsic (per share):\n\n"
            "1) P/B* = (ROE − g) / (r − g)\n"
            "2) Clamp P/B* to [0.5x, 8x] for stability\n"
            "3) Intrinsic Price = BVPS × P/B*\n"
            "Note: If ROE ≤ g, model floors to 1.0× BVPS.\n"
        ),
        "Blend": (
            "Intelligent Fair Value = winsorized, sector-routed weighted blend.\n\n"
            "Steps:\n"
            "1) Pick weights by business type (FINANCIAL / ASSET_LIGHT / CYCLICAL / GENERAL)\n"
            "2) Ignore models with missing data\n"
            "3) Winsorize model outputs (10th–90th percentile) to reduce outlier skew\n"
            "4) Weighted average of winsorized model outputs\n"
            "5) MoS Buy = Fair × (1 − MoS%)\n"
        )
    }

    for i, name in enumerate(model_order):
        val = model_values.get(name)
        with mcols[i]:
            st.markdown(f"**{name}**")
            if val is None:
                st.markdown('<div class="warn">NA (Yahoo data missing)</div>', unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='kpi'><div class='val'>{_fmt_money_inr(val)}</div><div class='sub'>per share</div></div>", unsafe_allow_html=True)

            with st.popover("ℹ️ Calculation used"):
                st.text(formula_text[name])

    # Blend details row
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.markdown("**Intelligent Fair Value (Blend)**")
    bcols = st.columns([1.2, 1.2, 1.2, 2.2])
    with bcols[0]:
        st.metric("Blend (raw)", _fmt_money_inr(raw_blend) if raw_blend is not None else "NA")
    with bcols[1]:
        st.metric("Blend (winsorized)", _fmt_money_inr(win_blend) if win_blend is not None else "NA")
    with bcols[2]:
        st.metric("MoS Buy", _fmt_money_inr(mos_buy) if mos_buy is not None else "NA")
    with bcols[3]:
        with st.popover("ℹ️ How the blend is calculated"):
            st.text(formula_text["Blend"])
            st.write("**Weights used (after removing missing models):**")
            st.json(weights_used if weights_used else {})
            st.write("**Model values used (raw):**")
            st.json(values_used.get("raw", {}) if values_used else {})
            st.write("**Model values used (winsorized):**")
            st.json(values_used.get("winsorized", {}) if values_used else {})

    # Warn if fair value looks extreme
    if intelligent_fair is not None and (intelligent_fair < 0.4 * ltp or intelligent_fair > 2.5 * ltp):
        st.markdown(
            "<div class='warn'>Fair value looks extreme vs current price. This can happen when Yahoo statements are incomplete or when one model dominates. Check inputs in the tabs below and consider adjusting assumptions.</div>",
            unsafe_allow_html=True
        )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # ============================================================
    # INPUTS TABLES PER MODEL + CALC DETAILS
    # ============================================================
    st.subheader("Inputs & Calculation Trace (tabular)")

    tabs = st.tabs(["Raw Yahoo Snapshot", "DCF (Growth)", "EPV (Earnings Power)", "P/B Intrinsic", "Blend"])

    # Raw snapshot tab
    with tabs[0]:
        raw_rows = [
            ["Ticker used", ticker],
            ["Company", info.get("longName") or info.get("shortName") or "NA"],
            ["Sector", info.get("sector") or "NA"],
            ["Industry", info.get("industry") or "NA"],
            ["Current Price", ltp],
            ["Shares Outstanding", shares],
            ["returnOnEquity (decimal)", roe],
            ["Book Value / Share", bvps],
            ["Book Value Source", bv_src],
            ["Total Cash", total_cash],
            ["Total Debt", total_debt],
            ["Net Cash (cash - debt)", net_cash],
            ["FCF Source", fcf_src],
            ["EBIT Source", ebit_src],
        ]
        raw_df = pd.DataFrame(raw_rows, columns=["Yahoo Field / Derived", "Value"])
        st.dataframe(raw_df, use_container_width=True, hide_index=True)

        st.markdown("**Statement coverage note:** For many NSE stocks, Yahoo may not provide full cashflow/income/balance statements. This app shows NA rather than fabricating values.")

    # Model tabs
    for tab_name in model_order:
        idx = {"DCF (Growth)": 1, "EPV (Earnings Power)": 2, "P/B Intrinsic": 3}[tab_name]
        with tabs[idx]:
            st.markdown("**Inputs used (from Yahoo + assumptions):**")
            df_in = model_inputs[tab_name].copy()
            # pretty formatting
            def _fmt_val(v):
                if isinstance(v, (int, float, np.floating)):
                    if abs(v) < 1 and "growth" in str(v).lower():
                        return v
                    return v
                return v
            df_in["Value"] = df_in["Value"].apply(_fmt_val)
            st.dataframe(df_in, use_container_width=True, hide_index=True)

            with st.popover("ℹ️ Calculation used"):
                st.text(formula_text[tab_name])

            st.markdown("**Calculation trace (intermediate values):**")
            det = model_details.get(tab_name, {}) or {}
            # Make a readable table
            if not det:
                st.markdown("<div class='warn'>No trace available (likely missing Yahoo statement data).</div>", unsafe_allow_html=True)
            else:
                trace_items = []
                for k, v in det.items():
                    if k == "yearly_fcfs":
                        continue
                    trace_items.append([k, v])
                trace_df = pd.DataFrame(trace_items, columns=["Intermediate", "Value"])
                st.dataframe(trace_df, use_container_width=True, hide_index=True)

                if tab_name == "DCF (Growth)" and "yearly_fcfs" in det:
                    y_fcfs = det["yearly_fcfs"]
                    fc_df = pd.DataFrame({"Year": list(range(1, len(y_fcfs)+1)), "Forecast FCF": y_fcfs})
                    st.markdown("**DCF stage-1 forecast cashflows:**")
                    st.dataframe(fc_df, use_container_width=True, hide_index=True)

    # Blend tab
    with tabs[4]:
        st.markdown("**Blend inputs (models + weights):**")
        blend_rows = []
        for n in model_order:
            blend_rows.append([n, model_values.get(n), weights_used.get(n) if weights_used else None])
        blend_df = pd.DataFrame(blend_rows, columns=["Model", "Model Value (₹/share)", "Weight Used"])
        st.dataframe(blend_df, use_container_width=True, hide_index=True)

        st.markdown("**Blend outputs:**")
        out_df = pd.DataFrame([
            ["Blend (raw)", raw_blend],
            ["Blend (winsorized)", win_blend],
            ["Intelligent Fair Value (used)", intelligent_fair],
            [f"MoS Buy ({mos}%)", mos_buy],
            ["Current Price", ltp],
            ["Upside/Downside (%)", upside],
        ], columns=["Output", "Value"])
        st.dataframe(out_df, use_container_width=True, hide_index=True)

        with st.popover("ℹ️ Calculation used"):
            st.text(formula_text["Blend"])

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.caption("If valuations are NA: Yahoo likely didn’t provide statements (especially cashflow/EBIT) for this NSE ticker. To make this truly reliable for NSE, you’ll need an NSE/paid fundamentals source (or Screener/Trendlyne/API).")

except Exception:
    st.error("A critical error occurred.")
    st.code(traceback.format_exc())
