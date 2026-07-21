import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os

# ==========================================
# 1. PAGE CONFIGURATION & METADATA
# ==========================================
st.set_page_config(page_title="Margin Analyzer", layout="wide", page_icon="🎯")
st.title("🎯 Customer Decile & Margin Impact Analyzer")
st.markdown("Analyze how shifting fixed Standing Charges to volumetric Unit Rates impacts your profitability across different customer consumption profiles.")

ALLOWANCE_DICT = {
    'DF': 'Direct Fuel Cost', 'Direct Fuel': 'Direct Fuel Cost', 
    'CM': 'Capacity Market', 'AA': 'Adjustment Allowance', 
    'PC': 'Policy Costs', 'NC': 'Network Costs', 'OC': 'Operating Costs (Legacy)', 
    'CO': 'Core Operating Costs', 'SMNCC': 'Smart Metering Net Cost Change', 
    'IC': 'Industry Charges', 'PAAC': 'Payment Method Uplift (Fixed)', 
    'PAP': 'Payment Method Uplift (Variable)', 'DRC': 'Debt-Related Costs', 
    'EBIT': 'Earnings Before Interest and Tax', 'HAP': 'Headroom Allowance Percentage', 
    'RO': 'Renewables Obligation (RO)', 'FiT': 'Feed-in Tariff (FiT)', 
    'ECO': 'Energy Company Obligation (ECO)', 'WHD': 'Warm Home Discount (WHD)', 
    'WHD (unit rate)': 'Warm Home Discount (Unit Rate)', 
    'AAHEDC': 'Assistance for Areas with High Electricity Distribution Costs', 
    'NCC': 'Network Charging Compensation', 'nRAB': 'Nuclear Regulated Asset Base', 
    'GGL': 'Green Gas Levy (GGL)',
    'CfD': 'Contracts for Difference (CfD)', 'Backwardation': 'Backwardation', 
    'Gas Transmission': 'Gas Transmission', 'Gas Distribution': 'Gas Distribution', 
    'TNUoS': 'Transmission Network Use of System (TNUoS)', 
    'BSUoS': 'Balancing Services Use of System (BSUoS)', 
    'DUoS': 'Distribution Use of System (DUoS)', 'Levelisation': 'Levelisation'
}

FUEL_MAPPING = {
    'Electricity Single Rate': 'Electricity Single-Rate',
    'Electricity- Single-Rate': 'Electricity Single-Rate',
    'Electricity - Single-Rate': 'Electricity Single-Rate',
    'Electricity - Single Rate': 'Electricity Single-Rate',
    'Electricity - Multi-Register': 'Electricity Multi-Register',
    'Electricity Multi Register': 'Electricity Multi-Register',
    'Non-PPM gas': 'Gas',
    'Gas': 'Gas',
    'Dual Fuel': 'Dual Fuel (implied)',
    'Dual Fuel (implied)': 'Dual Fuel (implied)'
}

DEFAULT_TDCV = {"Gas": 11500, "Electricity Single-Rate": 2900, "Electricity Multi-Register": 2900}

# Define 10 Consumption Deciles (Anchored around Decile 5 as TDCV)
DECILES = {
    "Gas": [3000, 5000, 7500, 9500, 11500, 13500, 16000, 19000, 23000, 28000],
    "Electricity Single-Rate": [1000, 1500, 2000, 2500, 2900, 3500, 4200, 5000, 6500, 8500],
    "Dual Fuel": [
        {"Elec": 1000, "Gas": 3000}, {"Elec": 1500, "Gas": 5000}, 
        {"Elec": 2000, "Gas": 7500}, {"Elec": 2500, "Gas": 9500}, 
        {"Elec": 2900, "Gas": 11500}, {"Elec": 3500, "Gas": 13500}, 
        {"Elec": 4200, "Gas": 16000}, {"Elec": 5000, "Gas": 19000}, 
        {"Elec": 6500, "Gas": 23000}, {"Elec": 8500, "Gas": 28000}
    ]
}

# Default Portfolio Distribution (Normally Distributed)
DEFAULT_PORTFOLIO_WEIGHTS = [0.03, 0.07, 0.12, 0.18, 0.20, 0.15, 0.10, 0.08, 0.05, 0.02]

# ==========================================
# 2. DATA LOADING & FILTERING
# ==========================================
@st.cache_data
def load_baseline_data():
    files = ['Cleaned_Price_Cap_Data.csv', 'wholesale_allowances_cleaned.csv', 'policy_costs_cleaned.csv', 'network_costs_cleaned.csv']
    possible_folders = ['', 'mastertrackerapp/']
    dfs = []
    
    for f in files:
        file_loaded = False
        for folder in possible_folders:
            filepath = os.path.join(folder, f)
            if os.path.exists(filepath):
                df = pd.read_csv(filepath)
                for col in ['Fuel Type', 'Charge Type', 'Payment Method', 'Allowance', 'Cap Period']:
                    if col in df.columns:
                        df[col] = df[col].astype(str).str.strip()
                if 'Fuel Type' in df.columns:
                    df['Fuel Type'] = df['Fuel Type'].replace(FUEL_MAPPING)
                if 'Allowance' in df.columns:
                    df['Allowance_Full'] = df['Allowance'].map(ALLOWANCE_DICT).fillna(df['Allowance'])
                if 'Payment Method' not in df.columns or df['Payment Method'].isnull().all() or (df['Payment Method'] == 'nan').all():
                    df['Payment Method'] = 'All' 
                if 'Cap Period' in df.columns:
                    df['Temp_Start'] = df['Cap Period'].astype(str).str.split('-').str[0].str.strip()
                    df['Parsed_Date'] = pd.to_datetime(df['Temp_Start'], errors='coerce')
                    
                dfs.append(df)
                file_loaded = True
                break
                
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        max_date = combined['Parsed_Date'].max()
        return combined[combined['Parsed_Date'] == max_date].copy()
    return pd.DataFrame()

df_baseline = load_baseline_data()

# ==========================================
# 3. SIDEBAR (GLOBAL SETTINGS)
# ==========================================
st.sidebar.header("1. Portfolio Settings")
fuel_options = ["Dual Fuel", "Electricity Single-Rate", "Gas"]
selected_fuel = st.sidebar.selectbox("Fuel Type Profile", options=fuel_options)
selected_payment = st.sidebar.selectbox("Payment Method", options=["Direct Debit", "Standard Credit", "PPM"])

st.sidebar.divider()
st.sidebar.header("2. Supplier Portfolio Mix")
st.sidebar.markdown("Adjust to match your actual customer base. Ensure it sums to 100%.")

weights = []
for i in range(10):
    w = st.sidebar.number_input(f"Decile {i+1} Weight (%)", value=DEFAULT_PORTFOLIO_WEIGHTS[i]*100, step=1.0, min_value=0.0, max_value=100.0)
    weights.append(w / 100.0)

portfolio_size = st.sidebar.number_input("Total Active Customers", value=1000000, step=100000)

is_dual_fuel = (selected_fuel == "Dual Fuel")
target_fuels = ['Electricity Single-Rate', 'Gas'] if is_dual_fuel else [selected_fuel]

df_filtered = df_baseline[
    (df_baseline['Fuel Type'].isin(target_fuels)) & 
    ((df_baseline['Payment Method'] == selected_payment) | (df_baseline['Payment Method'] == 'All'))
].copy()
df_filtered['Charge Type'] = df_filtered['Charge Type'].replace({'UR': 'Unit Rate', 'SC': 'Standing Charge'})

# Calculate Current SC and UR Rates (Not Annualized, raw £/kWh and £/year)
sc_baseline_total = df_filtered[df_filtered['Charge Type'] == 'Standing Charge']['Cost Value'].sum()
ur_baseline_elec = df_filtered[(df_filtered['Charge Type'] == 'Unit Rate') & (df_filtered['Fuel Type'] == 'Electricity Single-Rate')]['Cost Value'].sum() / DEFAULT_TDCV['Electricity Single-Rate'] if is_dual_fuel or selected_fuel == 'Electricity Single-Rate' else 0
ur_baseline_gas = df_filtered[(df_filtered['Charge Type'] == 'Unit Rate') & (df_filtered['Fuel Type'] == 'Gas')]['Cost Value'].sum() / DEFAULT_TDCV['Gas'] if is_dual_fuel or selected_fuel == 'Gas' else 0

# ==========================================
# 4. TARIFF RESTRUCTURING LEVER
# ==========================================
st.markdown("### 🎛️ The Restructuring Engine")
st.markdown("Simulate Ofgem shifting costs from the Standing Charge to the Unit Rate. (e.g., Shifting Operating Costs entirely to volumetric recovery).")

col1, col2, col3 = st.columns(3)
shift_amount = col1.number_input("Amount to shift off Standing Charge (£)", min_value=0.0, max_value=float(sc_baseline_total), value=0.0, step=5.0)

shift_fuel_target = col2.selectbox(
    "Apply Volumetric Shift to:", 
    options=["Electricity", "Gas", "Split (70% Elec / 30% Gas)"]
) if is_dual_fuel else selected_fuel

# Math: Converting the SC £ drop into a UR p/kWh increase based on TDCV
sc_simulated_total = sc_baseline_total - shift_amount
ur_simulated_elec = ur_baseline_elec
ur_simulated_gas = ur_baseline_gas

if shift_amount > 0:
    if shift_fuel_target == "Electricity" or (not is_dual_fuel and selected_fuel == 'Electricity Single-Rate'):
        ur_simulated_elec += (shift_amount / DEFAULT_TDCV['Electricity Single-Rate'])
    elif shift_fuel_target == "Gas" or (not is_dual_fuel and selected_fuel == 'Gas'):
        ur_simulated_gas += (shift_amount / DEFAULT_TDCV['Gas'])
    elif shift_fuel_target == "Split (70% Elec / 30% Gas)":
        ur_simulated_elec += ((shift_amount * 0.70) / DEFAULT_TDCV['Electricity Single-Rate'])
        ur_simulated_gas += ((shift_amount * 0.30) / DEFAULT_TDCV['Gas'])

# ==========================================
# 5. DECILE IMPACT CALCULATION
# ==========================================
decile_data = []

for i in range(10):
    if is_dual_fuel:
        elec_kwh = DECILES["Dual Fuel"][i]["Elec"]
        gas_kwh = DECILES["Dual Fuel"][i]["Gas"]
        label = f"D{i+1}: E:{elec_kwh} / G:{gas_kwh}"
    else:
        elec_kwh = DECILES[selected_fuel][i] if selected_fuel == 'Electricity Single-Rate' else 0
        gas_kwh = DECILES[selected_fuel][i] if selected_fuel == 'Gas' else 0
        label = f"D{i+1}: {elec_kwh if elec_kwh > 0 else gas_kwh} kWh"
        
    # Calculate baseline and simulated revenues (which equates to the cap bill)
    base_rev = sc_baseline_total + (ur_baseline_elec * elec_kwh) + (ur_baseline_gas * gas_kwh)
    sim_rev = sc_simulated_total + (ur_simulated_elec * elec_kwh) + (ur_simulated_gas * gas_kwh)
    variance = sim_rev - base_rev
    
    customers_in_decile = portfolio_size * weights[i]
    portfolio_margin_impact = variance * customers_in_decile
    
    decile_data.append({
        "Decile": f"D{i+1}",
        "Profile": label,
        "Baseline Bill": base_rev,
        "Simulated Bill": sim_rev,
        "Net Margin Impact (£/cust)": variance,
        "Portfolio Impact (£)": portfolio_margin_impact
    })

df_results = pd.DataFrame(decile_data)
net_portfolio_impact = df_results["Portfolio Impact (£)"].sum()

# ==========================================
# 6. VISUALISATION
# ==========================================
st.divider()
st.markdown("### 📊 Distributional Margin Heatmap")

met1, met2, met3 = st.columns(3)
met1.metric("Standing Charge Reduction", f"-£{shift_amount:,.2f}")
if net_portfolio_impact < 0:
    met2.metric("Total Portfolio Margin Impact", f"-£{abs(net_portfolio_impact):,.0f}", delta="Net Loss", delta_color="inverse")
else:
    met2.metric("Total Portfolio Margin Impact", f"+£{net_portfolio_impact:,.0f}", delta="Net Gain", delta_color="normal")
met3.metric("Portfolio Verification", f"{sum(weights)*100:.1f}% Distributed", help="Must equal 100%")

if sum(weights) > 1.01 or sum(weights) < 0.99:
    st.error("Warning: Your portfolio weights in the sidebar do not equal 100%. Please adjust.")

# Visual 1: Decile Revenue Shift
fig_bar = go.Figure()

colors = ['#ef4444' if x < 0 else '#10b981' for x in df_results['Net Margin Impact (£/cust)']]

fig_bar.add_trace(go.Bar(
    x=df_results['Decile'], 
    y=df_results['Net Margin Impact (£/cust)'],
    marker_color=colors,
    text=[f"£{v:,.2f}" for v in df_results['Net Margin Impact (£/cust)']],
    textposition='auto',
    hovertemplate="<b>%{x}</b> (%{customdata})<br>Change: £%{y:.2f}<extra></extra>",
    customdata=df_results['Profile']
))

fig_bar.update_layout(
    title="Realized Margin Impact Per Customer by Decile",
    yaxis_title="Change in EBIT/Margin (£)",
    xaxis_title="Consumption Deciles (Low to High Usage)",
    hovermode="x unified",
    showlegend=False
)

st.plotly_chart(fig_bar, use_container_width=True)

# Visual 2: Full Portfolio Economics Table
st.markdown("### 📑 Portfolio Economics Ledger")
st.markdown("Breaks down the absolute financial exposure based on your specific customer distribution.")

format_dict = {
    'Baseline Bill': '£{:.2f}',
    'Simulated Bill': '£{:.2f}',
    'Net Margin Impact (£/cust)': '£{:.2f}',
    'Portfolio Impact (£)': '£{:,.0f}'
}
st.dataframe(df_results.style.format(format_dict).background_gradient(
    subset=['Net Margin Impact (£/cust)', 'Portfolio Impact (£)'], 
    cmap='RdYlGn'
), use_container_width=True)
