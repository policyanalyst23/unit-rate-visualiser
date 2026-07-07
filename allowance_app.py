import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Page Config (Only needed if this is a standalone file)
# st.set_page_config(page_title="Allowance Breakdown", layout="wide")

st.title("📊 Allowance Breakdown Tracker")
st.write("Deep dive into the underlying costs making up the price cap.")

# 2. Load the cleaned long-form data
@st.cache_data
def load_allowances():
    # Make sure this matches the exact name of your uploaded CSV
    return pd.read_csv("Cleaned_Price_Cap_Data.csv")

allowances_df = load_allowances()

# 3. Create Top-Level Filters (Fuel and Charge Type)
col1, col2 = st.columns(2)
with col1:
    selected_fuel = st.selectbox("Select Fuel Type:", options=allowances_df["Fuel Type"].unique())
with col2:
    selected_charge = st.selectbox("Select Charge Type:", options=allowances_df["Charge Type"].unique())

st.markdown("---")

# 4. Create the 3 Payment Method Tabs
payment_methods = allowances_df["Payment Method"].unique()
tabs = st.tabs(list(payment_methods))

# 5. Loop through each tab and draw the specific stacked bar chart
for i, pm in enumerate(payment_methods):
    with tabs[i]:
        # Filter the dataframe for the specific tab and dropdown selections
        filtered_df = allowances_df[
            (allowances_df["Fuel Type"] == selected_fuel) &
            (allowances_df["Charge Type"] == selected_charge) &
            (allowances_df["Payment Method"] == pm)
        ].copy()
        
        if filtered_df.empty:
            st.warning(f"No data available for {pm} with the current filters.")
        else:
            # Build the Stacked Bar Chart
            fig = px.bar(
                filtered_df,
                x="Cap Period",
                y="Cost Value",
                color="Allowance", # This stacks the bars by allowance category
                title=f"{pm}: {selected_charge} Breakdown ({selected_fuel})",
                labels={"Cost Value": "Cost (£)", "Cap Period": "Regulatory Period"},
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            
            # Remove background gridlines for a cleaner corporate look
            fig.update_layout(
                barmode='stack',
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='lightgrey')
            )
            
            st.plotly_chart(fig, use_container_width=True)
