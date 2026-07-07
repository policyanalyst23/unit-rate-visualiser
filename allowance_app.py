import streamlit as st
import pandas as pd
import plotly.express as px

st.title("📊 Allowance Breakdown Tracker")
st.write("Deep dive into the underlying costs making up the standing charge and unit rate by payment method and fuel type.")

# 1. Load the cleaned long-form data AND sort chronologically
@st.cache_data
def load_allowances():
    df = pd.read_csv("Cleaned_Price_Cap_Data.csv")
    
    # THE FIX: Split the text by the hyphen, grab the first date, and convert to a real datetime object
    df["Start_Date"] = pd.to_datetime(df["Cap Period"].str.split(" - ").str[0], errors="coerce")
    
    # Sort the entire database chronologically by this new hidden column
    df = df.sort_values("Start_Date")
    return df

allowances_df = load_allowances()

# 2. Create Top-Level Filters (Fuel and Charge Type)
col1, col2 = st.columns(2)
with col1:
    selected_fuel = st.selectbox("Select Fuel Type:", options=allowances_df["Fuel Type"].unique())
with col2:
    selected_charge = st.selectbox("Select Charge Type:", options=allowances_df["Charge Type"].unique())

st.markdown("---")

# 3. THE NEW TIMELINE RANGE SLIDER
# Because we sorted the dataframe in Step 1, .unique() now extracts them in perfect chronological order!
cap_periods = allowances_df["Cap Period"].unique().tolist()

st.write("### ⏱️ Adjust Timeline")
start_period, end_period = st.select_slider(
    "Select Cap Period Range:",
    options=cap_periods,
    value=(cap_periods[0], cap_periods[-1]) 
)

start_idx = cap_periods.index(start_period)
end_idx = cap_periods.index(end_period)
valid_periods = cap_periods[start_idx:end_idx+1]

st.markdown("---")

# Logic to figure out all the periods that sit between the user's start and end choices
start_idx = cap_periods.index(start_period)
end_idx = cap_periods.index(end_period)
valid_periods = cap_periods[start_idx:end_idx+1]

st.markdown("---")

# 4. Create the 3 Payment Method Tabs
payment_methods = allowances_df["Payment Method"].unique()
tabs = st.tabs(list(payment_methods))

# 5. Loop through each tab and draw the specific stacked bar chart
for i, pm in enumerate(payment_methods):
    with tabs[i]:
        # Filter the dataframe for Fuel, Charge Type, Payment Method, AND the selected Timeline
        filtered_df = allowances_df[
            (allowances_df["Fuel Type"] == selected_fuel) &
            (allowances_df["Charge Type"] == selected_charge) &
            (allowances_df["Payment Method"] == pm) &
            (allowances_df["Cap Period"].isin(valid_periods)) # Apply the timeline filter
        ].copy()
        
        if filtered_df.empty:
            st.warning(f"No data available for {pm} within this timeframe.")
        else:
            # Build the Stacked Bar Chart
            fig = px.bar(
                filtered_df,
                x="Cap Period",
                y="Cost Value",
                color="Allowance", 
                title=f"{pm}: {selected_charge} Breakdown ({selected_fuel})",
                labels={"Cost Value": "Cost (£)", "Cap Period": "Regulatory Period"},
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            
            # Remove background gridlines for a cleaner corporate look
            # Remove background gridlines for a cleaner corporate look
            fig.update_layout(
                barmode='stack',
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(
                    showgrid=False,
                    categoryorder='array',       # THE FIX: Tells Plotly to use a custom order
                    categoryarray=valid_periods  # THE FIX: Feeds it our perfectly sorted timeline list
                ),
                yaxis=dict(showgrid=True, gridcolor='lightgrey')
            )
            
            st.plotly_chart(fig, use_container_width=True)
