import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import statsmodels.api as sm
import json, requests

st.set_page_config(page_title="Home", page_icon="🏠",layout="wide")

st.title("Power Outage")

data = pd.read_csv("data/power_outage.csv")
states = sorted(data['state'].unique())
states.insert(0, 'All')
col1, col2, col3 = st.columns(3)
years = ["All",2014,2015,2016,2017, 2018, 2019, 2020, 2021, 2022, 2023]
years_filter = col3.multiselect("Select Year(s)", options=years, default=['All'])
states_filter = col1.multiselect('Select State(s)', options=states,default=['All'])
# print(years,type(years))
st.markdown(" ")
if 'All' in states_filter:
    states_filter = states[1:]  # all except 'All'

if 'All' in years_filter:
    years_filter = years[1:]  # all except 'All'

data['Year'] = pd.to_datetime(data['start_datetime']).dt.year
# Filter data
data_filtered = data[data['Year'].isin(years_filter)]
data_filtered = data_filtered[data_filtered['state'].isin(states_filter)]

df = data_filtered.copy()
df['Year'] = pd.to_datetime(df['start_datetime']).dt.year

#KPIs
events_by_year = df.groupby('Year').size()
if len(events_by_year) >= 2:
    latest_year = events_by_year.index.max()
    prev_year = latest_year - 1
    if prev_year in events_by_year.index:
        yoy = ((events_by_year.loc[latest_year] - events_by_year.loc[prev_year]) /
               max(events_by_year.loc[prev_year], 1)) * 100
        delta_fmt = f"{yoy:+.1f}%"
    else:
        delta_fmt = "N/A"
else:
    delta_fmt = "N/A"

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Events", len(data_filtered))
col2.metric("Total Customers Affected", f"{data_filtered['max_customers'].sum():,}")
col3.metric("Avg Duration (hrs)", round(data_filtered['duration'].mean(), 2))
col4.metric("Year-over-Year Change", delta_fmt, delta_color="inverse")

#Line Plots
col1, col2 = st.columns(2)

df = data_filtered.copy()
df['month'] = pd.to_datetime(df['start_datetime']).dt.to_period('M').dt.to_timestamp()

monthly_counts = (
    df.groupby('month')
      .size()
      .reset_index(name='events')
)

fig = px.line(monthly_counts, x='month', y='events',
              markers=True, title='Events Over Time (Monthly)')
col1.plotly_chart(fig, use_container_width=True)

df = data_filtered.copy()
df['month'] = pd.to_datetime(df['start_datetime']).dt.to_period('M').dt.to_timestamp()

monthly_customers = (
    df.groupby(['month','Event Type'])['max_customers']
      .sum()
      .reset_index()
)

fig = px.area(monthly_customers, x='month', y='max_customers',
              color='Event Type', groupnorm=None,
              title='Total Customers Affected Over Time (by Event Type)')
col2.plotly_chart(fig, use_container_width=True)

# Bar Plots
top_counties = (
    data_filtered.groupby(['state','county'])['max_customers']
    .sum()
    .reset_index()
    .sort_values('max_customers', ascending=False)
    .head(10)
)

fig = px.bar(top_counties, x='max_customers', y='county',
             color='state', orientation='h',
             title='Top 10 Counties by Customers Affected',
             labels={'max_customers':'Customers Affected','county':'County'})
fig.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig, use_container_width=True)


by_type = (
    data_filtered.groupby('Event Type')
    .agg(events=('Event Type','size'),
         customers=('max_customers','sum'))
    .reset_index()
)

tab1, tab2 = st.tabs(["By Events", "By Customers"])
with tab1:
    fig1 = px.bar(by_type.sort_values('events', ascending=False),
                  x='Event Type', y='events',
                  title='Events by Type')
    st.plotly_chart(fig1, use_container_width=True)

with tab2:
    fig2 = px.bar(by_type.sort_values('customers', ascending=False),
                  x='Event Type', y='customers',
                  title='Customers Affected by Type')
    st.plotly_chart(fig2, use_container_width=True)
# Box Plot
fig = px.box(data_filtered, x='Event Type', y='duration',
             points='outliers', title='Event Duration by Type (hrs)',
             labels={'duration':'Hours'})
st.plotly_chart(fig, use_container_width=True)

# Scatter Plot
fig = px.scatter(data_filtered, x='duration', y='max_customers',
                 color='Event Type', hover_data=['state','county','start_datetime'],
                 trendline='ols', title='Duration vs Customers Affected')
st.plotly_chart(fig, use_container_width=True)

# Heatmap
df = data_filtered.copy()
df['Year'] = pd.to_datetime(df['start_datetime']).dt.year
df['Month'] = pd.to_datetime(df['start_datetime']).dt.month

grid = (df.groupby(['Year','Month'])
          .size()
          .reset_index(name='events'))

fig = px.density_heatmap(grid, x='Month', y='Year', z='events',
                         title='Seasonality Heatmap: Events by Month & Year',
                         nbinsx=12, color_continuous_scale='Viridis')
st.plotly_chart(fig, use_container_width=True)


# Map

state_agg = (data_filtered.groupby('state_codes')['max_customers']
             .sum().reset_index())

# Plotly expects state codes (e.g., 'TX', 'CA') in 'locations' with locationmode='USA-states'
fig = px.choropleth(
    state_agg, locations='state_codes', color='max_customers',
    locationmode='USA-states', scope='usa',
    color_continuous_scale='Reds',
    title='Total Customers Affected by State'
)
st.plotly_chart(fig, use_container_width=True)

@st.cache_data
def load_counties_geojson():
    # Plotly reference file (public)
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    return requests.get(url, timeout=10).json()

counties = load_counties_geojson()

county_agg = (data_filtered
              .dropna(subset=['fips'])
              .assign(fips=lambda d: d['fips'].astype(str).str.zfill(5))
              .groupby(['fips','state','county'])['max_customers']
              .sum().reset_index())

fig = px.choropleth(
    county_agg,
    geojson=counties,
    locations='fips',
    color='max_customers',
    scope='usa',
    color_continuous_scale='Reds',
    hover_name='county',
    labels={'max_customers':'Customers'}
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(title='Total Customers Affected by County (FIPS)')
st.plotly_chart(fig, use_container_width=True)


# Maps with Lat and Long
# import pydeck as pdk

# points = data_filtered.dropna(subset=['lat','lon']).copy()
# points['size'] = (points['max_customers'].fillna(0) ** 0.5)  # scale marker size

# layer = pdk.Layer(
#     "ScatterplotLayer",
#     points,
#     get_position='[lon, lat]',
#     get_radius='size * 1000',
#     pickable=True,
#     get_fill_color='[200, 30, 0, 160]'
# )
# view_state = pdk.ViewState(latitude=37.5, longitude=-96, zoom=3.5)
# r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{county}, {state}\nCustomers: {max_customers}"})
# st.pydeck_chart(r)
