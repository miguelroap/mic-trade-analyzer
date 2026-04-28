"""
==============================================================================
  MIC Trade Analyzer — Streamlit Dashboard
==============================================================================
  Lee mic_data.parquet desde GitHub (raw URL) y renderiza el dashboard
  completo con 7 secciones interactivas.

  Despliegue:
    1. Sube mic_data.parquet a tu repo de GitHub
    2. Ajusta PARQUET_URL con la URL raw del archivo
    3. streamlit run mic_streamlit_app.py
    ó despliega en Streamlit Community Cloud apuntando a este script.

  Dependencias (requirements.txt):
    streamlit>=1.35
    pandas>=2.0
    pyarrow>=14
    plotly>=5.20
    requests>=2.31
==============================================================================
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests, io

# ==============================================================================
# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
# ==============================================================================

PARQUET_URL = (
    "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/mic_data.parquet"
)

# Paleta coherente con el dashboard HTML
CLR = px.colors.qualitative.Plotly
GREEN   = "#3fb950"
RED     = "#f78166"
YELLOW  = "#e3b341"
BLUE    = "#58a6ff"
BG      = "#0d1117"
SURFACE = "#161b22"

st.set_page_config(
    page_title="MIC Trade Analyzer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS mínimo para oscurecer el fondo y afinar tipografía
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background:#0d1117; }
  [data-testid="stSidebar"]          { background:#161b22; }
  [data-testid="stHeader"]           { background:#161b22; border-bottom:1px solid #30363d; }
  h1,h2,h3,h4 { color:#c9d1d9; }
  .metric-label { font-size:.7rem !important; }
  div[data-testid="stMetric"] label { font-size:.72rem; color:#8b949e; }
  div[data-testid="stMetric"] div[data-testid="stMetricValue"] { font-size:1.4rem; }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# ── CARGA DE DATOS ────────────────────────────────────────────────────────────
# ==============================================================================

@st.cache_data(ttl=3600, show_spinner="Cargando datos desde GitHub…")
def load_data(url: str) -> dict[str, pd.DataFrame]:
    """
    Descarga el Parquet desde GitHub y lo parte en subsets por _table.
    Cachéado 1 hora para no descargar en cada interacción.
    """
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_parquet(io.BytesIO(r.content))

    tables = {}
    for name in df['_table'].unique():
        tables[name] = df[df['_table'] == name].drop(columns='_table').reset_index(drop=True)
    return tables


@st.cache_data(ttl=3600, show_spinner=False)
def load_data_local(path: str) -> dict[str, pd.DataFrame]:
    """Alternativa para desarrollo local."""
    df = pd.read_parquet(path)
    tables = {}
    for name in df['_table'].unique():
        tables[name] = df[df['_table'] == name].drop(columns='_table').reset_index(drop=True)
    return tables


# ==============================================================================
# ── HELPERS ───────────────────────────────────────────────────────────────────
# ==============================================================================

def fmt_eur(v):   return f"{v:,.0f} €"
def fmt_mwh(v):   return f"{v:,.2f} MWh"
def fmt_price(v): return f"{v:,.2f} €/MWh"

def color_val(v):
    """Devuelve color verde/rojo según signo para métricas."""
    return GREEN if (v or 0) >= 0 else RED

def plotly_layout(title="", height=350, margin_l=60):
    return dict(
        title=dict(text=title, font=dict(size=13, color="#8b949e")),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9", size=11),
        margin=dict(t=36 if title else 12, b=48, l=margin_l, r=16),
        xaxis=dict(gridcolor="#21262d", zerolinecolor="#30363d"),
        yaxis=dict(gridcolor="#21262d", zerolinecolor="#30363d"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    )

def bar_colors(series):
    return [GREEN if v >= 0 else RED for v in series]


# ==============================================================================
# ── SECCIONES DEL DASHBOARD ───────────────────────────────────────────────────
# ==============================================================================

def section_overview(T):
    st.header("Overview")

    ag = T.get('by_agent', pd.DataFrame())
    if ag.empty:
        st.warning("Sin datos de agentes."); return

    total_sell_mwh = ag['Sell_MWh'].sum()
    total_buy_mwh  = ag['Buy_MWh'].sum()
    total_sell_c   = ag['Sell_Cash'].sum()
    total_buy_c    = ag['Buy_Cash'].sum()
    net_cash       = total_sell_c - total_buy_c
    total_opp      = ag['MIC_vs_MD_EUR'].sum() if 'MIC_vs_MD_EUR' in ag else 0
    n_agents       = len(ag)
    n_units        = len(T.get('by_unit', pd.DataFrame()))

    # KPIs
    c = st.columns(5)
    c[0].metric("Energía Vendida",  fmt_mwh(total_sell_mwh))
    c[1].metric("Energía Comprada", fmt_mwh(total_buy_mwh))
    c[2].metric("Balance Neto",     fmt_eur(net_cash),
                delta=f"{net_cash:+,.0f} €", delta_color="normal")
    c[3].metric("Beneficio vs MD",  fmt_eur(total_opp),
                delta=f"{total_opp:+,.0f} €", delta_color="normal")
    c[4].metric("Agentes / Unidades", f"{n_agents} / {n_units}")

    c2 = st.columns(2)
    avg_sell = total_sell_c / total_sell_mwh if total_sell_mwh else 0
    avg_buy  = total_buy_c  / total_buy_mwh  if total_buy_mwh  else 0
    c2[0].metric("P° Medio Venta",  fmt_price(avg_sell))
    c2[1].metric("P° Medio Compra", fmt_price(avg_buy))

    st.divider()

    col1, col2 = st.columns(2)

    # Balance neto top 15 agentes
    with col1:
        top15 = ag.sort_values('Net_Cash_EUR', ascending=False).head(15)
        fig = go.Figure(go.Bar(
            x=top15['Agent'], y=top15['Net_Cash_EUR'],
            marker_color=bar_colors(top15['Net_Cash_EUR']),
            hovertemplate="%{x}<br><b>%{y:,.0f} €</b><extra></extra>",
        ))
        fig.update_layout(**plotly_layout("Balance Neto por Agente — Top 15 (€)"))
        fig.update_xaxes(tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

    # Pie tecnología
    with col2:
        tech = T.get('by_tech', pd.DataFrame())
        if not tech.empty:
            tech['Total_MWh'] = tech['Sell_MWh'] + tech['Buy_MWh']
            fig = px.pie(tech, names='Technology', values='Total_MWh',
                         hole=.4, color_discrete_sequence=CLR)
            fig.update_layout(**plotly_layout("Volumen por Tecnología (MWh)"))
            fig.update_traces(textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)

    # MIC vs MD por agente
    with col3:
        if 'MIC_vs_MD_EUR' in ag.columns:
            opp = ag.sort_values('MIC_vs_MD_EUR', ascending=False).head(15)
            fig = go.Figure(go.Bar(
                x=opp['Agent'], y=opp['MIC_vs_MD_EUR'],
                marker_color=bar_colors(opp['MIC_vs_MD_EUR']),
                hovertemplate="%{x}<br><b>%{y:,.0f} €</b><extra></extra>",
            ))
            fig.update_layout(**plotly_layout("Beneficio MIC vs MD por Agente (€)"))
            fig.update_xaxes(tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

    # Precio medio venta vs compra
    with col4:
        ps = ag[ag['Sell_MWh'] > 0].copy()
        ps['P_Venta']  = ps['Sell_Cash'] / ps['Sell_MWh']
        ps['P_Compra'] = ps['Buy_Cash']  / ps['Buy_MWh'].replace(0, float('nan'))
        ps = ps.sort_values('Sell_Cash', ascending=False).head(12)
        fig = go.Figure()
        fig.add_bar(name="P° Venta",  x=ps['Agent'], y=ps['P_Venta'],
                    marker_color=GREEN)
        fig.add_bar(name="P° Compra", x=ps['Agent'], y=ps['P_Compra'],
                    marker_color=BLUE)
        fig.update_layout(**plotly_layout("Precio Medio Venta vs Compra (€/MWh)"),
                          barmode='group')
        fig.update_xaxes(tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)


def section_agents(T):
    st.header("Por Agente")
    ag = T.get('by_agent', pd.DataFrame())
    if ag.empty: st.warning("Sin datos."); return

    col1, col2 = st.columns(2)

    with col1:
        top20 = ag.sort_values('Sell_MWh', ascending=False).head(20)
        fig = go.Figure()
        fig.add_bar(name="Ventas",  x=top20['Agent'], y=top20['Sell_MWh'],
                    marker_color=GREEN)
        fig.add_bar(name="Compras", x=top20['Agent'], y=top20['Buy_MWh'],
                    marker_color=BLUE)
        fig.update_layout(**plotly_layout("Compras vs Ventas — Top 20 (MWh)"),
                          barmode='group')
        fig.update_xaxes(tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if 'MIC_vs_MD_EUR' in ag.columns:
            fig = px.scatter(
                ag,
                x='Net_Cash_EUR', y='MIC_vs_MD_EUR',
                text='Agent', size=ag['Sell_MWh'].clip(lower=1),
                color='Net_Cash_EUR', color_continuous_scale='RdYlGn',
                hover_name='Agent',
                labels={'Net_Cash_EUR':'Net Cash (€)','MIC_vs_MD_EUR':'MIC vs MD (€)'},
            )
            fig.add_hline(y=0, line_dash="dot", line_color="#30363d")
            fig.add_vline(x=0, line_dash="dot", line_color="#30363d")
            fig.update_traces(textposition='top center', textfont_size=9)
            fig.update_layout(**plotly_layout("Net Cash vs Beneficio MIC−MD (scatter)"),
                              coloraxis_showscale=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # Tabla
    st.subheader("Detalle por Agente")
    filt = st.text_input("Filtrar agente", key="ag_filter")
    disp = ag[ag['Agent'].str.contains(filt, case=False, na=False)] if filt else ag

    show_cols = ['Agent','Sell_MWh','Buy_MWh','Net_MWh',
                 'Sell_Cash','Buy_Cash','Net_Cash_EUR',
                 'Avg_Sell_Price','Avg_Buy_Price','MIC_vs_MD_EUR']
    show_cols = [c for c in show_cols if c in disp.columns]
    st.dataframe(
        disp[show_cols].style.format({
            'Sell_MWh':'.2f','Buy_MWh':'.2f','Net_MWh':'.2f',
            'Sell_Cash':',.0f','Buy_Cash':',.0f','Net_Cash_EUR':',.0f',
            'Avg_Sell_Price':'.2f','Avg_Buy_Price':'.2f','MIC_vs_MD_EUR':',.0f',
        }).map(lambda v: f"color:{GREEN}" if isinstance(v,(int,float)) and v>=0
               else f"color:{RED}" if isinstance(v,(int,float)) and v<0 else "",
               subset=[c for c in ['Net_Cash_EUR','MIC_vs_MD_EUR','Net_MWh'] if c in show_cols]),
        use_container_width=True, hide_index=True,
    )


def section_tech(T):
    st.header("Por Tecnología")
    tech = T.get('by_tech', pd.DataFrame())
    if tech.empty: st.warning("Sin datos."); return

    col1, col2 = st.columns(2)
    with col1:
        s = tech.sort_values('Net_Cash_EUR', ascending=False)
        fig = go.Figure(go.Bar(
            x=s['Technology'], y=s['Net_Cash_EUR'],
            marker_color=bar_colors(s['Net_Cash_EUR']),
            hovertemplate="%{x}<br><b>%{y:,.0f} €</b><extra></extra>",
        ))
        fig.update_layout(**plotly_layout("Cash Neto por Tecnología (€)"))
        fig.update_xaxes(tickangle=-25)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if 'MIC_vs_MD_EUR' in tech.columns:
            os_ = tech.sort_values('MIC_vs_MD_EUR', ascending=False)
            fig = go.Figure(go.Bar(
                x=os_['Technology'], y=os_['MIC_vs_MD_EUR'],
                marker_color=bar_colors(os_['MIC_vs_MD_EUR']),
                hovertemplate="%{x}<br><b>%{y:,.0f} €</b><extra></extra>",
            ))
            fig.update_layout(**plotly_layout("Beneficio MIC vs MD por Tecnología (€)"))
            fig.update_xaxes(tickangle=-25)
            st.plotly_chart(fig, use_container_width=True)

    show_cols = ['Technology','Sell_MWh','Buy_MWh','Net_MWh',
                 'Sell_Cash','Buy_Cash','Net_Cash_EUR','MIC_vs_MD_EUR']
    show_cols = [c for c in show_cols if c in tech.columns]
    st.dataframe(
        tech[show_cols].sort_values('Net_Cash_EUR', ascending=False)
        .style.format({c:',.0f' for c in show_cols if c not in ['Technology','Sell_MWh','Buy_MWh','Net_MWh']})
        .format({'Sell_MWh':'.2f','Buy_MWh':'.2f','Net_MWh':'.2f'}),
        use_container_width=True, hide_index=True,
    )


def section_units(T):
    st.header("Unidades de Oferta")
    unit = T.get('by_unit', pd.DataFrame())
    if unit.empty: st.warning("Sin datos."); return

    # Filtros sidebar ya aplicados globalmente; aquí filtros locales
    col_f1, col_f2, col_f3 = st.columns(3)
    txt   = col_f1.text_input("Filtrar unidad / agente", key="unit_txt")
    techs = ['Todas'] + sorted(unit['Technology'].dropna().unique().tolist())
    tech  = col_f2.selectbox("Tecnología", techs, key="unit_tech")
    sign  = col_f3.selectbox("Balance", ["Todos","Positivo","Negativo"], key="unit_sign")

    disp = unit.copy()
    if txt:  disp = disp[disp['Unit'].str.contains(txt,case=False,na=False) |
                         disp['Agent'].str.contains(txt,case=False,na=False)]
    if tech != 'Todas': disp = disp[disp['Technology'] == tech]
    if sign == 'Positivo': disp = disp[disp['Net_Cash_EUR'] >= 0]
    if sign == 'Negativo': disp = disp[disp['Net_Cash_EUR'] <  0]

    # Top 20 horizontal
    top20 = disp.sort_values('Net_Cash_EUR', ascending=False).head(20)
    fig = go.Figure(go.Bar(
        x=top20['Net_Cash_EUR'],
        y=top20.get('Unit_Name', top20['Unit']),
        orientation='h',
        marker_color=bar_colors(top20['Net_Cash_EUR']),
        hovertemplate="%{y}<br><b>%{x:,.0f} €</b><extra></extra>",
    ))
    fig.update_layout(**plotly_layout("Top 20 Unidades — Net Cash (€)", height=420, margin_l=150))
    st.plotly_chart(fig, use_container_width=True)

    show_cols = ['Unit','Unit_Name','Agent','Technology',
                 'Sell_MWh','Buy_MWh','Net_Cash_EUR','MIC_vs_MD_EUR']
    show_cols = [c for c in show_cols if c in disp.columns]
    st.dataframe(
        disp[show_cols].sort_values('Net_Cash_EUR', ascending=False)
        .style.format({'Sell_MWh':'.2f','Buy_MWh':'.2f',
                       'Net_Cash_EUR':',.0f','MIC_vs_MD_EUR':',.0f'}),
        use_container_width=True, hide_index=True,
    )


def section_monthly(T):
    st.header("Evolución Mensual")
    monthly = T.get('monthly_agent', pd.DataFrame())
    if monthly.empty: st.warning("Sin datos."); return

    agents = ['Todos'] + sorted(monthly['Agent'].unique().tolist())
    chosen = st.selectbox("Agente", agents, key="month_agent")

    data = monthly if chosen == 'Todos' else monthly[monthly['Agent'] == chosen]

    # Aggregate across agents if "Todos"
    byM = data.groupby('Month_Year').agg(
        Net_Cash_EUR =('Net_Cash_EUR','sum'),
        MIC_vs_MD_EUR=('MIC_vs_MD_EUR','sum'),
    ).reset_index().sort_values('Month_Year')

    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(go.Bar(
            x=byM['Month_Year'], y=byM['Net_Cash_EUR'],
            marker_color=bar_colors(byM['Net_Cash_EUR']),
            hovertemplate="%{x}<br><b>%{y:,.0f} €</b><extra></extra>",
        ))
        fig.update_layout(**plotly_layout("Net Cash Mensual (€)"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure(go.Scatter(
            x=byM['Month_Year'], y=byM['MIC_vs_MD_EUR'],
            mode='lines+markers', fill='tozeroy',
            line=dict(color=BLUE, width=2.5),
            marker=dict(size=8, color=BLUE),
            fillcolor='rgba(88,166,255,0.1)',
            hovertemplate="%{x}<br><b>%{y:,.0f} €</b><extra></extra>",
        ))
        fig.update_layout(**plotly_layout("MIC vs MD Mensual (€)"))
        st.plotly_chart(fig, use_container_width=True)

    # Heatmap agente × mes (solo en "Todos")
    if chosen == 'Todos':
        st.subheader("Heatmap Agente × Mes — Net Cash (€)")
        pivot = monthly.pivot_table(
            index='Agent', columns='Month_Year',
            values='Net_Cash_EUR', aggfunc='sum', fill_value=0,
        )
        fig = go.Figure(go.Heatmap(
            z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
            colorscale=[[0,RED],[0.5,SURFACE],[1,GREEN]],
            zmid=0,
            colorbar=dict(title='€', tickformat=',.0f'),
            hovertemplate="%{y}<br>%{x}<br><b>%{z:,.0f} €</b><extra></extra>",
        ))
        fig.update_layout(**plotly_layout("", height=max(300, len(pivot)*22+80),
                                          margin_l=120))
        st.plotly_chart(fig, use_container_width=True)


def section_target(T):
    st.header("Balance Objetivo")
    tgt = T.get('target_balance', pd.DataFrame())
    if tgt.empty: st.warning("Sin datos de unidades objetivo."); return

    units   = tgt['Unit_Name'].fillna(tgt['Unit']).unique().tolist()
    months  = sorted(tgt['Month_Year'].unique().tolist())
    pivot   = tgt.pivot_table(
        index='Unit_Name', columns='Month_Year',
        values='Net_Balance_EUR', aggfunc='sum', fill_value=0,
    )

    # Heatmap
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale=[[0,RED],[0.5,SURFACE],[1,GREEN]], zmid=0,
        colorbar=dict(title='€', tickformat=',.0f'),
        hovertemplate="%{y}<br>%{x}<br><b>%{z:,.0f} €</b><extra></extra>",
    ))
    fig.update_layout(**plotly_layout("Heatmap Balance Mensual Unidades Objetivo (€)",
                                      height=380, margin_l=170))
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    byUnit = tgt.groupby('Unit_Name').agg(
        Net_Balance_EUR=('Net_Balance_EUR','sum'),
        MIC_vs_MD_EUR  =('MIC_vs_MD_EUR',  'sum'),
    ).reset_index().sort_values('Net_Balance_EUR')

    with col1:
        fig = go.Figure(go.Bar(
            x=byUnit['Net_Balance_EUR'], y=byUnit['Unit_Name'],
            orientation='h',
            marker_color=bar_colors(byUnit['Net_Balance_EUR']),
            hovertemplate="%{y}<br><b>%{x:,.0f} €</b><extra></extra>",
        ))
        fig.update_layout(**plotly_layout("Balance Neto Acumulado (€)",
                                          margin_l=160))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if 'MIC_vs_MD_EUR' in byUnit.columns:
            fig = go.Figure(go.Bar(
                x=byUnit['MIC_vs_MD_EUR'], y=byUnit['Unit_Name'],
                orientation='h',
                marker_color=bar_colors(byUnit['MIC_vs_MD_EUR']),
                hovertemplate="%{y}<br><b>%{x:,.0f} €</b><extra></extra>",
            ))
            fig.update_layout(**plotly_layout("MIC vs MD Acumulado (€)",
                                              margin_l=160))
            st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        tgt[['Unit','Unit_Name','Month_Year','Net_Balance_EUR','MIC_vs_MD_EUR']]
        .sort_values(['Unit_Name','Month_Year'])
        .style.format({'Net_Balance_EUR':',.0f','MIC_vs_MD_EUR':',.0f'}),
        use_container_width=True, hide_index=True,
    )


def section_hourly(T):
    st.header("⏱ Evolución Cuarto-Horaria")
    dh = T.get('hourly_target', pd.DataFrame())
    if dh.empty:
        st.info("No hay datos horarios de unidades objetivo en el Parquet.")
        return

    # ── Controles ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    units   = ['Todas'] + sorted(dh['Unit_Name'].dropna().unique().tolist())
    dates   = ['Todos'] + sorted(dh['Date'].unique().tolist())
    unit    = col1.selectbox("Instalación",    units, key="h_unit")
    date    = col2.selectbox("Día",            dates, key="h_date")
    p_mode  = col3.selectbox("Vista precio",
                             ["MIC y MD","Solo MIC","Solo MD","Spread MIC−MD"],
                             key="h_pmode")
    pr_mode = col4.selectbox("Perfil por",
                             ["Media","Suma","Máximo"], key="h_prmode")

    data = dh.copy()
    if unit != 'Todas': data = data[data['Unit_Name'] == unit]
    if date != 'Todos': data = data[data['Date']      == date]

    if data.empty:
        st.warning("Sin datos para la selección."); return

    multi_unit = (unit == 'Todas')

    # ── KPIs ──────────────────────────────────────────────────────────────────
    tS   = data['Sell_MWh'].sum()
    tB   = data['Buy_MWh'].sum()
    tN   = data['Net_Cash_EUR'].sum()
    tO   = data['MIC_vs_MD_EUR'].sum() if 'MIC_vs_MD_EUR' in data else 0
    valid = data.dropna(subset=['MIC_Price','MD_Price'])
    avg_sp = (valid['MIC_Price'] - valid['MD_Price']).mean() if not valid.empty else 0
    n_days = data['Date'].nunique()
    act_qh = data[
        (data['Sell_MWh'] > 0.001) | (data['Buy_MWh'] > 0.001)
    ]['QH_Start'].nunique()

    kc = st.columns(5)
    kc[0].metric("Sell Total",    fmt_mwh(tS))
    kc[1].metric("Buy Total",     fmt_mwh(tB))
    kc[2].metric("Net Cash",      fmt_eur(tN),
                 delta=f"{tN:+,.0f} €", delta_color="normal")
    kc[3].metric("Beneficio vs MD", fmt_eur(tO),
                 delta=f"{tO:+,.0f} €", delta_color="normal")
    kc[4].metric("Spread Medio",  fmt_price(avg_sp),
                 delta=f"{avg_sp:+,.2f} €/MWh", delta_color="normal")

    st.divider()

    # ── ① Curva precio cuarto-horaria ─────────────────────────────────────────
    st.subheader("① Curva de Precio MIC vs MD — cuarto a cuarto")

    fig = go.Figure()
    units_list = data['Unit_Name'].unique() if multi_unit else [unit]
    colors_map = {u: CLR[i % len(CLR)] for i, u in enumerate(units_list)}

    for i, u in enumerate(units_list):
        ud = data[data['Unit_Name'] == u].sort_values('QH_Key') if multi_unit else \
             data.sort_values('QH_Key')
        x_lbl = ud['QH_Key'].str.replace(r'(\d{4})(\d{2})(\d{2}) ', r'\3/\2/\1 ',
                                          regex=True)
        col = colors_map[u]
        if p_mode in ("MIC y MD", "Solo MIC"):
            fig.add_scatter(x=x_lbl, y=ud['MIC_Price'], name=f"{u} MIC" if multi_unit else "MIC",
                            mode='lines', line=dict(color=col, width=1.8),
                            hovertemplate=f"{u}<br>%{{x}}<br>MIC: <b>%{{y:.2f}} €/MWh</b><extra></extra>")
        if p_mode in ("MIC y MD", "Solo MD"):
            fig.add_scatter(x=x_lbl, y=ud['MD_Price'], name=f"{u} MD" if multi_unit else "MD",
                            mode='lines', line=dict(color=col, width=1.2, dash='dot'),
                            hovertemplate=f"{u}<br>%{{x}}<br>MD: <b>%{{y:.2f}} €/MWh</b><extra></extra>")
        if p_mode == "Spread MIC−MD":
            spread = ud['MIC_Price'] - ud['MD_Price']
            fig.add_scatter(x=x_lbl, y=spread, name=f"{u} Spread" if multi_unit else "Spread",
                            mode='lines', fill='tozeroy', fillcolor='rgba(227,179,65,0.1)',
                            line=dict(color=YELLOW, width=1.8),
                            hovertemplate=f"{u}<br>%{{x}}<br>Spread: <b>%{{y:.2f}} €/MWh</b><extra></extra>")

    y_title = "Spread MIC−MD (€/MWh)" if p_mode == "Spread MIC−MD" else "Precio (€/MWh)"
    fig.update_layout(**plotly_layout(f"Precio por Cuarto de Hora — {unit}", height=340))
    fig.update_yaxes(title_text=y_title)
    fig.update_xaxes(tickangle=-38, nticks=32, title_text="Cuarto de hora")
    st.plotly_chart(fig, use_container_width=True)

    # ── ② Perfil cuarto-horario promedio ──────────────────────────────────────
    st.subheader("② Perfil Cuarto-Horario Promedio")

    all_qh = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0,15,30,45]]
    agg_fn = {'Media': 'mean', 'Suma': 'sum', 'Máximo': 'max'}[pr_mode]

    profile = data.groupby('QH_Start').agg(
        Sell_MWh    =('Sell_MWh',     agg_fn),
        Buy_MWh     =('Buy_MWh',      agg_fn),
        Net_Cash_EUR=('Net_Cash_EUR',  agg_fn),
        MIC_vs_MD   =('MIC_vs_MD_EUR', agg_fn),
    ).reindex(all_qh, fill_value=0).reset_index()

    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure()
        fig.add_bar(name="Ventas",  x=profile['QH_Start'], y=profile['Sell_MWh'],
                    marker_color=GREEN)
        fig.add_bar(name="Compras", x=profile['QH_Start'], y=profile['Buy_MWh'],
                    marker_color=BLUE)
        fig.update_layout(**plotly_layout(f"Volumen por Cuarto ({pr_mode})"),
                          barmode='group')
        fig.update_xaxes(nticks=24, tickangle=-38, title_text="HH:MM")
        fig.update_yaxes(title_text="MWh")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_bar(x=profile['QH_Start'], y=profile['Net_Cash_EUR'],
                    name="Net Cash", marker_color=bar_colors(profile['Net_Cash_EUR']),
                    secondary_y=False)
        fig.add_scatter(x=profile['QH_Start'], y=profile['MIC_vs_MD'],
                        name="MIC vs MD", mode='lines',
                        line=dict(color=YELLOW, width=2), secondary_y=True)
        fig.update_layout(**plotly_layout(f"Balance Neto por Cuarto ({pr_mode})"))
        fig.update_xaxes(nticks=24, tickangle=-38, title_text="HH:MM")
        fig.update_yaxes(title_text="Net Cash (€)", secondary_y=False, gridcolor="#21262d")
        fig.update_yaxes(title_text="MIC vs MD (€)", secondary_y=True,
                         gridcolor="transparent", showgrid=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── ③ Evolución diaria ────────────────────────────────────────────────────
    st.subheader("③ Evolución Día a Día")

    col1, col2 = st.columns(2)
    daily_net = data.groupby(['Date','Unit_Name'])['Net_Cash_EUR'].sum().reset_index()
    daily_opp = data.groupby(['Date','Unit_Name'])['MIC_vs_MD_EUR'].sum().reset_index()

    with col1:
        if multi_unit:
            fig = px.line(daily_net, x='Date', y='Net_Cash_EUR', color='Unit_Name',
                          markers=True, color_discrete_sequence=CLR,
                          labels={'Net_Cash_EUR':'Net Cash (€)','Date':'Fecha'})
        else:
            d_agg = daily_net.groupby('Date')['Net_Cash_EUR'].sum().reset_index()
            fig = go.Figure(go.Bar(
                x=d_agg['Date'], y=d_agg['Net_Cash_EUR'],
                marker_color=bar_colors(d_agg['Net_Cash_EUR']),
                hovertemplate="%{x}<br><b>%{y:,.2f} €</b><extra></extra>",
            ))
        fig.update_layout(**plotly_layout("Balance Neto Diario (€)"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if multi_unit:
            fig = px.line(daily_opp, x='Date', y='MIC_vs_MD_EUR', color='Unit_Name',
                          markers=True, line_dash_sequence=['dot'],
                          color_discrete_sequence=CLR,
                          labels={'MIC_vs_MD_EUR':'MIC vs MD (€)','Date':'Fecha'})
        else:
            d_agg = daily_opp.groupby('Date')['MIC_vs_MD_EUR'].sum().reset_index()
            fig = go.Figure(go.Scatter(
                x=d_agg['Date'], y=d_agg['MIC_vs_MD_EUR'],
                mode='lines+markers', fill='tozeroy',
                fillcolor='rgba(88,166,255,0.1)',
                line=dict(color=BLUE, width=2.5),
                hovertemplate="%{x}<br><b>%{y:,.2f} €</b><extra></extra>",
            ))
        fig.update_layout(**plotly_layout("MIC vs MD Diario (€)"))
        st.plotly_chart(fig, use_container_width=True)

    # ── ④ Heatmaps QH × Día ──────────────────────────────────────────────────
    st.subheader("④ Heatmaps Concentración — Cuarto × Día")

    dates_sorted = sorted(data['Date'].unique())

    def build_heatmap_z(field):
        z = []
        for qh in all_qh:
            row = []
            for d in dates_sorted:
                rows = data[(data['QH_Start'] == qh) & (data['Date'] == d)]
                row.append(rows[field].sum() if not rows.empty else 0)
            z.append(row)
        return z

    def build_spread_z():
        z = []
        for qh in all_qh:
            row = []
            for d in dates_sorted:
                rows = data[
                    (data['QH_Start'] == qh) & (data['Date'] == d) &
                    data['MIC_Price'].notna() & data['MD_Price'].notna()
                ]
                row.append((rows['MIC_Price'] - rows['MD_Price']).mean()
                           if not rows.empty else None)
            z.append(row)
        return z

    col1, col2 = st.columns(2)
    hm_h = max(400, len(all_qh) * 4)

    with col1:
        fig = go.Figure(go.Heatmap(
            z=build_heatmap_z('Sell_MWh'), x=dates_sorted, y=all_qh,
            colorscale=[[0,"#0d1117"],[1,GREEN]],
            colorbar=dict(title='MWh', tickformat=',.3f'),
            hovertemplate="%{y} · %{x}<br>Vendido: <b>%{z:.3f} MWh</b><extra></extra>",
        ))
        fig.update_layout(**plotly_layout("Volumen Vendido (MWh)", height=hm_h))
        fig.update_xaxes(tickangle=-38)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = go.Figure(go.Heatmap(
            z=build_spread_z(), x=dates_sorted, y=all_qh,
            colorscale=[[0,RED],[0.5,SURFACE],[1,BLUE]], zmid=0,
            colorbar=dict(title='€/MWh', tickformat=',.2f'),
            hovertemplate="%{y} · %{x}<br>Spread MIC−MD: <b>%{z:.2f} €/MWh</b><extra></extra>",
        ))
        fig.update_layout(**plotly_layout("Spread MIC−MD (€/MWh)", height=hm_h))
        fig.update_xaxes(tickangle=-38)
        st.plotly_chart(fig, use_container_width=True)

    fig = go.Figure(go.Heatmap(
        z=build_heatmap_z('Net_Cash_EUR'), x=dates_sorted, y=all_qh,
        colorscale=[[0,RED],[0.5,SURFACE],[1,GREEN]], zmid=0,
        colorbar=dict(title='€', tickformat=',.2f'),
        hovertemplate="%{y} · %{x}<br>Net Cash: <b>%{z:,.2f} €</b><extra></extra>",
    ))
    fig.update_layout(**plotly_layout("Balance Neto (€)", height=hm_h))
    fig.update_xaxes(tickangle=-38)
    st.plotly_chart(fig, use_container_width=True)

    # ── Tabla detalle ─────────────────────────────────────────────────────────
    with st.expander("Ver detalle cuarto-horario (primeras 500 filas)"):
        show = data.sort_values(['QH_Key','Unit_Name']).head(500)
        show_cols = ['Unit_Name','Date','QH_Start','Sell_MWh','Buy_MWh',
                     'MIC_Price','MD_Price','Net_Cash_EUR','MIC_vs_MD_EUR']
        show_cols = [c for c in show_cols if c in show.columns]
        st.dataframe(
            show[show_cols].style.format({
                'Sell_MWh':'.3f','Buy_MWh':'.3f',
                'MIC_Price':'.2f','MD_Price':'.2f',
                'Net_Cash_EUR':',.2f','MIC_vs_MD_EUR':',.2f',
            }),
            use_container_width=True, hide_index=True,
        )


# ==============================================================================
# ── SIDEBAR + ROUTING ─────────────────────────────────────────────────────────
# ==============================================================================

def main():
    st.sidebar.title("⚡ MIC Trade Analyzer")
    st.sidebar.caption("Mercado Intradiario Continuo · XBID")
    st.sidebar.divider()

    # Origen de datos
    source = st.sidebar.radio(
        "Fuente de datos",
        ["GitHub (producción)", "Archivo local (desarrollo)"],
        key="source",
    )

    if source == "GitHub (producción)":
        try:
            T = load_data(PARQUET_URL)
        except Exception as e:
            st.error(f"Error cargando desde GitHub: {e}\n\nComprueba que PARQUET_URL es correcto.")
            st.stop()
    else:
        local_path = st.sidebar.text_input(
            "Ruta local del .parquet",
            value="mic_data.parquet",
            key="local_path",
        )
        if not local_path or not __import__('os').path.exists(local_path):
            st.info("Introduce la ruta del archivo Parquet local.")
            st.stop()
        T = load_data_local(local_path)

    # Info rápida
    trades = T.get('trades', pd.DataFrame())
    if not trades.empty:
        st.sidebar.divider()
        if 'Month_Year' in trades.columns:
            months = sorted(trades['Month_Year'].dropna().unique())
            st.sidebar.caption(f"**Período:** {months[0]} → {months[-1]}")
        st.sidebar.caption(f"**Operaciones:** {len(trades):,}")

    st.sidebar.divider()

    # Navegación
    section = st.sidebar.radio(
        "Sección",
        ["Overview", "Por Agente", "Por Tecnología", "Unidades",
         "Evolución Mensual", "Balance Objetivo", "⏱ Evolución Cuarto-Horaria"],
        key="nav",
    )

    # Render
    if   section == "Overview":                    section_overview(T)
    elif section == "Por Agente":                  section_agents(T)
    elif section == "Por Tecnología":              section_tech(T)
    elif section == "Unidades":                    section_units(T)
    elif section == "Evolución Mensual":           section_monthly(T)
    elif section == "Balance Objetivo":            section_target(T)
    elif section == "⏱ Evolución Cuarto-Horaria":  section_hourly(T)


if __name__ == "__main__":
    main()
