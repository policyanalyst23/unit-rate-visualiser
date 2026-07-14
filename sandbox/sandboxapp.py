import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Price Cap Sandbox", layout="wide", page_icon="🎛️")
st.title("🎛️ Energy Price Cap Simulator & Sandbox")
st.markdown("Play with the July 2026 price cap allowances. Add, edit, or remove policies to simulate the exact impact on the final consumer bill.")

# ==========================================
# 2. LOAD DATA & TDCV METADATA
# ==========================================
@st.cache_data
def load_sandbox_data():
    try:
        df = pd.read_csv("sandbox/Sandbox_Master_Allowances_July2026.csv")
        return df
    except FileNotFoundError:
        st.error("Missing 'Sandbox_Master_Allowances_July2026.csv'. Please run the Colab extraction script first.")
        return pd.DataFrame()

df_master = load_sandbox_data()

# Official Ofgem TDCV values (July 2026 onwards)
TDCV_DEFAULTS = {
    'Gas': 11500,
    'Electricity Single-Rate': 2900,
    'Electricity Multi-Register': 3900,
    'Dual Fuel (implied)': 100 # Represented as a percentage for Dual Fuel
}

# ==========================================
# 3. SIDEBAR ENGINE: ANCHORS & CONSUMPTION
# ==========================================
st.sidebar.header("1. Choose Baseline Profile")
if not df_master.empty:
    available_fuels = sorted(df_master['Fuel Type'].unique())
    available_pms = sorted(df_master['Payment Method'].unique())
else:
    available_fuels, available_pms = [], []

selected_fuel = st.sidebar.selectbox("Fuel Type", options=available_fuels)
selected_pm = st.sidebar.selectbox("Payment Method", options=available_pms)

st.sidebar.divider()
st.sidebar.header("2. Set Consumer Usage")

default_tdcv = TDCV_DEFAULTS.get(selected_fuel, 2900)
use_tdcv = st.sidebar.checkbox("Use Standard Ofgem TDCV", value=True)

if selected_fuel == 'Dual Fuel (implied)':
    st.sidebar.markdown("*Dual Fuel scales by % of typical usage.*")
    custom_usage = st.sidebar.number_input(
        "Usage Level (%)", 
        min_value=10, max_value=300, value=100, step=10,
        disabled=use_tdcv
    )
    usage_multiplier = custom_usage / 100.0
else:
    custom_usage = st.sidebar.number_input(
        f"Annual Consumption (kWh)", 
        min_value=0, value=default_tdcv, step=100,
        disabled=use_tdcv
    )
    # The crucial scaling math:
    usage_multiplier = custom_usage / default_tdcv

st.sidebar.divider()
st.sidebar.info("💡 **How scaling works:** Standing Charge changes apply a flat £ impact. Unit Rate changes scale dynamically based on the consumption entered above.")

# ==========================================
# 4. INITIALIZE SESSION STATE FOR CUSTOM POLICIES
# ==========================================
if 'custom_policies' not in st.session_state:
    st.session_state.custom_policies = []

# ==========================================
# 5. MAIN SANDBOX LAYOUT
# ==========================================
if df_master.empty:
    st.stop()

# Filter data to the chosen anchor
df_filtered = df_master[(df_master['Fuel Type'] == selected_fuel) & 
                        (df_master['Payment Method'] == selected_pm)].copy()

if df_filtered.empty:
    st.warning("No baseline data available for this specific combination.")
    st.stop()

col_controls, col_visuals = st.columns([1.2, 2])

# Dictionary to hold the final simulated values from the inputs
simulated_values = {}
baseline_values = {}

with col_controls:
    st.subheader("🛠️ Policy Control Panel")
    st.markdown("*(Values shown are annualized £ at standard TDCV)*")
    
    # Render an expander for every Tab Category in the data
    categories = sorted(df_filtered['Tab Category'].unique())
    
    for category in categories:
        with st.expander(f"📁 {category}", expanded=False):
            cat_data = df_filtered[df_filtered['Tab Category'] == category]
            for _, row in cat_data.iterrows():
                allowance_name = row['Allowance']
                charge_type = row['Charge Type']
                base_val = float(row['Allowance Value'])
                
                # Unique key for the widget
                widget_key = f"{category}_{allowance_name}_{charge_type}"
                
                # The Sandbox Input
                sim_val = st.number_input(
                    label=f"{allowance_name} ({'SC' if charge_type == 'Standing Charge' else 'UR'})",
                    value=base_val,
                    step=5.0,
                    key=widget_key
                )
                
                simulated_values[widget_key] = {
                    'name': allowance_name,
                    'charge_type': charge_type,
                    'baseline': base_val,
                    'simulated': sim_val
                }

    # --- CUSTOM POLICY ADDER ---
    with st.expander("➕ Add Proposed Custom Policy", expanded=True):
        st.markdown("Introduce a brand new allowance to the price cap.")
        cp_name = st.text_input("Policy Name", placeholder="e.g., Green Grid Levy")
        cp_type = st.selectbox("Charge Application", ["Standing Charge", "Unit Rate"])
        cp_val = st.number_input("Annual Value at TDCV (£)", value=0.0, step=5.0)
        
        if st.button("Add Policy to Simulation"):
            if cp_name:
                st.session_state.custom_policies.append({
                    'name': cp_name,
                    'charge_type': cp_type,
                    'baseline': 0.0,
                    'simulated': cp_val
                })
                st.rerun()

    # Allow clearing custom policies
    if st.session_state.custom_policies:
        if st.button("🗑️ Clear Custom Policies"):
            st.session_state.custom_policies = []
            st.rerun()

# ==========================================
# 6. CALCULATE IMPACTS & RENDER VISUALS
# ==========================================
with col_visuals:
    # 1. Math Engine: Apply Consumption Multipliers
    total_baseline_bill = 0.0
    total_simulated_bill = 0.0
    waterfall_steps = []
    
    # Process existing allowances
    for key, data in simulated_values.items():
        mult = 1.0 if data['charge_type'] == 'Standing Charge' else usage_multiplier
        
        adj_base = data['baseline'] * mult
        adj_sim = data['simulated'] * mult
        delta = adj_sim - adj_base
        
        total_baseline_bill += adj_base
        total_simulated_bill += adj_sim
        
        if round(delta, 2) != 0:
            waterfall_steps.append({'name': data['name'], 'delta': delta})
            
    # Process custom policies
    for cp in st.session_state.custom_policies:
        mult = 1.0 if cp['charge_type'] == 'Standing Charge' else usage_multiplier
        adj_sim = cp['simulated'] * mult
        
        total_simulated_bill += adj_sim
        if round(adj_sim, 2) != 0:
            waterfall_steps.append({'name': f"⭐ {cp['name']}", 'delta': adj_sim})

    net_impact = total_simulated_bill - total_baseline_bill

    # 2. Render KPI Cards
    st.subheader("📊 Simulation Results")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Baseline Bill (July 2026)", f"£{total_baseline_bill:,.2f}")
    kpi2.metric("Simulated Bill", f"£{total_simulated_bill:,.2f}", delta=f"£{net_impact:,.2f}", delta_color="inverse")
    
    impact_pct = (net_impact / total_baseline_bill * 100) if total_baseline_bill > 0 else 0
    kpi3.metric("Percentage Change", f"{impact_pct:,.2f}%", delta=f"{impact_pct:,.2f}%", delta_color="inverse")
    
    st.divider()

    # 3. Render Waterfall Chart
    x_labels = ["Baseline Bill"]
    y_values = [total_baseline_bill]
    measure = ["absolute"]
    
    # Add the deltas
    for step in waterfall_steps:
        x_labels.append(step['name'])
        y_values.append(step['delta'])
        measure.append("relative")
        
    # Add dummy step if no changes made so chart renders nicely
    if not waterfall_steps:
        x_labels.append("No Changes")
        y_values.append(0)
        measure.append("relative")
        
    x_labels.append("Simulated Bill")
    y_values.append(total_simulated_bill)
    measure.append("total")
    
    fig = go.Figure(go.Waterfall(
        name = "Impact", 
        orientation = "v",
        measure = measure,
        x = x_labels,
        textposition = "outside",
        text = [f"{'+' if v > 0 and m == 'relative' else ''}£{v:,.0f}" for v, m in zip(y_values, measure)],
        y = y_values,
        connector = {"line":{"color":"rgb(63, 63, 63)", "width": 2}},
        decreasing = {"marker":{"color":"#2ca02c"}}, # Green for savings
        increasing = {"marker":{"color":"#d62728"}}, # Red for price hikes
        totals = {"marker":{"color":"#1f77b4"}}      # Blue for the Bill Totals
    ))
    
    fig.update_layout(
        title="Impact of Policy Changes on Consumer Bill",
        waterfallgap=0.3,
        height=600,
        margin=dict(t=50, b=100),
        yaxis_title="Total Bill (£)"
    )
    
    st.plotly_chart(fig, use_container_width=True)
