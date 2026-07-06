import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# 1. Page Configuration & Password Protection
st.set_page_config(page_title="Price Cap Component Tracker", layout="wide")

password = st.text_input("Enter password to view tracker:", type="password")
if password != st.secrets["app_password"]:
    st.warning("Please enter the correct password to view the dashboard.")
    st.stop()

st.title("⚡ Dynamic UK Energy Price Cap Tracker")
st.write("Percentage breakdown of the Standing Charge and Unit Rate cost stacks.")

# 2. Fetch Local Data from GitHub
@st.cache_data
def load_data():
    data = pd.read_csv("Dashboard_Data - Sheet1.csv")
    
    # THE NUCLEAR CLEANING STEP:
    # 1. Convert the column to string text
    data['Cost Value'] = data['Cost Value'].astype(str)
    
    # 2. Replace accounting dashes (and variations of dashes) with '0'
    data['Cost Value'] = data['Cost Value'].replace(['-', '–', '—'], '0')
    
    # 3. Regex: Delete absolutely everything that IS NOT a number, decimal, or minus sign
    data['Cost Value'] = data['Cost Value'].str.replace(r'[^\d.-]', '', regex=True)
    
    # 4. If the cell is now completely empty, make it a '0'
    data['Cost Value'] = data['Cost Value'].replace('', '0')
    
    # 5. Convert to pure numbers!
    data['Cost Value'] = pd.to_numeric(data['Cost Value'], errors='coerce').fillna(0.0)
    
    return data.dropna(subset=["Period"])

df = load_data()

# 3. Create the Interactive Slider
periods = df["Period"].unique().tolist()
selected_period = st.select_slider("Select Price Cap Period:", options=periods)

filtered_df = df[df["Period"] == selected_period].copy()

# 4. Data Preparation for a 100% Stacked Bar Chart
filtered_df['Category'] = filtered_df['Fuel'] + " - " + filtered_df['Charge Type']

# Calculate the total sum for each Category
category_totals = filtered_df.groupby('Category')['Cost Value'].transform('sum')

# Calculate the percentage securely (avoids divide-by-zero errors)
# np.where tells Python: "If the total is 0, make the percentage 0. Otherwise, do the math."
filtered_df['Percentage'] = np.where(
    category_totals == 0, 
    0, 
    (filtered_df['Cost Value'] / category_totals) * 100
)

# 5. Build the 100% Stacked Column Chart
st.markdown("### Component Breakdown: Percentage of Total")

fig = px.bar(
    filtered_df, 
    x="Category", 
    y="Percentage", 
    color="Component",       
    barmode="stack",         
    title=f"Cost Stack Breakdown ({selected_period})",
    labels={"Percentage": "Percentage of Total (%)", "Category": "Fuel & Charge Type"},
    color_discrete_sequence=px.colors.qualitative.Pastel,
    custom_data=["Cost Value"] 
)

# Customise the hover pop-up
fig.update_traces(
    hovertemplate="<b>%{color}</b><br>" +
                  "Share of Stack: %{y:.1f}%<br>" +
                  "Absolute Value: %{customdata[0]:.4f}<extra></extra>"
)

# Lock the Y-axis to 100%
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
