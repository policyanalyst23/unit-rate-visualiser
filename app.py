import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Page Configuration & Password Protection
st.set_page_config(page_title="Price Cap Component Tracker", layout="wide")

password = st.text_input("Enter password to view tracker:", type="password")
if password != st.secrets["app_password"]:
    st.warning("Please enter the correct password to view the dashboard.")
    st.stop()

st.title("⚡ Dynamic UK Energy Price Cap Tracker")
st.write("Percentage breakdown of the Standing Charge and Unit Rate cost stacks.")

# 2. Securely Fetch Live Data
@st.cache_data(ttl=600) 
def load_data():
    # REPLACE WITH YOUR ACTUAL PUBLISHED CSV LINK:
    # csv_url = "https://docs.google.com/spreadsheets/d/e/YOUR_UNIQUE_LINK_HERE/pub?gid=123&single=true&output=csv"
    
    data = pd.read_csv("Dashboard_Data - Sheet1.csv")
    return data.dropna(subset=["Period"])

df = load_data()

# 3. Create the Interactive Slider
periods = df["Period"].unique().tolist()
selected_period = st.select_slider("Select Price Cap Period:", options=periods)

filtered_df = df[df["Period"] == selected_period].copy()

# 4. Data Preparation for a 100% Stacked Bar Chart
# First, create the category labels for the X-axis
filtered_df['Category'] = filtered_df['Fuel'] + " - " + filtered_df['Charge Type']

# Next, calculate the total sum for each Category (e.g., Total Elec Unit Rate)
# We use 'transform' so the total is appended to every relevant row
category_totals = filtered_df.groupby('Category')['Cost Value'].transform('sum')

# Now, calculate the percentage contribution of each component to its category total
filtered_df['Percentage'] = (filtered_df['Cost Value'] / category_totals) * 100

# 5. Build the 100% Stacked Column Chart
st.markdown("### Component Breakdown: Percentage of Total")

# Plot using the new 'Percentage' column instead of the raw value
fig = px.bar(
    filtered_df, 
    x="Category", 
    y="Percentage", 
    color="Component",       
    barmode="stack",         
    title=f"Cost Stack Breakdown ({selected_period})",
    labels={"Percentage": "Percentage of Total (%)", "Category": "Fuel & Charge Type"},
    color_discrete_sequence=px.colors.qualitative.Pastel,
    custom_data=["Cost Value"] # We pass the raw value here so we can show it when hovering
)

# Customise the hover pop-up to show both the % and the actual monetary figure
fig.update_traces(
    hovertemplate="<b>%{color}</b><br>" +
                  "Share of Stack: %{y:.1f}%<br>" +
                  "Absolute Value: %{customdata[0]:.4f}<extra></extra>"
)

# Lock the Y-axis to 100% so it looks neat
fig.update_layout(
    xaxis_title="", 
    yaxis_title="Percentage (%)", 
    yaxis_range=[0, 100],
    legend_title_text="Allowance Component", 
    plot_bgcolor="rgba(0,0,0,0)"
)

st.plotly_chart(fig, use_container_width=True)

# 6. Add Data Table for Transparency
st.markdown("### Underlying Data Figures (Absolute Values)")
display_df = filtered_df.pivot_table(index=["Fuel", "Charge Type", "Component"], values="Cost Value", aggfunc="sum").reset_index()
st.dataframe(display_df, use_container_width=True)
