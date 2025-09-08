import streamlit as st
import pandas as pd
import altair as alt
import numpy as np

# ----------------------------
# Page + theme
# ----------------------------
st.set_page_config(
    page_title="New York Population • 2010–2019",
    page_icon="🗽",
    layout="wide",
    initial_sidebar_state="expanded",
)
alt.theme.enable("dark")   # Altair 5+

# ----------------------------
# Load NST-EST2019 data (your path)
# ----------------------------
df_raw = pd.read_csv('data/nst-est2019-alldata.csv')

# Keep ONLY states (SUMLEV 40); we'll compute US totals separately
df_states = df_raw[df_raw['SUMLEV'] == 40].copy()

# Identify population columns (POPESTIMATE2010..2019)
pop_cols = [c for c in df_states.columns if c.startswith('POPESTIMATE20')]

# Reshape to tidy long form
keep_cols = ['NAME', 'STATE'] + pop_cols
df_long = (
    df_states[keep_cols]
    .melt(id_vars=['NAME', 'STATE'], var_name='year', value_name='population')
)
df_long['year'] = df_long['year'].str.extract(r'(\d{4})').astype(int)
df_long = df_long.rename(columns={'NAME': 'state'})

# ----------------------------
# Build NY-only and comparison frames
# ----------------------------
ny = df_long[df_long['state'] == 'New York'][['year', 'population']].sort_values('year').reset_index(drop=True)

# US (sum of states; Puerto Rico not in SUMLEV 40 here, so this is 50-states + DC)
us = (
    df_long.groupby('year', as_index=False)['population']
    .sum()
    .rename(columns={'population': 'us_population'})
)

# Rank per year for NY (1 = largest)
df_long['rank'] = df_long.groupby('year')['population'].rank(ascending=False, method='min')
ny_rank = df_long[df_long['state'] == 'New York'][['year', 'rank']].copy()

# Merge US + rank into NY time series
ny = ny.merge(us, on='year', how='left').merge(ny_rank, on='year', how='left')
ny['share_of_us_%'] = (ny['population'] / ny['us_population']) * 100

# YoY change and % change
ny['yoy_change'] = ny['population'].diff()
ny['yoy_pct'] = ny['population'].pct_change() * 100

# Peak and CAGR (2010→2019)
base_pop = ny.loc[ny['year'] == 2010, 'population'].iloc[0]
last_pop = ny.loc[ny['year'] == 2019, 'population'].iloc[0]
years_span = 9  # 2010 -> 2019
cagr = ( (last_pop / base_pop) ** (1/years_span) - 1 ) * 100

peak_row = ny.loc[ny['population'].idxmax()]
peak_pop = int(peak_row['population'])
peak_year = int(peak_row['year'])
abs_change_2010_2019 = int(last_pop - base_pop)

# Optional tiny comparison vs CA, TX, FL
compare_states = ['California', 'Texas', 'Florida', 'New York']
comp = (
    df_long[df_long['state'].isin(compare_states)][['state', 'year', 'population', 'rank']]
    .sort_values(['state','year'])
)

# ----------------------------
# Helpers
# ----------------------------
def fmt_num(n: float) -> str:
    sign = '-' if n < 0 else ''
    n = abs(int(n))
    if n >= 1_000_000:
        return f"{sign}{n/1_000_000:.1f} M" if n % 1_000_000 else f"{sign}{n//1_000_000} M"
    return f"{sign}{n//1_000} K"

# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    st.title("🗽 New York Population")
    st.caption("Vintage 2019 estimates (Census NST-EST2019)")

    # Toggle to show mini compare chart
    show_compare = st.checkbox("Show mini comparison vs CA/TX/FL", value=True)

# ----------------------------
# Layout
# ----------------------------
col = st.columns((2.2, 4.0, 2.3), gap='large')

# --- Left: Key metrics ---
with col[0]:
    st.markdown("### New York — Key Metrics")

    m1, m2 = st.columns(2)
    with m1:
        st.metric("Peak population", fmt_num(peak_pop), help=f"Peak year: {peak_year}")
    with m2:
        st.metric("2010→2019 CAGR", f"{cagr:.2f}%")

    m3, m4 = st.columns(2)
    with m3:
        st.metric("2010→2019 change", fmt_num(abs_change_2010_2019),
                  delta=f"{fmt_num(abs_change_2010_2019)} vs 2010")
    with m4:
        # latest share (2019)
        latest_share = ny.loc[ny['year'] == 2019, 'share_of_us_%'].iloc[0]
        st.metric("Share of US (2019)", f"{latest_share:.2f}%")

    st.markdown("#### Rank by Year (1 = largest)")
    rank_chart = (
        alt.Chart(ny)
        .mark_line(point=True)
        .encode(
            x=alt.X('year:O', title='Year'),
            y=alt.Y('rank:Q', scale=alt.Scale(domain=[ny['rank'].max(), 1])),  # invert so 1 is on top
            tooltip=['year', alt.Tooltip('rank:Q', format='.0f')]
        ).properties(height=220)
    )
    st.altair_chart(rank_chart, use_container_width=True)

# --- Middle: NY Trend + YoY change ---
with col[1]:
    st.markdown("### New York Population Trend (2010–2019)")
    line = (
        alt.Chart(ny)
        .mark_line(point=True)
        .encode(
            x=alt.X('year:O', title='Year'),
            y=alt.Y('population:Q', title='Population'),
            tooltip=['year', alt.Tooltip('population:Q', format=',')]
        )
        .properties(height=300)
    )
    st.altair_chart(line, use_container_width=True)

    st.markdown("### Year-over-Year Change")
    bars = (
        alt.Chart(ny)
        .mark_bar()
        .encode(
            x=alt.X('year:O', title='Year'),
            y=alt.Y('yoy_change:Q', title='Δ Population vs prior year'),
            color=alt.condition(alt.datum.yoy_change >= 0, alt.value('#27AE60'), alt.value('#E74C3C')),
            tooltip=['year', alt.Tooltip('yoy_change:Q', format=',')]
        )
        .properties(height=220)
    )
    st.altair_chart(bars, use_container_width=True)

# --- Right: Comparison (optional) + Raw table ---
with col[2]:
    if show_compare:
        st.markdown("### Mini Compare (CA/TX/FL vs NY)")
        bump = (
            alt.Chart(comp)
            .mark_line(point=True)
            .encode(
                x=alt.X('year:O', title='Year'),
                y=alt.Y('rank:Q', title='Rank', scale=alt.Scale(domain=[comp['rank'].max(), 1])),
                color=alt.Color('state:N', legend=alt.Legend(title="State")),
                tooltip=['state', 'year', 'rank', alt.Tooltip('population:Q', format=',')]
            )
            .properties(height=240)
        )
        # labels on 2019
        last_year = comp['year'].max()
        last_pts = comp[comp['year'] == last_year]
        labels = (
            alt.Chart(last_pts)
            .mark_text(align='left', dx=5)
            .encode(x='year:O', y='rank:Q', text='state:N', color='state:N')
        )
        st.altair_chart(bump + labels, use_container_width=True)

    st.markdown("### New York Data (2010–2019)")
    ny_table = ny[['year', 'population', 'yoy_change', 'share_of_us_%', 'rank']].copy()
    ny_table['population'] = ny_table['population'].map(lambda v: f"{int(v):,}")
    ny_table['yoy_change'] = ny_table['yoy_change'].fillna(0).map(lambda v: f"{int(v):,}")
    ny_table['share_of_us_%'] = ny_table['share_of_us_%'].map(lambda v: f"{v:.2f}%")
    ny_table['rank'] = ny_table['rank'].astype(int)
    st.dataframe(
        ny_table,
        hide_index=True,
        use_container_width=True,
        column_order=['year', 'population', 'yoy_change', 'share_of_us_%', 'rank'],
    )

# ----------------------------
# Footer
# ----------------------------
st.caption("Source: U.S. Census Bureau — State Population Totals, Vintage 2019 (NST-EST2019)")
