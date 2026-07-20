import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# ==========================================
# 1. PAGE CONFIGURATION & METADATA
# ==========================================
st.set_page_config(page_title="Policy Sandbox", layout="wide", page_icon="🛠️")
st.title("🛠️ Price Cap Policy Sandbox")
st.markdown("Simulate how changes to individual allowances or brand-new policies impact the total annualised bill.")

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

# The strict list of granular allowances (no aggregate 'PC' or 'NC' buckets)
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

# Standardize messy fuel names to cast a wide net across all CSV files
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

# ==========================================
# 2. DATA LOADING & FILTERING
# ==========================================
@st.cache_data
def load_baseline_data():
    files = [
        'Cleaned_Price_Cap_Data.csv', 
        'wholesale_allowances_cleaned.csv', 
        'policy_costs_cleaned.csv', 
        'network_costs_cleaned.csv'
    ]
    
    # Let's check both the current folder and the 'mastertrackerapp' folder
    possible_folders = ['', 'mastertrackerapp/']
    
    dfs = []
    for f in files:
        file_loaded = False
        for folder in possible_folders:
            filepath = os.path.join(folder, f)
            if os.path.exists(filepath):
                df = pd.read_csv(filepath)
                
                # Scrub Whitespaces first to prevent mapping errors
                for col in ['Fuel Type', 'Charge Type', 'Payment Method', 'Allowance', 'Cap Period']:
                    if col in df.columns:
                        df[col] = df[col].astype(str).str.strip()
                
                # Standardize Fuel Types so filtering works across all sheets
                if 'Fuel Type' in df.columns:
                    df['Fuel Type'] = df['Fuel Type'].replace(FUEL_MAPPING)
                    
                # Map Allowance codes to readable names
                if 'Allowance' in df.columns:
                    df['Allowance_Full'] = df['Allowance'].map(ALLOWANCE_DICT).fillna(df['Allowance'])
                
                # Fill missing Payment Methods for universal items (like Policy Costs)
                if 'Payment Method' not in df.columns or df['Payment Method'].isnull().all() or (df['Payment Method'] == 'nan').all():
                    df['Payment Method'] = 'All' 
                    
                # Parse Start Date to find the absolute latest period chronologically
                if 'Cap Period' in df.columns:
                    df['Temp_Start'] = df['Cap Period'].astype(str).str.split('-').str[0].str.strip()
                    df['Parsed_Date'] = pd.to_datetime(df['Temp_Start'], errors='coerce')
                    
                dfs.append(df)
                file_loaded = True
                break # Move to the next file if found
                
        if not file_loaded:
            st.sidebar.warning(f"Warning: Could not find {f}")
            
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        
        # --- DYNAMIC LATEST PERIOD LOCATOR ---
        # Find the absolute maximum start date in the entire dataset
        max_date = combined['Parsed_Date'].max()
        # Filter the dataset to ONLY include rows that match this max date (i.e. July 2026)
        latest_period_data = combined[combined['Parsed_Date'] == max_date].copy()
        
        return latest_period_data
        
    return pd.DataFrame()

df_baseline = load_baseline_data()

# ==========================================
# 3. SIDEBAR FILTERS
# ==========================================
st.sidebar.header("1. Global Settings")
fuel_options = ["Electricity Single-Rate", "Electricity Multi-Register", "Gas"]
selected_fuel = st.sidebar.selectbox("Fuel Type", options=fuel_options)

payment_options = ["Direct Debit", "Standard Credit", "PPM"]
selected_payment = st.sidebar.selectbox("Payment Method", options=payment_options)

st.sidebar.divider()
st.sidebar.header("2. TDCV Settings")
st.sidebar.markdown("Adjust the Typical Domestic Consumption Value to see how scaling affects the annualised Unit Rate costs.")
baseline_tdcv = DEFAULT_TDCV.get(selected_fuel, 2900)
custom_tdcv = st.sidebar.number_input(f"New TDCV ({selected_fuel})", value=baseline_tdcv, step=100)

# Filter data to selection
df_filtered = df_baseline[
    (df_baseline['Fuel Type'] == selected_fuel) & 
    ((df_baseline['Payment Method'] == selected_payment) | (df_baseline['Payment Method'] == 'All'))
].copy()

# Lock down valid granular allowances (removes aggregate 'PC' / 'NC' double counts)
valid_allowances = [item for sublist in TAB_GROUPINGS.values() for item in sublist]
df_filtered = df_filtered[df_filtered['Allowance_Full'].isin(valid_allowances)]

def get_bucket(allowance_name):
    for bucket, allowances in TAB_GROUPINGS.items():
        if allowance_name in allowances:
            return bucket
    return "Other Costs"

df_filtered['Bucket'] = df_filtered['Allowance_Full'].apply(get_bucket)
df_filtered['Charge Type'] = df_filtered['Charge Type'].replace({'UR': 'Unit Rate', 'SC': 'Standing Charge'})

# Group to handle duplicates if files overlap
df_filtered = df_filtered.groupby(['Bucket', 'Allowance_Full', 'Charge Type'], as_index=False)['Cost Value'].sum()

# ==========================================
# 4. UI: ALLOWANCE ADJUSTMENTS
# ==========================================
st.markdown("### 🎛️ Modify Allowances")
st.markdown("Edit existing baseline allowances or inject new policy costs below. Unit Rates (UR) will automatically scale with your chosen TDCV.")

simulated_values = []
buckets = ["Wholesale", "Policy", "Network", "OPEX", "Other Costs"]

col1, col2 = st.columns(2)

for i, bucket in enumerate(buckets):
    bucket_data = df_filtered[df_filtered['Bucket'] == bucket].sort_values('Allowance_Full')
    target_col = col1 if i % 2 == 0 else col2
    
    with target_col.expander(f"{bucket} Allowances", expanded=(i==0)):
        if not bucket_data.empty:
            for _, row in bucket_data.iterrows():
                allowance = row['Allowance_Full']
                charge_type = row['Charge Type']
                base_val = float(row['Cost Value'])
                
                # Pre-fill with the exact baseline cost
                new_val = st.number_input(
                    f"{allowance} ({charge_type})", 
                    value=base_val, 
                    step=1.0, 
                    key=f"{allowance}_{charge_type}_{bucket}"
                )
                
                simulated_values.append({
                    "Bucket": bucket,
                    "Allowance": allowance,
                    "Charge Type": charge_type,
                    "Baseline Value": base_val,
                    "Simulated Value": new_val
                })
        else:
            st.info(f"No {bucket} data available for this configuration.")

st.divider()

# --- Custom Policy Injection ---
st.markdown("### ➕ Add a New Policy Allowance")
with st.expander("Inject New Regulatory Cost", expanded=True):
    new_pol_col1, new_pol_col2, new_pol_col3, new_pol_col4 = st.columns(4)
    new_pol_name = new_pol_col1.text_input("Policy Name", value="New Green Levy")
    new_pol_bucket = new_pol_col2.selectbox("Categorise As:", options=buckets, index=1)
    new_pol_charge = new_pol_col3.selectbox("Charge Type", options=["Standing Charge", "Unit Rate"])
    new_pol_val = new_pol_col4.number_input("Annualised Cost Value (£)", value=0.0, step=1.0)
    
    if new_pol_val != 0.0:
        simulated_values.append({
            "Bucket": new_pol_bucket,
            "Allowance": new_pol_name,
            "Charge Type": new_pol_charge,
            "Baseline Value": 0.0,
            "Simulated Value": new_pol_val
        })

# ==========================================
# 5. TDCV MATH & CALCULATIONS
# ==========================================
df_sim = pd.DataFrame(simulated_values)

if df_sim.empty:
    st.warning("No data available to simulate. Check the sidebar warnings for missing files.")
    st.stop()

def apply_tdcv_scaling(row, val_col):
    """Scales Unit Rate based on the difference between standard and custom TDCV"""
    if row['Charge Type'] == 'Unit Rate':
        return row[val_col] * (custom_tdcv / baseline_tdcv)
    return row[val_col]

df_sim['Baseline Adjusted'] = df_sim.apply(lambda r: apply_tdcv_scaling(r, 'Baseline Value'), axis=1)
df_sim['Simulated Adjusted'] = df_sim.apply(lambda r: apply_tdcv_scaling(r, 'Simulated Value'), axis=1)

base_total = df_sim['Baseline Adjusted'].sum()
sim_total = df_sim['Simulated Adjusted'].sum()
diff = sim_total - base_total

# ==========================================
# 6. VISUALISATION
# ==========================================
st.markdown("### 📊 Bill Impact Analysis")

# Dynamically display the Cap Period name so you know exactly which one it caught
display_period = df_baseline['Cap Period'].iloc[0] if not df_baseline.empty else "Latest Period"

met_col1, met_col2, met_col3 = st.columns(3)
met_col1.metric(f"Baseline Annualised Bill ({display_period})", f"£{base_total:,.2f}")
met_col2.metric("Simulated Annualised Bill", f"£{sim_total:,.2f}", delta=f"£{diff:,.2f}")
met_col3.metric("TDCV Scaling Applied", f"{custom_tdcv} kWh")

df_agg = df_sim.groupby('Bucket')[['Baseline Adjusted', 'Simulated Adjusted']].sum().reset_index()

# Build Grouped Bar Chart
fig_bar = go.Figure()

fig_bar.add_trace(go.Bar(
    x=df_agg['Bucket'], y=df_agg['Baseline Adjusted'],
    name=f'Baseline ({display_period})', marker_color='#94a3b8',
    hovertemplate="<b>%{x}</b><br>Baseline: £%{y:.2f}<extra></extra>"
))

fig_bar.add_trace(go.Bar(
    x=df_agg['Bucket'], y=df_agg['Simulated Adjusted'],
    name='Simulated', marker_color='#3b82f6',
    hovertemplate="<b>%{x}</b><br>Simulated: £%{y:.2f}<extra></extra>"
))

fig_bar.update_layout(
    title="Cost Breakdown by Bucket: Baseline vs Simulated",
    barmode='group',
    yaxis_title="Annualised Cost (£)",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig_bar, use_container_width=True)

# Build Waterfall Chart for precise variances
st.markdown("### 💧 Detailed Variance (What Changed)")
variance_df = df_sim[df_sim['Baseline Adjusted'] != df_sim['Simulated Adjusted']].copy()

if not variance_df.empty:
    variance_df['Variance'] = variance_df['Simulated Adjusted'] - variance_df['Baseline Adjusted']
    
    # Format labels for clarity
    labels = variance_df.apply(lambda r: f"{r['Allowance']} ({r['Charge Type']})", axis=1).tolist()
    labels.append("Net Change")
    
    fig_waterfall = go.Figure(go.Waterfall(
        name="Variance",
        orientation="v",
        measure=["relative"] * len(variance_df) + ["total"],
        x=labels,
        y=variance_df['Variance'].tolist() + [diff],
        textfont={"family": "Arial", "size": 13},
        textposition="outside",
        connector={"line": {"color": "rgb(63, 63, 63)", "width": 2}}
    ))

    fig_waterfall.update_layout(
        title="Impact of Adjustments on Total Bill",
        showlegend=False,
        yaxis_title="Change in Cost (£)",
        xaxis_tickangle=-45
    )
    st.plotly_chart(fig_waterfall, use_container_width=True)
else:
    st.info("No cost variances detected. Adjust the allowances or TDCV above to see the breakdown.")
