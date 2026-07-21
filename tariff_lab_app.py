import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 1. PAGE CONFIGURATION & METADATA
# ==========================================
st.set_page_config(page_title="Post-MHHS Tariff Lab", layout="wide", page_icon="⚡")
st.title("⚡ Post-MHHS Tariff Lab")
st.markdown("Simulate Time of Use (ToU) market shifts, build custom tariffs, and quantify winners, losers, and supplier margin risks.")

# ==========================================
# 2. SYNTHETIC WHOLESALE & COHORT ENGINE
# ==========================================
@st.cache_data
def generate_simulation_data(base_ws_p=9.85, base_duos_p=2.45, base_policy_p=3.50, tdcv=2900.0):
    """
    Generates 17,520 half-hourly periods with 4 distinct cohort load shapes
    and mathematically sound wholesale/network cost curves.
    """
    dates = pd.date_range(start="2026-01-01", end="2026-12-31 23:30:00", freq="30min")
    df = pd.DataFrame({"datetime": dates})
    df["date"] = df["datetime"].dt.date
    df["month"] = df["datetime"].dt.month
    df["day_of_week"] = df["datetime"].dt.dayofweek
    df["period"] = df["datetime"].dt.hour * 2 + df["datetime"].dt.minute // 30 + 1
    t_hours = (df["period"] - 1) * 0.5
    
    # Modulators
    day_of_year = df["datetime"].dt.dayofyear
    seasonal_mult = 1.0 + 0.45 * np.cos(2 * np.pi * (day_of_year - 1) / 365)
    is_weekend = df["day_of_week"] >= 5
    weekend_mult = np.where(is_weekend, 0.92, 1.0)
    
    # --- COHORT LOAD SHAPES ---
    # 1. Inflexible Family (High evening peak, low flex)
    c1_base = (0.12 + 0.5 * np.exp(-((t_hours - 8.0)**2)/(2*1.2**2)) + 1.4 * np.exp(-((t_hours - 18.5)**2)/(2*1.8**2))) * seasonal_mult * weekend_mult
    # 2. EV / Smart Home (Heavy overnight spike + evening load)
    c2_base = (0.10 + 2.5 * np.where((t_hours >= 0.5) & (t_hours <= 5.0), 1.0, 0.0) + 0.8 * np.exp(-((t_hours - 18.5)**2)/(2*2.0**2))) * seasonal_mult * weekend_mult
    # 3. Economy 7 / Off-Grid (Classic 7-hour overnight block)
    c3_base = (0.08 + 2.2 * np.where((t_hours >= 0.5) & (t_hours <= 7.5), 1.0, 0.0) + 0.3 * np.exp(-((t_hours - 18.5)**2)/(2*2.0**2))) * seasonal_mult * weekend_mult
    # 4. Low-Income / Flat Profile (Steady baseload, minimal peak)
    c4_base = (0.25 + 0.2 * np.exp(-((t_hours - 12.0)**2)/(2*4.0**2)) + 0.3 * np.exp(-((t_hours - 18.0)**2)/(2*2.0**2))) * seasonal_mult * weekend_mult

    # Normalize all cohorts to strictly conserve Target TDCV
    for name, base_vec in [("Cohort_1", c1_base), ("Cohort_2", c2_base), ("Cohort_3", c3_base), ("Cohort_4", c4_base)]:
        df[f"{name}_kWh"] = (base_vec / base_vec.sum()) * tdcv

    # --- MARKET COST SHAPING ---
    is_weekday = df['day_of_week'] < 5
    # Wholesale: Evening peak premium, overnight discount
    ws_mult = np.where((t_hours >= 16.0) & (t_hours < 19.5), 2.2, np.where((t_hours >= 23.0) | (t_hours < 7.0), 0.4, 0.9))
    df['Wholesale_Cost_Raw'] = base_ws_p * ws_mult * (1.0 + 0.3 * np.cos(2 * np.pi * (day_of_year - 1) / 365))
    
    # DUoS: RAG Network Congestion Bands
    red_band = is_weekday & (t_hours >= 16.0) & (t_hours < 19.0)
    amber_band = is_weekday & (((t_hours >= 7.5) & (t_hours < 16.0)) | ((t_hours >= 19.0) & (t_hours < 22.0)))
    df['DUoS_Cost_Raw'] = np.where(red_band, base_duos_p * 8.0, np.where(amber_band, base_duos_p * 1.5, base_duos_p * 0.1))

    # Align weighted averages back to the Ofgem Flat Cap using Cohort 1 as the reference SVT profile
    ref_kwh = df["Cohort_1_kWh"]
    ws_avg = (df['Wholesale_Cost_Raw'] * ref_kwh).sum() / ref_kwh.sum()
    duos_avg = (df['DUoS_Cost_Raw'] * ref_kwh).sum() / ref_kwh.sum()
    
    df['Wholesale_Cost_p'] = df['Wholesale_Cost_Raw'] * (base_ws_p / ws_avg)
    df['DUoS_Cost_p'] = df['DUoS_Cost_Raw'] * (base_duos_p / duos_avg)
    
    # Generate the perfectly cost-reflective ToU benchmark
    df["Reference_ToU_Rate_p"] = df["Wholesale_Cost_p"] + df["DUoS_Cost_p"] + base_policy_p

    return df

# ==========================================
# 3. SIDEBAR PARAMETERS & BUILDER
# ==========================================
st.sidebar.header("1. Baseline Assumptions")
st.sidebar.markdown("Baseline Ofgem standard flat allowances.")
base_ws = st.sidebar.number_input("Wholesale Allowance (p/kWh)", value=9.85, step=0.1)
base_duos = st.sidebar.number_input("Network / DUoS Allowance (p/kWh)", value=2.45, step=0.1)
base_policy = st.sidebar.number_input("Policy & Other Allowances (p/kWh)", value=3.50, step=0.1)
base_sc = st.sidebar.number_input("Standing Charge (£/yr)", value=180.0, step=5.0)

st.sidebar.divider()
st.sidebar.header("2. Custom Tariff Builder")
st.sidebar.markdown("Design a consumer ToU tariff to compete with the market.")
ct_peak = st.sidebar.number_input("Peak Rate (16:00–19:30) p/kWh", value=28.5, step=0.5)
ct_shoulder = st.sidebar.number_input("Shoulder Rate p/kWh", value=18.0, step=0.5)
ct_offpeak = st.sidebar.number_input("Off-Peak Rate (23:00–07:00) p/kWh", value=8.5, step=0.5)
ct_sc = st.sidebar.number_input("Custom Standing Charge (£/yr)", value=180.0, step=5.0)

# Generate Data
df = generate_simulation_data(base_ws, base_duos, base_policy).copy()
flat_cap_rate = base_ws + base_duos + base_policy

# Apply Custom Tariff Logic
t_hours = (df["period"] - 1) * 0.5
custom_peak_mask = (t_hours >= 16.0) & (t_hours < 19.5)
custom_offpeak_mask = (t_hours >= 23.0) | (t_hours < 7.0)
df["Custom_Tariff_Rate_p"] = np.where(custom_peak_mask, ct_peak, np.where(custom_offpeak_mask, ct_offpeak, ct_shoulder))

# ==========================================
# 4. TABBED INTERFACE
# ==========================================
tab1, tab2, tab3 = st.tabs(["🎮 Tariff Simulator", "👥 Portfolio Impact", "📖 Lab Guide"])

# ------------------------------------------
# TAB 1: TARIFF SIMULATOR
# ------------------------------------------
with tab1:
    st.markdown("### Simulate Individual Customer Impact")
    cohort_dict = {
        "Cohort 1: Inflexible Family (High Evening Peak)": "Cohort_1",
        "Cohort 2: EV / Smart Home Owner (Overnight Spike)": "Cohort_2",
        "Cohort 3: Economy 7 / Off-Grid (Overnight Storage)": "Cohort_3",
        "Cohort 4: Low-Income / Flat Profile (Baseload)": "Cohort_4"
    }
    selected_cohort_label = st.selectbox("Select Customer Archetype:", list(cohort_dict.keys()))
    c_col = cohort_dict[selected_cohort_label]
    
    # Bills Calculation
    vol = df[f"{c_col}_kWh"]
    bill_flat = ((vol * flat_cap_rate).sum() / 100) + base_sc
    bill_ref_tou = ((vol * df["Reference_ToU_Rate_p"]).sum() / 100) + base_sc
    bill_custom = ((vol * df["Custom_Tariff_Rate_p"]).sum() / 100) + ct_sc
    
    st.divider()
    b1, b2, b3 = st.columns(3)
    b1.metric("1. Baseline Flat Cap Bill", f"£{bill_flat:,.2f}")
    b2.metric("2. Reference ToU Bill (Market Cost)", f"£{bill_ref_tou:,.2f}", delta=f"£{bill_ref_tou - bill_flat:,.2f} vs Flat", delta_color="inverse")
    b3.metric("3. Your Custom Tariff Bill", f"£{bill_custom:,.2f}", delta=f"£{bill_custom - bill_flat:,.2f} vs Flat", delta_color="inverse")
    
    st.markdown("### 🕒 Average 24-Hour Load vs. Tariff Rates")
    avg_day = df.groupby('period')[[f"{c_col}_kWh", 'Reference_ToU_Rate_p', 'Custom_Tariff_Rate_p']].mean().reset_index()
    avg_day['Time'] = pd.to_datetime(avg_day['period'] * 30, unit='m').dt.strftime('%H:%M')

    fig_rates = make_subplots(specs=[[{"secondary_y": True}]])
    fig_rates.add_trace(go.Scatter(x=avg_day['Time'], y=avg_day[f"{c_col}_kWh"], fill='tozeroy', mode='none', name='Customer Load (kWh)', fillcolor='rgba(148, 163, 184, 0.4)'), secondary_y=False)
    fig_rates.add_trace(go.Scatter(x=avg_day['Time'], y=avg_day['Reference_ToU_Rate_p'], mode='lines', name='Reference ToU Market Cost (p/kWh)', line=dict(color='#ef4444', width=2, dash='dot')), secondary_y=True)
    fig_rates.add_trace(go.Scatter(x=avg_day['Time'], y=avg_day['Custom_Tariff_Rate_p'], mode='lines', name='Your Custom Tariff Rate (p/kWh)', line=dict(color='#3b82f6', width=3)), secondary_y=True)

    fig_rates.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig_rates.update_yaxes(title_text="Volume (kWh)", secondary_y=False)
    fig_rates.update_yaxes(title_text="Rate (p/kWh)", secondary_y=True)
    st.plotly_chart(fig_rates, use_container_width=True)

# ------------------------------------------
# TAB 2: PORTFOLIO IMPACT (WINNERS & LOSERS)
# ------------------------------------------
with tab2:
    st.markdown("### 🏆 Winners & Losers Matrix")
    st.markdown("Compare how your **Custom Tariff** impacts the bills of different customer groups compared to the standard Flat Cap.")
    
    matrix_data = []
    for c_label, c_id in cohort_dict.items():
        v = df[f"{c_id}_kWh"]
        b_flat = ((v * flat_cap_rate).sum() / 100) + base_sc
        b_cust = ((v * df["Custom_Tariff_Rate_p"]).sum() / 100) + ct_sc
        cost_to_serve = ((v * df["Reference_ToU_Rate_p"]).sum() / 100) + base_sc # Supplier's actual cost
        
        matrix_data.append({
            "Archetype": c_label.split(":")[0],
            "Description": c_label.split(":")[1].strip(),
            "Flat Cap Bill": b_flat,
            "Custom Tariff Bill": b_cust,
            "Customer Impact (£)": b_cust - b_flat,
            "Customer Impact (%)": ((b_cust - b_flat) / b_flat) * 100,
            "Supplier Margin (£)": b_cust - cost_to_serve
        })
    
    df_matrix = pd.DataFrame(matrix_data)
    
    # Format for display
    styled_matrix = df_matrix.style.format({
        "Flat Cap Bill": "£{:.2f}", "Custom Tariff Bill": "£{:.2f}", 
        "Customer Impact (£)": "£{:.2f}", "Customer Impact (%)": "{:.1f}%",
        "Supplier Margin (£)": "£{:.2f}"
    }).map(lambda x: 'color: #10b981' if x < 0 else ('color: #ef4444' if x > 0 else ''), subset=["Customer Impact (£)", "Customer Impact (%)"])\
      .map(lambda x: 'color: #10b981' if x > 0 else ('color: #ef4444' if x < 0 else ''), subset=["Supplier Margin (£)"])
    
    st.dataframe(styled_matrix, use_container_width=True, hide_index=True)
    
    st.divider()
    st.markdown("### 📉 Supplier Portfolio Mix & Risk Exposure")
    st.markdown("Adjust the slider to reflect your supplier's customer base. See how your Custom Tariff impacts total margin and policy levy recovery.")
    
    p1, p2, p3, p4 = st.columns(4)
    mix_1 = p1.number_input("% Cohort 1 (Inflexible)", value=50, step=5)
    mix_2 = p2.number_input("% Cohort 2 (EV/Smart)", value=15, step=5)
    mix_3 = p3.number_input("% Cohort 3 (Economy 7)", value=10, step=5)
    mix_4 = p4.number_input("% Cohort 4 (Low-Income)", value=25, step=5)
    
    total_mix = mix_1 + mix_2 + mix_3 + mix_4
    if total_mix != 100:
        st.error(f"Portfolio mix must equal 100%. Current total: {total_mix}%")
    else:
        # Calculate Weighted Portfolio Metrics
        total_customers = 100000 # Example portfolio size
        w_margin = (
            (mix_1/100 * df_matrix.loc[0, "Supplier Margin (£)"]) +
            (mix_2/100 * df_matrix.loc[1, "Supplier Margin (£)"]) +
            (mix_3/100 * df_matrix.loc[2, "Supplier Margin (£)"]) +
            (mix_4/100 * df_matrix.loc[3, "Supplier Margin (£)"])
        ) * total_customers
        
        st.info(f"**Net Portfolio Margin Impact (per 100,000 customers):** £{w_margin:,.2f}")
        if w_margin < 0:
            st.warning("⚠️ **Margin Deficit Warning:** Your Custom Tariff underprices the peak relative to wholesale costs, or gives away too much discount to flexible users. You are losing money on this portfolio mix.")
        else:
            st.success("✅ **Margin Positive:** Your tariff rules successfully recover wholesale/network costs across your selected customer mix.")

# ------------------------------------------
# TAB 3: LAB GUIDE
# ------------------------------------------
with tab3:
    st.markdown("### 📖 How to Use the Tariff Lab")
    st.markdown("""
    Welcome to the Post-MHHS Tariff Lab. This tool is designed for policy teams to evaluate the commercial and societal impacts of moving away from a static Flat Price Cap.
    
    #### 1. What is the 'Reference ToU Market Cost'?
    Ofgem's traditional SVT is flat. However, under MHHS (Market-wide Half-Hourly Settlement), suppliers are exposed to actual 30-minute market costs. 
    The **Reference ToU Market Cost** (the red dotted line in Tab 1) shows what a perfectly cost-reflective tariff looks like. It mathematically shapes the Wholesale and Network (DUoS RAG) allowances against real market physics—resulting in ~28p/kWh winter evening peaks and ~5p/kWh summer off-peaks.
    
    #### 2. Evaluating the 'Winners and Losers'
    Not all customers can shift their energy use. 
    *   **Winners:** Customers in **Cohort 2 (EVs)** inherently use energy at night. Under a ToU cap, their bills naturally drop without them changing behavior. 
    *   **Losers:** Customers in **Cohort 1 (Inflexible Families)** cook dinner and use appliances during the 16:00–19:00 peak. If forced onto a cost-reflective ToU tariff, their bills will spike severely.
    
    #### 3. The Supplier Margin Trap
    When you build a **Custom Tariff**, the system calculates whether the revenue you collect covers your **actual** cost-to-serve (Wholesale + DUoS + Policy).
    If you offer a massive overnight discount to attract EV owners (Cohort 2), you collect less revenue per kWh. Because **Policy Costs (RO, FiT, WHD)** are mostly flat volumetric levies, selling cheap overnight power can result in a failure to collect enough revenue to pay your regulatory policy bills. 
    Use the **Portfolio Impact** tab to ensure your tariff covers costs across a mixed customer base.
    """)
