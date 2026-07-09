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

# ALL_TABS helper variable for events that span across the whole dashboard
ALL_TABS = ["Wholesale", "Policy", "Network", "OPEX", "Other Costs"]

POLICY_EVENTS = [
    {"date": "2022-06-23", "category": ["Wholesale"], "text": "Updated CfD methodology (dynamic negative recovery)"},
    {"date": "2022-08-04", "category": ["Wholesale"], "text": "Wholesale Cost Adjustment (+£46 for SVT demand)"},
    {"date": "2023-02-17", "category": ["OPEX"], "text": "COVID-19 True-Up Process (+£11 bad debt)"},
    {"date": "2023-02-27", "category": ["Policy"], "text": "ECO+ / GBIS allowance introduced"},
    {"date": "2023-08-25", "category": ["OPEX"], "text": "EBIT hybrid model (+£10)"},
    {"date": "2023-08-25", "category": ["OPEX"], "text": "ASC Bad Debt (+£8.77) for PPM"},
    {"date": "2023-08-25", "category": ["Wholesale"], "text": "Technical changes regarding inflation calculations and UIG allocation"},
    {"date": "2024-02-23", "category": ["OPEX"], "text": "Debt Float (+£28) introduced"},
    {"date": "2024-02-23", "category": ["Other Costs"], "text": "Standing Charge Levelisation (PPM -£49, DD +£10)"},
    {"date": "2024-08-23", "category": ["OPEX"], "text": "ASC Bad Debt Allowance extended"},
    {"date": "2025-02-25", "category": ["Policy"], "text": "Network Charging Compensation (NCC) (+£3)"},
    {"date": "2025-05-23", "category": ["OPEX"], "text": "Enduring OPEX framework replaces debt floats (-£8 avg)"},
    {"date": "2025-08-25", "category": ["Wholesale"], "text": "Interim UIG Allowance updated (+£4.30)"},
    {"date": "2025-10-24", "category": ["Policy"], "text": "WHD Scheme Expansion Cost (+£7)"},
    {"date": "2025-11-21", "category": ["Policy"], "text": "nRAB Allowance (+£14) for Sizewell C"},
    {"date": "2025-11-21", "category": ["Wholesale"], "text": "GCF adj (~+£5.10 impact) & Deadband removed"},
    {"date": "2025-11-21", "category": ALL_TABS, "text": "Lowered Typical Domestic Consumption Values (TDCV)"},
    {"date": "2025-12-09", "category": ["Policy"], "text": "WHD shifted from standing charge to unit rate"}
]

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

# Standardize messy fuel names across all datasets to prevent jagged line graphs
FUEL_MAPPING = {
    'Electricity Single Rate': 'Electricity Single-Rate',
    'Electricity- Single-Rate': 'Electricity Single-Rate',
    'Electricity - Single-Rate': 'Electricity Single-Rate',
    'Electricity - Multi-Register': 'Electricity Multi-Register',
    'Electricity Multi Register': 'Electricity Multi-Register',
    'Non-PPM gas': 'Gas',
    'Gas': 'Gas',
    'Dual Fuel': 'Dual Fuel (implied)',
    'Dual Fuel (implied)': 'Dual Fuel (implied)'
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
            
            # A. SCRUB WHITESPACES FIRST: Strip hidden spaces from key columns
            for col in ['Fuel Type', 'Charge Type', 'Payment Method', 'Allowance']:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
            
            # B. Apply Standardization Mappings
            if 'Fuel Type' in df.columns:
                df['Fuel Type'] = df['Fuel Type'].replace(FUEL_MAPPING)
                
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
                
            # If payment method is entirely missing or was converted to string 'nan', set to 'All'
            if 'Payment Method' not in df.columns or df['Payment Method'].isnull().all() or (df['Payment Method'] == 'nan').all():
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
        
        # Scrub whitespaces here too
        for col in ['Fuel Type', 'Charge Type', 'Payment Method']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                
        if 'Fuel Type' in df.columns:
            df['Fuel Type'] = df['Fuel Type'].replace(FUEL_MAPPING)
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
selected_charge = st.sidebar.selectbox("Charge Type (Note: Some allowances are exclusive to SC or UR)", options=charge_types)

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

    # Strict, exact matching to prevent jagged graph lines
    filtered = df_master[(df_master['Fuel Type'] == selected_fuel) & 
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
        bench_data = df_bench[(df_bench['Fuel Type'] == selected_fuel) & 
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

    # --- Policy Events specific to this Tab ---
    show_events = st.checkbox(f"Show {tab_title} Policy Events (Hover over stars for details)", value=True, key=f"chk_{tab_title}")
    if show_events:
        date_to_events = {}
        # Group events by date that match this specific tab
        for event in POLICY_EVENTS:
            if tab_title in event["category"]:
                event_date = pd.to_datetime(event["date"])
                if start_date <= event_date <= end_date:
                    if event_date not in date_to_events:
                        date_to_events[event_date] = []
                    date_to_events[event_date].append(event["text"])
        
        event_dates, event_texts = [], []
        for e_date, texts in date_to_events.items():
            event_dates.append(e_date)
            # Create a clean bulleted list if there are multiple events on the same day
            bullet_points = "<br>".join([f"• {t}" for t in texts])
            event_texts.append(f"{e_date.strftime('%d %b %Y')}<br>{bullet_points}")
            
        if event_dates:
            y_min = chart_data['Cost Value'].min() if not chart_data.empty else 0
            star_y = 0 if y_min >= 0 else y_min
            
            fig.add_trace(
                go.Scatter(
                    x=event_dates, 
                    y=[star_y] * len(event_dates),
                    mode='markers',
                    marker=dict(symbol='star', size=16, color='red', line=dict(width=1, color='darkred')),
                    name='Policy Events',
                    text=event_texts,
                    hovertemplate="<b>📌 Policy Event</b><br>%{text}<extra></extra>",
                    showlegend=True
                ),
                secondary_y=False
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
