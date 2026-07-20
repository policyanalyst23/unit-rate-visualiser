import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# ==========================================
# 1. PAGE CONFIGURATION & METADATA
# ==========================================
st.set_page_config(page_title="Scenario Engine", layout="wide", page_icon="📈")
st.title("📈 Regulatory Consultation Scenario Engine")
st.markdown("Build and compare up to 4 distinct regulatory scenarios simultaneously. Edit the grid directly to alter existing allowances or add new rows for hypothetical policies.")

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

TAB_GROUPINGS = {
    "Wholesale": ['Direct Fuel Cost', 'Backwardation', 'Capacity Market', 'Contracts for Difference (CfD)'],
    "Policy": ['Renewables Obligation (RO)', 'Feed-in Tariff (FiT)', 'Energy Company Obligation (ECO)', 
               'Warm Home Discount (WHD)', 'Warm Home Discount (Unit Rate)', 'Assistance for Areas with High Electricity Distribution Costs', 
               'Network Charging Compensation', 'Nuclear Regulated Asset Base', 'Green Gas Levy (GGL)'],
    "Network": ['Transmission Network Use of System (TNUoS)', 'Distribution Use of System (DUoS)', 
                'Balancing Services Use of System (BSUoS)', 'Gas Distribution', 'Gas Transmission'],
    "OPEX": ['Operating Costs (Legacy)', 'Core Operating Costs', 'Debt-Related Costs', 'Industry Charges', 
             'Earnings Before Interest and Tax', 'Smart Metering Net Cost Change', 'Headroom Allowance Percentage'],
    "Other Costs": ['Adjustment Allowance', 'Payment Method Uplift (Fixed)', 'Payment Method Uplift (Variable)', 'Levelisation']
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
BUCKETS = ["Wholesale", "Policy", "Network", "OPEX", "Other Costs"]

# ==========================================
# 2. DATA LOADING
# ==========================================
@st.cache_data
def load_baseline_data():
    files = [
        'Cleaned_Price_Cap_Data.csv', 
        'wholesale_allowances_cleaned.csv', 
        'policy_costs_cleaned.csv', 
        'network_costs_cleaned.csv'
    ]
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
# 3. SIDEBAR FILTERS
# ==========================================
st.sidebar.header("1. Global Settings")
fuel_options = ["Dual Fuel", "Electricity Single-Rate", "Electricity Multi-Register", "Gas"]
selected_fuel = st.sidebar.selectbox("Fuel Type Profile", options=fuel_options)

payment_options = ["Direct Debit", "Standard Credit", "PPM"]
selected_payment = st.sidebar.selectbox("Payment Method", options=payment_options)

st.sidebar.divider()
st.sidebar.header("2. TDCV Settings")
is_dual_fuel = (selected_fuel == "Dual Fuel")

if is_dual_fuel:
    custom_tdcv_elec = st.sidebar.number_input("New TDCV (Electricity)", value=DEFAULT_TDCV["Electricity Single-Rate"], step=100)
    custom_tdcv_gas = st.sidebar.number_input("New TDCV (Gas)", value=DEFAULT_TDCV["Gas"], step=100)
    target_fuels = ['Electricity Single-Rate', 'Gas']
else:
    baseline_tdcv = DEFAULT_TDCV.get(selected_fuel, 2900)
    custom_tdcv = st.sidebar.number_input(f"New TDCV ({selected_fuel})", value=baseline_tdcv, step=100)
    target_fuels = [selected_fuel]

# Filter baseline data
df_filtered = df_baseline[
    (df_baseline['Fuel Type'].isin(target_fuels)) & 
    ((df_baseline['Payment Method'] == selected_payment) | (df_baseline['Payment Method'] == 'All'))
].copy()

valid_allowances = [item for sublist in TAB_GROUPINGS.values() for item in sublist]
df_filtered = df_filtered[df_filtered['Allowance_Full'].isin(valid_allowances)]

def get_bucket(allowance_name):
    for bucket, allowances in TAB_GROUPINGS.items():
        if allowance_name in allowances:
            return bucket
    return "Other Costs"

df_filtered['Bucket'] = df_filtered['Allowance_Full'].apply(get_bucket)
df_filtered['Charge Type'] = df_filtered['Charge Type'].replace({'UR': 'Unit Rate', 'SC': 'Standing Charge'})
df_filtered = df_filtered.groupby(['Bucket', 'Allowance_Full', 'Charge Type', 'Fuel Type'], as_index=False)['Cost Value'].sum()

# ==========================================
# 4. INTERACTIVE SCENARIO BUILDER (GRID)
# ==========================================
st.markdown("### 🎛️ The Scenario Grid")
st.markdown("Double-click any cell in the Scenario columns to edit values. Click the bottom row to add a completely new policy.")

# Prepare the Editor DataFrame
editor_df = df_filtered[['Bucket', 'Allowance_Full', 'Charge Type', 'Fuel Type', 'Cost Value']].copy()
editor_df.rename(columns={'Allowance_Full': 'Allowance', 'Cost Value': 'Baseline (£)'}, inplace=True)
editor_df['Scenario 1 (£)'] = editor_df['Baseline (£)']
editor_df['Scenario 2 (£)'] = editor_df['Baseline (£)']
editor_df['Scenario 3 (£)'] = editor_df['Baseline (£)']
editor_df['Scenario 4 (£)'] = editor_df['Baseline (£)']
editor_df = editor_df.sort_values(['Bucket', 'Allowance', 'Fuel Type']).reset_index(drop=True)

# Render the Data Editor
edited_df = st.data_editor(
    editor_df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    disabled=['Baseline (£)'], 
    column_config={
        "Bucket": st.column_config.SelectboxColumn("Bucket", options=BUCKETS, required=True),
        "Allowance": st.column_config.TextColumn("Allowance Name", required=True),
        "Charge Type": st.column_config.SelectboxColumn("Charge Type", options=["Standing Charge", "Unit Rate"], required=True),
        "Fuel Type": st.column_config.SelectboxColumn("Fuel Type", options=["Electricity Single-Rate", "Gas"], required=True) if is_dual_fuel else st.column_config.TextColumn("Fuel Type", disabled=True),
        "Baseline (£)": st.column_config.NumberColumn("Baseline (£)", format="£%.2f"),
        "Scenario 1 (£)": st.column_config.NumberColumn("Scenario 1 (£)", format="£%.2f"),
        "Scenario 2 (£)": st.column_config.NumberColumn("Scenario 2 (£)", format="£%.2f"),
        "Scenario 3 (£)": st.column_config.NumberColumn("Scenario 3 (£)", format="£%.2f"),
        "Scenario 4 (£)": st.column_config.NumberColumn("Scenario 4 (£)", format="£%.2f")
    }
)

# Fill NaNs if a user adds a new row and leaves some columns blank
edited_df = edited_df.fillna({'Baseline (£)': 0, 'Scenario 1 (£)': 0, 'Scenario 2 (£)': 0, 'Scenario 3 (£)': 0, 'Scenario 4 (£)': 0})

# ==========================================
# 5. TDCV MATH & CALCULATIONS
# ==========================================
def apply_tdcv_scaling(row, val_col):
    if row['Charge Type'] == 'Unit Rate':
        if is_dual_fuel:
            if row['Fuel Type'] == 'Gas':
                return row[val_col] * (custom_tdcv_gas / DEFAULT_TDCV['Gas'])
            else:
                return row[val_col] * (custom_tdcv_elec / DEFAULT_TDCV['Electricity Single-Rate'])
        else:
            return row[val_col] * (custom_tdcv / baseline_tdcv)
    return row[val_col]

columns_to_scale = ['Baseline (£)', 'Scenario 1 (£)', 'Scenario 2 (£)', 'Scenario 3 (£)', 'Scenario 4 (£)']
scaled_df = edited_df.copy()

for col in columns_to_scale:
    scaled_df[col] = scaled_df.apply(lambda r: apply_tdcv_scaling(r, col), axis=1)

# ==========================================
# 6. VISUALISATION (SCENARIO COMPARISON)
# ==========================================
st.divider()
st.markdown("### 📊 Scenario Impact Analysis")

# Macro Totals
totals = scaled_df[columns_to_scale].sum()

col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
col_m1.metric("Baseline Total", f"£{totals['Baseline (£)']:,.2f}")
col_m2.metric("Scenario 1", f"£{totals['Scenario 1 (£)']:,.2f}", delta=f"£{totals['Scenario 1 (£)'] - totals['Baseline (£)']:,.2f}")
col_m3.metric("Scenario 2", f"£{totals['Scenario 2 (£)']:,.2f}", delta=f"£{totals['Scenario 2 (£)'] - totals['Baseline (£)']:,.2f}")
col_m4.metric("Scenario 3", f"£{totals['Scenario 3 (£)']:,.2f}", delta=f"£{totals['Scenario 3 (£)'] - totals['Baseline (£)']:,.2f}")
col_m5.metric("Scenario 4", f"£{totals['Scenario 4 (£)']:,.2f}", delta=f"£{totals['Scenario 4 (£)'] - totals['Baseline (£)']:,.2f}")

chart_col1, chart_col2 = st.columns(2)

# Chart 1: Stacked Bar (SC vs UR)
with chart_col1:
    charge_agg = scaled_df.groupby('Charge Type')[columns_to_scale].sum()
    
    fig_stack = go.Figure()
    sc_vals = charge_agg.loc['Standing Charge'] if 'Standing Charge' in charge_agg.index else [0]*5
    ur_vals = charge_agg.loc['Unit Rate'] if 'Unit Rate' in charge_agg.index else [0]*5
    
    x_labels = ['Baseline', 'Scenario 1', 'Scenario 2', 'Scenario 3', 'Scenario 4']
    
    fig_stack.add_trace(go.Bar(name='Standing Charge', x=x_labels, y=sc_vals, marker_color='#a855f7'))
    fig_stack.add_trace(go.Bar(name='Unit Rate', x=x_labels, y=ur_vals, marker_color='#14b8a6'))
    
    fig_stack.update_layout(title="Total Bill: Standing Charge vs Unit Rate", barmode='stack', yaxis_title="Annualised Cost (£)", hovermode="x unified")
    st.plotly_chart(fig_stack, use_container_width=True)

# Chart 2: Net Variance from Baseline
with chart_col2:
    fig_var = go.Figure()
    variances = [
        totals['Scenario 1 (£)'] - totals['Baseline (£)'],
        totals['Scenario 2 (£)'] - totals['Baseline (£)'],
        totals['Scenario 3 (£)'] - totals['Baseline (£)'],
        totals['Scenario 4 (£)'] - totals['Baseline (£)']
    ]
    var_labels = ['Scenario 1', 'Scenario 2', 'Scenario 3', 'Scenario 4']
    colors = ['#10b981' if v < 0 else '#ef4444' for v in variances]
    
    fig_var.add_trace(go.Bar(
        x=var_labels, y=variances, 
        marker_color=colors,
        hovertemplate="<b>%{x}</b><br>Net Change: £%{y:.2f}<extra></extra>"
    ))
    
    fig_var.update_layout(title="Total Net Variance vs Baseline", yaxis_title="Change in Cost (£)", hovermode="x unified")
    st.plotly_chart(fig_var, use_container_width=True)
