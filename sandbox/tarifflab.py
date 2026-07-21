import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Post-MHHS Tariff Lab", layout="wide", page_icon="⚡")
st.title("⚡ Post-MHHS Tariff Lab")
st.markdown("Simulate Time of Use (ToU) and Dynamic Tariffs to calculate customer bill impacts and actual supplier margin recovery.")

# ==========================================
# 2. SYNTHETIC LOAD SHAPE GENERATOR
# ==========================================
@st.cache_data
def generate_synthetic_profiles(target_tdcv=2900.0):
    dates = pd.date_range(start="2026-01-01", end="2026-12-31 23:30:00", freq="30min")
    df = pd.DataFrame({"datetime": dates})
    df["date"] = df["datetime"].dt.date
    df["month"] = df["datetime"].dt.month
    df["day_of_week"] = df["datetime"].dt.dayofweek
    df["period"] = df["datetime"].dt.hour * 2 + df["datetime"].dt.minute // 30 + 1
    
    t_hours = (df["period"] - 1) * 0.5

    # Gaussian Base Shapes
    pc1_base = 0.15 + 0.6 * np.exp(-((t_hours - 8.0) ** 2) / (2 * 1.2 ** 2)) + 1.2 * np.exp(-((t_hours - 18.5) ** 2) / (2 * 2.0 ** 2))
    pc2_base = 0.10 + 2.2 * np.where((t_hours >= 0.5) & (t_hours <= 7.5), 1.0, 0.0) + 0.3 * np.exp(-((t_hours - 18.5) ** 2) / (2 * 2.0 ** 2))

    # Modulators
    day_of_year = df["datetime"].dt.dayofyear
    seasonal_mult = 1.0 + 0.45 * np.cos(2 * np.pi * (day_of_year - 1) / 365)
    is_weekend = df["day_of_week"] >= 5
    weekend_mult = np.where(is_weekend, 0.92, 1.0)

    # Compile and Normalize to enforce Volume Conservation
    df["PC1_kWh"] = (pc1_base * seasonal_mult * weekend_mult)
    df["PC1_kWh"] = (df["PC1_kWh"] / df["PC1_kWh"].sum()) * target_tdcv
    
    df["PC2_kWh"] = (pc2_base * seasonal_mult * weekend_mult)
    df["PC2_kWh"] = (df["PC2_kWh"] / df["PC2_kWh"].sum()) * target_tdcv

    return df

# ==========================================
# 3. COST SHAPING ENGINE
# ==========================================
def apply_shaped_costs(df, base_ws_p, base_duos_p):
    hours = (df['period'] - 1) * 0.5
    is_weekday = df['day_of_week'] < 5
    
    # 1. Wholesale Time Multiplier (Peak: 1.8x, Off-Peak: 0.5x)
    ws_mult = np.where((hours >= 16.0) & (hours < 19.5), 1.8, np.where((hours >= 23.0) | (hours < 7.0), 0.5, 1.0))
    day_of_year = df["datetime"].dt.dayofyear
    seasonal_mult = 1.0 + 0.35 * np.cos(2 * np.pi * (day_of_year - 1) / 365)
    
    df['wholesale_cost_raw'] = base_ws_p * ws_mult * seasonal_mult
    
    # 2. DUoS RAG Charging (Red: 9x, Amber: 1.2x, Green: 0.15x)
    red_band = is_weekday & (hours >= 16.0) & (hours < 19.0)
    amber_band = is_weekday & (((hours >= 7.5) & (hours < 16.0)) | ((hours >= 19.0) & (hours < 22.0)))
    
    df['duos_cost_raw'] = np.where(red_band, base_duos_p * 9.0, np.where(amber_band, base_duos_p * 1.2, base_duos_p * 0.15))
    
    # Mathematical Normalization: Force the weighted average of the shaped curves to perfectly match the user's flat baseline input
    current_ws_avg = (df['wholesale_cost_raw'] * df['baseline_kWh']).sum() / df['baseline_kWh'].sum()
    current_duos_avg = (df['duos_cost_raw'] * df['baseline_kWh']).sum() / df['baseline_kWh'].sum()
    
    df['wholesale_cost_p'] = df['wholesale_cost_raw'] * (base_ws_p / current_ws_avg)
    df['duos_cost_p'] = df['duos_cost_raw'] * (base_duos_p / current_duos_avg)
    
    return df

# ==========================================
# 4. SIDEBAR CONTROLS
# ==========================================
st.sidebar.header("1. Customer Profile")
profile_choice = st.sidebar.selectbox("Elexon Profile Class", ["PC1 (Standard Unrestricted)", "PC2 (Economy 7)"])
tdcv_input = st.sidebar.number_input("Annual Consumption (TDCV) kWh", value=2900, step=100)

st.sidebar.divider()
st.sidebar.header("2. Supplier Cost Baseline (p/kWh)")
st.sidebar.markdown("Set the flat Ofgem allowances.")
base_ws = st.sidebar.number_input("Direct Wholesale (avg p/kWh)", value=10.0, step=0.5)
base_duos = st.sidebar.number_input("DUoS Network (avg p/kWh)", value=2.0, step=0.1)
base_other = st.sidebar.number_input("Other Volumetric (Policy/TNUoS) p/kWh", value=4.5, step=0.1)
base_sc = st.sidebar.number_input("Total Standing Charge (£/year)", value=180.0, step=5.0)

st.sidebar.divider()
st.sidebar.header("3. Demand Shifter")
st.sidebar.markdown("Shift volume from the 16:00-19:30 Peak into the 23:00-07:00 Off-Peak.")
shift_pct = st.sidebar.slider("Shift % of Peak Demand", min_value=0.0, max_value=50.0, value=10.0, step=1.0) / 100.0

st.sidebar.divider()
st.sidebar.header("4. Dynamic Tariff Rules")
tariff_type = st.sidebar.radio("Tariff Structure", ["Time of Use (ToU)", "Rising Block (RBT)", "Falling Block (FBT)"])

if tariff_type == "Time of Use (ToU)":
    tou_peak = st.sidebar.number_input("Peak Rate (16:00-19:30) p/kWh", value=32.0, step=1.0)
    tou_shoulder = st.sidebar.number_input("Shoulder Rate p/kWh", value=22.0, step=1.0)
    tou_offpeak = st.sidebar.number_input("Off-Peak Rate (23:00-07:00) p/kWh", value=12.0, step=1.0)
else:
    block_threshold = st.sidebar.number_input("Block 1 Threshold (kWh/year)", value=2000, step=100)
    tier1_rate = st.sidebar.number_input("Tier 1 Rate (p/kWh)", value=18.0 if tariff_type == "Rising Block (RBT)" else 28.0)
    tier2_rate = st.sidebar.number_input("Tier 2 Rate (p/kWh)", value=28.0 if tariff_type == "Rising Block (RBT)" else 15.0)

# ==========================================
# 5. CORE CALCULATIONS
# ==========================================
df = generate_synthetic_profiles(tdcv_input).copy()
df['baseline_kWh'] = df['PC1_kWh'] if "PC1" in profile_choice else df['PC2_kWh']

# Apply Demand Shifting
peak_mask = (df["period"] >= 33) & (df["period"] <= 39)
offpeak_mask = (df["period"] >= 47) | (df["period"] <= 14)

df["shifted_kWh"] = df["baseline_kWh"].copy()
daily_peak_shifted = df[peak_mask].groupby("date")["baseline_kWh"].sum() * shift_pct
df.loc[peak_mask, "shifted_kWh"] *= (1 - shift_pct)

daily_offpeak_counts = df[offpeak_mask].groupby("date").size()
add_per_offpeak = daily_peak_shifted / daily_offpeak_counts
df["add_vol"] = df["date"].map(add_per_offpeak)
df.loc[offpeak_mask, "shifted_kWh"] += df.loc[offpeak_mask, "add_vol"]

# Generate Shaped Costs
df = apply_shaped_costs(df, base_ws, base_duos)

# Apply Revenue Tariffs
flat_baseline_rate = base_ws + base_duos + base_other
df['revenue_baseline_p'] = flat_baseline_rate
df['revenue_baseline_GBP'] = (df['baseline_kWh'] * flat_baseline_rate) / 100.0

if tariff_type == "Time of Use (ToU)":
    df['simulated_rate_p'] = np.where(peak_mask, tou_peak, np.where(offpeak_mask, tou_offpeak, tou_shoulder))
    df['revenue_simulated_GBP'] = (df['shifted_kWh'] * df['simulated_rate_p']) / 100.0
else:
    # Daily Block Calculation Proxy
    daily_limit = block_threshold / 365.0
    daily_usage = df.groupby('date')['shifted_kWh'].transform('sum')
    df['tier1_fraction'] = np.where(daily_usage > 0, np.clip(daily_limit / daily_usage, 0.0, 1.0), 1.0)
    df['simulated_rate_p'] = (df['tier1_fraction'] * tier1_rate) + ((1 - df['tier1_fraction']) * tier2_rate)
    df['revenue_simulated_GBP'] = (df['shifted_kWh'] * df['simulated_rate_p']) / 100.0

# Calculate Total Billed Amounts
total_baseline_bill = df['revenue_baseline_GBP'].sum() + base_sc
total_simulated_bill = df['revenue_simulated_GBP'].sum() + base_sc
customer_variance = total_simulated_bill - total_baseline_bill

# Calculate Realized Costs
df['cost_wholesale_GBP'] = (df['shifted_kWh'] * df['wholesale_cost_p']) / 100.0
df['cost_duos_GBP'] = (df['shifted_kWh'] * df['duos_cost_p']) / 100.0
df['cost_other_GBP'] = (df['shifted_kWh'] * base_other) / 100.0

total_wholesale_cost = df['cost_wholesale_GBP'].sum()
total_network_cost = df['cost_duos_GBP'].sum()
total_policy_cost = df['cost_other_GBP'].sum()

net_margin = total_simulated_bill - (total_wholesale_cost + total_network_cost + total_policy_cost + base_sc)
margin_pct = (net_margin / total_simulated_bill) * 100 if total_simulated_bill > 0 else 0

# ==========================================
# 6. UI DASHBOARD
# ==========================================
m1, m2, m3, m4 = st.columns(4)
m1.metric("Flat Baseline Bill (£/yr)", f"£{total_baseline_bill:,.2f}")
m2.metric("Simulated Dynamic Bill (£/yr)", f"£{total_simulated_bill:,.2f}", delta=f"£{customer_variance:,.2f}", delta_color="inverse")
m3.metric("Customer Savings", f"{-customer_variance / total_baseline_bill * 100:,.1f}%" if customer_variance < 0 else "None")
m4.metric("Realized Supplier Margin", f"£{net_margin:,.2f}", delta=f"{margin_pct:.1f}% Margin")

st.divider()

# --- Chart A: 24-Hour Load Profile Overlay ---
st.markdown("### 🕒 Average 24-Hour Demand vs. Tariff Structure")
avg_day = df.groupby('period')[['baseline_kWh', 'shifted_kWh', 'simulated_rate_p', 'wholesale_cost_p']].mean().reset_index()
avg_day['Time'] = pd.to_datetime(avg_day['period'] * 30, unit='m').dt.strftime('%H:%M')

figA = make_subplots(specs=[[{"secondary_y": True}]])
figA.add_trace(go.Scatter(x=avg_day['Time'], y=avg_day['baseline_kWh'], fill='tozeroy', mode='none', name='Baseline Load', fillcolor='rgba(148, 163, 184, 0.3)'), secondary_y=False)
figA.add_trace(go.Scatter(x=avg_day['Time'], y=avg_day['shifted_kWh'], mode='lines', name='Shifted Load', line=dict(color='#3b82f6', width=3)), secondary_y=False)
figA.add_trace(go.Scatter(x=avg_day['Time'], y=avg_day['simulated_rate_p'], mode='lines', name='Dynamic Tariff Rate (p/kWh)', line=dict(color='#f59e0b', width=2, dash='dash')), secondary_y=True)
figA.add_trace(go.Scatter(x=avg_day['Time'], y=avg_day['wholesale_cost_p'], mode='lines', name='Wholesale Cost (p/kWh)', line=dict(color='#ef4444', width=2, dash='dot')), secondary_y=True)

figA.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
figA.update_yaxes(title_text="Volume (kWh)", secondary_y=False)
figA.update_yaxes(title_text="Cost / Rate (p/kWh)", secondary_y=True)
st.plotly_chart(figA, use_container_width=True)

colB, colC = st.columns(2)

# --- Chart B: Cost Recovery Margin Waterfall ---
with colB:
    st.markdown("### 💧 Annual Margin Recovery Waterfall")
    figB = go.Figure(go.Waterfall(
        orientation="v", measure=["relative", "relative", "relative", "relative", "relative", "total"],
        x=["Standing Charge", "Billed Unit Revenue", "Wholesale Cost", "DUoS Network Cost", "Policy & Other", "Net Supplier Margin"],
        y=[base_sc, total_simulated_bill - base_sc, -total_wholesale_cost, -total_network_cost, -total_policy_cost, net_margin],
        connector={"line": {"color": "rgb(63, 63, 63)", "width": 2}},
        decreasing={"marker": {"color": "#ef4444"}}, increasing={"marker": {"color": "#10b981"}}, totals={"marker": {"color": "#6366f1"}}
    ))
    figB.update_layout(showlegend=False, yaxis_title="Amount (£)")
    st.plotly_chart(figB, use_container_width=True)

# --- Chart C: Seasonal Margin Exposure ---
with colC:
    st.markdown("### 🗓️ Monthly Margin Heatmap")
    df['Total_Cost_GBP'] = df['cost_wholesale_GBP'] + df['cost_duos_GBP'] + df['cost_other_GBP']
    monthly = df.groupby('month')[['revenue_simulated_GBP', 'Total_Cost_GBP']].sum().reset_index()
    monthly['Margin'] = monthly['revenue_simulated_GBP'] - monthly['Total_Cost_GBP']
    
    figC = go.Figure()
    figC.add_trace(go.Bar(x=monthly['month'], y=monthly['revenue_simulated_GBP'], name='Revenue', marker_color='#14b8a6'))
    figC.add_trace(go.Bar(x=monthly['month'], y=-monthly['Total_Cost_GBP'], name='Cost to Serve', marker_color='#f43f5e'))
    figC.add_trace(go.Scatter(x=monthly['month'], y=monthly['Margin'], mode='lines+markers', name='Net Volumetric Margin', line=dict(color='#facc15', width=3)))
    
    figC.update_layout(barmode='relative', xaxis=dict(tickmode='array', tickvals=list(range(1,13)), ticktext=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']), yaxis_title="Amount (£)")
    st.plotly_chart(figC, use_container_width=True)

# ==========================================
# 7. DATA EXPORT
# ==========================================
st.divider()
st.markdown("### 📥 Export Granular Simulation Data")
export_df = df[['datetime', 'date', 'period', 'baseline_kWh', 'shifted_kWh', 'simulated_rate_p', 'wholesale_cost_p', 'duos_cost_p', 'revenue_simulated_GBP', 'cost_wholesale_GBP']].copy()
st.download_button(
    label="Download Full 17,520 Half-Hourly Simulation (CSV)",
    data=export_df.to_csv(index=False).encode('utf-8'),
    file_name="dynamic_tariff_simulation.csv",
    mime="text/csv"
)
