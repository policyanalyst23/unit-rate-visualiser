import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Page Configuration & Password Protection
st.set_page_config(page_title="Price Cap Component Tracker", layout="wide")

# Simple password lock to prevent unauthorized viewing if someone guesses the app URL
password = st.text_input("Enter password to view tracker:", type="password")
if password != st.secrets["app_password"]:
    st.warning("Please enter the correct password to view the dashboard.")
    st.stop() # Stops the rest of the app from loading

st.title("⚡ Dynamic UK Energy Price Cap Tracker")
st.write("Secure live data feed active. Use the slider to change periods.")

# 2. Securely Fetch Live Data via the Obscured CSV Link
@st.cache_data(ttl=600) # Checks the Google Sheet for updates every 10 minutes
def load_data():
    # PASTE YOUR SECURE CSV LINK HERE:
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSTOf7APKDB3BONwv-T4tBi5mh0dMMsH_ERFQFgihpOc_SfrjEXGH-cYG71yV6KdQ/pub?gid=344411272&single=true&output=csv"
    
    # Read the data and drop any accidentally blank rows
    data = pd.read_csv(csv_url)
    return data.dropna(subset=["Period"])

df = load_data()

# 3. Create the Interactive Slider
periods = df["Period"].unique().tolist()
selected_period = st.select_slider("Select Price Cap Period:", options=periods)

filtered_df = df[df["Period"] == selected_period].copy()

# 4. Data Preparation for Visualisation
# Scale unit rates so they are visible next to standing charges on the same chart
def scale_values(row):
    if row['Charge Type'] == 'Unit Rate':
        return row['Cost Value'] * 1000 
    return row['Cost Value']

filtered_df['Visualisation Value'] = filtered_df.apply(scale_values, axis=1)
filtered_df['Category'] = filtered_df['Fuel'] + " - " + filtered_df['Charge Type']

# 5. Build the Stacked Column Chart
st.markdown("### Component Breakdown: Standing Charge vs Unit Rate")

fig = px.bar(
    filtered_df, 
    x="Category", 
    y="Visualisation Value", 
    color="Component",       
    barmode="stack",         
    title=f"Cost Stack Breakdown for {selected_period}",
    labels={"Visualisation Value": "Comparative Value (SC in £/yr, UR scaled)", "Category": "Fuel & Charge Type"},
    color_discrete_sequence=px.colors.qualitative.Pastel
)

fig.update_layout(xaxis_title="", yaxis_title="Relative Value", legend_title_text="Allowance Component", plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, use_container_width=True)

# 6. Add Data Table for Transparency
st.markdown("### Underlying Data Figures")
display_df = filtered_df.pivot_table(index=["Fuel", "Charge Type", "Component"], values="Cost Value", aggfunc="sum").reset_index()
st.dataframe(display_df, use_container_width=True)
