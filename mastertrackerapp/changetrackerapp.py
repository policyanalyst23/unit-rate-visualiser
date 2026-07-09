import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Ofgem Price Cap Dashboard", layout="wide", page_icon="⚡")
st.title("⚡ Ofgem Energy Price Cap Visualizer")
st.markdown("Explore how wholesale, policy, network, operating, and other costs have evolved over time.")

# ==========================================
# 2. DICTIONARIES & METADATA
# ==========================================
ALLOWANCE_DICT = {
    'DF': 'Direct Fuel Cost',
    'CM': 'Capacity Market',
    'AA': 'Adjustment Allowance',
    'PC': 'Policy Costs',
    'NC': 'Network Costs',
    'OC': 'Operating Costs (Legacy)',
    'CO': 'Core Operating Costs',
    'SMNCC': 'Smart Metering Net Cost Change',
    'IC': 'Industry Charges',
    'PAAC': 'Payment Method Uplift (Fixed)',
    'PAP': 'Payment Method Uplift (Variable)',
    'DRC': 'Debt-Related Costs',
    'EBIT': 'Earnings Before Interest and Tax',
    'HAP': 'Headroom Allowance Percentage',
    'RO': 'Renewables Obligation (RO)',
    'FiT': 'Feed-in Tariff (FiT)',
    'ECO': 'Energy Company Obligation (ECO)',
    'WHD': 'Warm Home Discount (WHD)',
    'WHD (unit rate)': 'Warm Home Discount (Unit Rate)',
    'AAHEDC': 'Assistance for Areas with High Electricity Distribution Costs',
    'NCC': 'Network Charging Compensation',
    'nRAB': 'Nuclear Regulated Asset Base',
    'CfD': 'Contracts for Difference (CfD)',
    'Backwardation': 'Backwardation',
    'Gas Transmission': 'Gas Transmission',
    'Gas Distribution': 'Gas Distribution',
    'TNUoS': 'Transmission Network Use of System (TNUoS)',
    'BSUoS': 'Balancing Services Use of System (BSUoS)',
    'DUoS': 'Distribution Use of System (DUoS)',
    'Levelisation': 'Levelisation'
}

POLICY_EVENTS = {
    "2022-06-23": "Updated CfD methodology (dynamic negative recovery)",
    "2022-08-04": "Wholesale Cost Adj (+£46 for SVT demand)",
    "2023-02-17": "COVID-19 True-Up Process (+£11 bad debt)",
    "2023-02-27": "ECO+ / GBIS allowance introduced",
    "2023-08-25": "EBIT hybrid model (+£10) & ASC Bad Debt (+£8.77)",
    "2024-02-23": "Debt Float (+£28) & SC Levelisation",
    "2024-08-23": "ASC Bad Debt Allowance extended",
    "2025-02-25": "Network Charging Compensation (+£3)",
    "2025-05-23": "Enduring OPEX framework replaces debt floats (-£8 avg)",
    "2025-08-25": "Interim UIG Allowance updated (+£4.30)",
    "2025-10-24": "WHD Scheme Expansion Cost (+£7)",
    "2025-11-21": "nRAB Allowance (+£14), GCF adj, Deadband removed",
    "2025-12-09": "WHD shifted from SC to unit rate"
}

TAB_GROUPINGS = {
    "Wholesale": ['Direct Fuel Cost', 'Backwardation', 'Capacity Market', 'Contracts for Difference (CfD)'],
    "Policy": ['Renewables Obligation (RO)', 'Feed-in Tariff (FiT)', 'Energy Company Obligation (ECO)', 
               'Warm Home Discount (WHD)', 'Warm Home Discount (Unit Rate)', 'Assistance for Areas with High Electricity Distribution Costs', 
               'Network Charging Compensation', 'Nuclear Regulated Asset Base'],
    "Network": ['Transmission Network Use of System (TNUoS)', 'Distribution Use of System (DUoS)', 
                'Balancing Services Use of System (BSUoS)', 'Gas Distribution', 'Gas Transmission'],
    "OPEX": ['Operating Costs (Legacy)', 'Core Operating Costs', 'Debt-Related Costs', 'Industry Charges', 
             'Earnings Before Interest and Tax', 'Smart Metering Net Cost Change', 'Headroom Allowance Percentage'],
    "Other Costs": ['Adjustment Allowance', 'Payment Method Uplift (Fixed)', 'Payment Method Uplift (Variable)', 'Levelisation']
}

# ==========================================
# 3. DATA LOADING & UNIFICATION
# ==========================================
@st.cache_data
def load_and_combine_data(folder_path):
    files = {
        'opex': 'Cleaned_Price_Cap_Data.csv',
        'whole': 'wholesale_allowances_cleaned.csv',
        'policy': 'policy_costs_cleaned.csv',
        'net': 'network_costs_cleaned.csv'
    }
    
    dfs = []
    for key, file in files.items():
        filepath = os.path.join(folder_path, file)
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            
            if 'Charge Type' in df.columns:
                df['Charge Type'] = df['Charge Type'].replace({'UR': 'Unit Rate', 'SC': 'Standing Charge'})
                
            if 'Start Date' not in df.columns and 'Cap Period' in df.columns:
                df['Start'] = df['Cap Period'].astype(str).str.split('-').str[0].str.strip()
                df['Start Date'] = pd.to_datetime(df['Start'], format='%B %Y', errors='coerce').fillna(
                                   pd.to_datetime(df['Start'], format='%b %Y', errors='coerce'))
            elif 'Start Date' in df.columns:
                df['Start Date'] = pd.to_datetime(df['Start Date'], errors='coerce')
                
            if 'Allowance' in df.columns:
                df['Allowance_Full'] = df['Allowance'].map(ALLOWANCE_DICT).fillna(df['Allowance'])
                
            if 'Payment Method' not in df.columns or df['Payment Method'].isnull().all():
                df['Payment Method'] = 'All' 
                
            dfs.append(df)
        else:
            st.sidebar.warning(f"Missing file: {file}")
            
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()

@st.cache_data
def load_benchmark(folder_path):
    filepath = os.path.join(folder_path, 'total_bill_cleaned.csv')
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        df['Start Date'] = pd.to_datetime(df['Start Date'], errors='coerce')
        return df
    return pd.DataFrame()

folder_path = 'mastertrackerapp/'
df_master = load_and_combine_data(folder_path)
df_bench = load_benchmark(folder_path)

# ==========================================
# 4. GLOBAL SIDEBAR CONTROLS
# ==========================================
st.sidebar.header("Global Filters")
fuel_types = ["Electricity Single-Rate", "Electricity Multi-Register", "Gas", "Dual Fuel (implied)"]
payment_methods = ["Direct Debit", "Standard Credit", "PPM"]
charge_types = ["Standing Charge", "Unit Rate"]

selected_fuel = st.sidebar.selectbox("Fuel Type", options=fuel_types)
selected_payment = st.sidebar.selectbox("Payment Method", options=payment_methods)
selected_charge = st.sidebar.selectbox("Charge Type", options=charge_types)

st.sidebar.divider()
st.sidebar.header("Benchmark Overlay")
selected_benchmark = st.sidebar.selectbox(
    "Compare trendline against (Right Y-Axis):", 
    options=["None", "Total SC", "Total UR", "Total Bill"]
)

# ==========================================
# 5. RENDER TAB CONTENT FUNCTION
# ==========================================
def render_tab_content(tab_title):
    if df_master.empty:
        st.error("Master dataset is empty. Please check your data files.")
        return

    filtered = df_master[(df_master['Fuel Type'].str.contains(selected_fuel.split()[0], na=False, case=False)) & 
                         (df_master['Charge Type'] == selected_charge)]
    filtered = filtered[(filtered['Payment Method'] == selected_payment) | (filtered['Payment Method'] == 'All')]
    
    tab_allowances = TAB_GROUPINGS[tab_title]
    filtered = filtered[filtered['Allowance_Full'].isin(tab_allowances)]

    if filtered.empty:
        st.info(f"No {tab_title} data available for the selected Fuel Type, Payment Method, and Charge Type.")
        return

    # --- UI: Check and Uncheck Allowances ---
    available_allowances = sorted(filtered['Allowance_Full'].unique())
    selected_allowances = st.multiselect(
        f"Select {tab_title} Allowances to view:", 
        options=available_allowances, 
        default=available_allowances
    )
    
    if not selected_allowances:
        st.warning("Please select at least one allowance from the dropdown.")
        return

    # --- UI: Select Slider for Time Range ---
    unique_dates = sorted(filtered['Start Date'].dropna().unique())
    if len(unique_dates) > 1:
        date_to_label = {d: filtered[filtered['Start Date'] == d]['Cap Period'].iloc[0] for d in unique_dates}
        label_to_date = {v: k for k, v in date_to_label.items()}
        sorted_labels = [date_to_label[d] for d in unique_dates]
        
        st.markdown(f"**Filter Time Range for {tab_title}:**")
        selected_range = st.select_slider(
            "Time Range",
            options=sorted_labels,
            value=(sorted_labels[0], sorted_labels[-1]),
            key=f"slider_{tab_title}",
            label_visibility="collapsed"
        )
        start_date = label_to_date[selected_range[0]]
        end_date = label_to_date[selected_range[1]]
    else:
        start_date = unique_dates[0]
        end_date = unique_dates[0]

    chart_data = filtered[filtered['Allowance_Full'].isin(selected_allowances)]
    chart_data = chart_data[(chart_data['Start Date'] >= start_date) & (chart_data['Start Date'] <= end_date)]
    chart_data = chart_data.sort_values('Start Date')

    # --- UI: Visualization Toggle ---
    chart_style = st.radio(
        "Chart Style (Left Axis):", 
        ["Stacked Bar", "Grouped Bar", "Line Graph"], 
        horizontal=True,
        key=f"radio_{tab_title}"
    )

    # --- Build Plotly Figure with Secondary Y-Axis ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    for allowance in selected_allowances:
        allowance_data = chart_data[chart_data['Allowance_Full'] == allowance]
        custom_hover = "<b>%{customdata}</b><br>Value: £%{y:.2f}<extra></extra>"
        
        if chart_style == "Line Graph":
            fig.add_trace(
                go.Scatter(
                    x=allowance_data['Start Date'], y=allowance_data['Cost Value'], 
                    mode='lines+markers', name=allowance,
                    customdata=allowance_data['Cap Period'], hovertemplate=custom_hover
                ), 
                secondary_y=False
            )
        else:
            fig.add_trace(
                go.Bar(
                    x=allowance_data['Start Date'], y=allowance_data['Cost Value'], 
                    name=allowance,
                    customdata=allowance_data['Cap Period'], hovertemplate=custom_hover
                ), 
                secondary_y=False
            )

    if chart_style == "Stacked Bar":
        fig.update_layout(barmode='stack')
    elif chart_style == "Grouped Bar":
        fig.update_layout(barmode='group')

    if selected_benchmark != "None" and not df_bench.empty:
        bench_data = df_bench[(df_bench['Fuel Type'].str.contains(selected_fuel.split()[0], na=False, case=False)) & 
                              (df_bench['Payment Method'] == selected_payment) & 
                              (df_bench['Charge Type'] == selected_benchmark)]
        if not bench_data.empty:
            bench_data = bench_data[(bench_data['Start Date'] >= start_date) & (bench_data['Start Date'] <= end_date)]
            bench_data = bench_data.sort_values('Start Date')
            
            fig.add_trace(
                go.Scatter(
                    x=bench_data['Start Date'], y=bench_data['Cost Value'],
                    mode='lines+markers', name=f"Benchmark: {selected_benchmark}",
                    line=dict(color='black', width=3, dash='dash'),
                    customdata=bench_data['Cap Period'], 
                    hovertemplate="<b>%{customdata}</b><br>Benchmark: £%{y:.2f}<extra></extra>"
                ),
                secondary_y=True
            )

    show_events = st.checkbox("Show Policy Events Overlay", value=True, key=f"chk_{tab_title}")
    if show_events:
        for date_str, event_text in POLICY_EVENTS.items():
            event_date = pd.to_datetime(date_str)
            if event_date >= start_date and event_date <= end_date:
                fig.add_vline(
                    x=event_date, line_width=1.5, line_dash="dot", line_color="red",
                    annotation_text="ℹ️", annotation_position="top left",
                    annotation_hovertext=f"{date_str}: {event_text}"
                )
    
    fig.update_xaxes(title_text="Timeline", tickformat="%b %Y", dtick="M3")
    fig.update_yaxes(title_text="Allowance Value (£)", secondary_y=False)
    
    if selected_benchmark != "None":
        fig.update_yaxes(title_text=f"{selected_benchmark} (£)", secondary_y=True, showgrid=False)
        
    fig.update_layout(
        title=f"{tab_title} Allowances Over Time",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # --- Data Download Button ---
    csv_data = chart_data.to_csv(index=False).encode('utf-8')
    st.download_button(
        label=f"📥 Download Filtered {tab_title} Data (CSV)",
        data=csv_data,
        file_name=f"ofgem_{tab_title.lower().replace(' ', '_')}_data.csv",
        mime="text/csv",
        key=f"download_{tab_title}"
    )

# ==========================================
# 6. MAIN APP: TABS
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏭 Wholesale", "📜 Policy", "🔌 Network", "🏢 OPEX", "🧩 Other Costs"])

with tab1:
    render_tab_content("Wholesale")
with tab2:
    render_tab_content("Policy")
with tab3:
    render_tab_content("Network")
with tab4:
    render_tab_content("OPEX")
with tab5:
    render_tab_content("Other Costs")

# ==========================================
# 7. FOOTER
# ==========================================
st.divider()
st.markdown("*Last updated to reflect July 2026 Price cap values. Historical reference begins from October to December 2022 period.*")
