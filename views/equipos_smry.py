import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.colors as mcolors
import modules.utils as utils
from modules.data_loader import cargar_datos_equipos_only # Importamos la carga especial

def render_view(df_ignored, categoria_sel):
    # Nota: df_ignored es el argumento que viene de app.py (df_raw), 
    # pero aquí lo ignoramos porque usamos la carga optimizada propia.
    
    # 1. Cargar datos optimizados (Carril B)
    try:
        df_teams_raw = cargar_datos_equipos_only()
    except:
        df_teams_raw = pd.DataFrame()

    # LMBPF: Sin filtro de categoría (liga de una sola rama)
    if not df_teams_raw.empty:
        df_teams = df_teams_raw.copy()
    else:
        df_teams = pd.DataFrame()

    if df_teams.empty:
        st.warning("No hay datos de equipos disponibles.")
        st.stop()

    # 3. Slider y Config
    max_games_found = df_teams.groupby('equipo_nombre')['id_abe'].nunique().max()
    if not max_games_found or pd.isna(max_games_found): max_games_found = 1
    else: max_games_found = int(max_games_found)
    
    col_header, col_slider_eq = st.columns([1, 1])
    with col_header:
        st.title("Equipos")
    with col_slider_eq:
        st.markdown("<br>", unsafe_allow_html=True)
        if max_games_found > 1:
            games_window_eq = st.slider("Calcular durante los últimos X juegos:", 1, max_games_found, max_games_found, key="slider_equipos")
        else:
            st.info("Mostrando datos disponibles.")
            games_window_eq = 1
        utils.rastrear_cambio("Slider Juegos (Equipos)", games_window_eq)

    SEASON_GAMES = 30  # LMBPF temporada regular

    # 4. Preparación (Directa, sin GroupBy)
    df_games = df_teams.copy()

    # Cálculos con Score Real
    df_games['Tm_PTS'] = df_games['Tm_Score']
    df_games['Opp_PTS'] = df_games['Opp_Score']
    df_games['W'] = np.where(df_games['Tm_PTS'] > df_games['Opp_PTS'], 1, 0)
    df_games['L'] = np.where(df_games['Tm_PTS'] < df_games['Opp_PTS'], 1, 0)

    # Posesiones
    denom_orb = df_games['Tm_ORB'] + df_games['Opp_DRB']
    orb_pct = np.divide(df_games['Tm_ORB'], denom_orb, out=np.zeros_like(df_games['Tm_ORB'], dtype=float), where=denom_orb!=0)
    missed_fg = df_games['Tm_FGA'] - df_games['Tm_FG']
    df_games['Tm_Poss'] = (df_games['Tm_FGA'] - (orb_pct * missed_fg * 1.07) + df_games['Tm_TOV'] + (0.4 * df_games['Tm_FTA']))

    denom_orb_opp = df_games['Opp_ORB'] + df_games['Tm_DRB']
    orb_pct_opp = np.divide(df_games['Opp_ORB'], denom_orb_opp, out=np.zeros_like(df_games['Opp_ORB'], dtype=float), where=denom_orb_opp!=0)
    opp_missed_fg = df_games['Opp_FGA'] - df_games['Opp_FG']
    df_games['Opp_Poss'] = (df_games['Opp_FGA'] - (orb_pct_opp * opp_missed_fg * 1.07) + df_games['Opp_TOV'] + (0.4 * df_games['Opp_FTA']))

    # 5. Agregación
    def calcular_metricas_agrupadas(dataframe_input):
        agg = dataframe_input.groupby('equipo_nombre').agg({
            'W': 'sum', 'L': 'sum',
            'Tm_PTS': 'sum', 'Opp_PTS': 'sum',
            'Tm_Poss': 'sum', 'Opp_Poss': 'sum',
            'id_abe': 'count'
        }).reset_index()
        agg.rename(columns={'id_abe': 'GP'}, inplace=True)

        agg['Off_Rtg'] = np.divide(agg['Tm_PTS'], agg['Tm_Poss'], out=np.zeros_like(agg['Tm_PTS'], dtype=float), where=agg['Tm_Poss']!=0) * 100
        agg['Def_Rtg'] = np.divide(agg['Opp_PTS'], agg['Opp_Poss'], out=np.zeros_like(agg['Opp_PTS'], dtype=float), where=agg['Opp_Poss']!=0) * 100
        agg['Net_Rtg'] = agg['Off_Rtg'] - agg['Def_Rtg']
        agg['Win_Pct'] = np.divide(agg['W'], agg['GP'], out=np.zeros_like(agg['W'], dtype=float), where=agg['GP']!=0)
        return agg

    # Dinámicas
    df_games_sorted = df_games.sort_values(['equipo_nombre', 'Fecha'], ascending=[True, False])
    df_window_raw = df_games_sorted.groupby('equipo_nombre').head(games_window_eq)
    df_dynamic = calcular_metricas_agrupadas(df_window_raw)

    # Last 5
    df_last5_raw = df_games_sorted.groupby('equipo_nombre').head(5)
    df_l5 = calcular_metricas_agrupadas(df_last5_raw)
    cols_rename_l5 = {'W': 'L5_W', 'L': 'L5_L', 'Net_Rtg': 'L5_Net', 'Off_Rtg': 'L5_Off', 'Def_Rtg': 'L5_Def'}
    df_l5.rename(columns=cols_rename_l5, inplace=True)
    df_l5 = df_l5[['equipo_nombre'] + list(cols_rename_l5.values())]

    df_final = pd.merge(df_dynamic, df_l5, on='equipo_nombre', how='left')

    # Pitágoras (Corregido con float 13.91)
    pts_power = df_final['Tm_PTS'] ** 13.91
    opp_pts_power = df_final['Opp_PTS'] ** 13.91
    denom_pyth = pts_power + opp_pts_power
    df_final['Pyth_Ratio'] = np.divide(pts_power, denom_pyth, out=np.zeros_like(pts_power, dtype=float), where=denom_pyth!=0)
    
    df_final['Exp_Total'] = df_final['Pyth_Ratio'] * SEASON_GAMES
    df_final['Exp_Current'] = df_final['Pyth_Ratio'] * df_final['GP']
    df_final['Diff_Wins'] = df_final['W'] - df_final['Exp_Current']

    # Rankings
    df_final['Rk_Net'] = df_final['Net_Rtg'].rank(ascending=False, method='min')
    df_final['Rk_W'] = df_final['W'].rank(ascending=False, method='min')
    df_final['Rk_L'] = df_final['L'].rank(ascending=True, method='min')
    df_final['Rk_Pct'] = df_final['Win_Pct'].rank(ascending=False, method='min')
    df_final['Rk_ExpT'] = df_final['Exp_Total'].rank(ascending=False, method='min')
    df_final['Rk_ExpC'] = df_final['Exp_Current'].rank(ascending=False, method='min')
    df_final['Rk_Diff'] = df_final['Diff_Wins'].rank(ascending=False, method='min')
    df_final['Rk_Off'] = df_final['Off_Rtg'].rank(ascending=False, method='min')
    df_final['Rk_Def'] = df_final['Def_Rtg'].rank(ascending=True, method='min')
    df_final['Rk_L5_W'] = df_final['L5_W'].rank(ascending=False, method='min')
    df_final['Rk_L5_L'] = df_final['L5_L'].rank(ascending=True, method='min')
    df_final['Rk_L5_Net'] = df_final['L5_Net'].rank(ascending=False, method='min')
    df_final['Rk_L5_Off'] = df_final['L5_Off'].rank(ascending=False, method='min')
    df_final['Rk_L5_Def'] = df_final['L5_Def'].rank(ascending=True, method='min')

    # Visualización
    st.markdown("### 📋 Resumen del torneo")
    mapa_orden_equipos = {
        "Victorias": "W", "Derrotas": "L", "%Victorias": "Win_Pct",
        "EWT": "Exp_Total", "EWA": "Exp_Current", "EWD": "Diff_Wins",
        "ORtg": "Off_Rtg", "DRtg": "Def_Rtg", "NRtg": "Net_Rtg",
        "Vict U5": "L5_W", "Derr U5": "L5_L", "ORtg U5": "L5_Off",
        "DRtg U5": "L5_Def", "NRtg U5": "L5_Net"
    }
    nombres_largos_adv = {
        "Victorias": "Partidos ganados", 
        "Derrotas": "Partidos perdidos",
        "%Victorias": "Porcentaje de victorias", 
        "EWT": "Expected Wins Total - estimado de victorias al final de la temporada a partir del rendimiento actual",
        "EWA": "Expected Wins Actual- estimado de victorias en los partidos jugados a partir del rendimiento actual", 
        "EWD": "Diferencia entre EWA y victorias reales",
        "ORtg": "Rating Ofensivo", 
        "DRtg": "Rating Defensivo", 
        "NRtg": "Net Rating",
        "Vict U5": "Victorias en los últimos 5 partidos", 
        "Derr U5": "Derrotas en los últimos 5 partidos", 
        "ORtg U5": "Rating Ofensivo en los últimos 5 partidos",
        "DRtg U5": "Rating Defensivo en los últimos 5 partidos", 
        "NRtg U5": "Net Rating en los últimos 5 partidos"
    }

    criterio_sort = st.radio("Criterio de orden:", options=list(mapa_orden_equipos.keys()), index=8, horizontal=True, label_visibility="collapsed", key="radio_equipos")
    utils.rastrear_cambio("Sort Equipos", criterio_sort) 

    columna_ordenar = mapa_orden_equipos[criterio_sort]
    ascendente = True if columna_ordenar in ['Def_Rtg', 'L', 'L5_L', 'Rk_Def', 'Rk_L5_Def'] else False
    
    df_disp = df_final.sort_values(columna_ordenar, ascending=ascendente)
    flecha = "⬆️" if ascendente else "⬇️"
    st.caption(f"Ordenando por **{nombres_largos_adv.get(criterio_sort)}** ({flecha})")

    data_struct = {
        ('Equipo', ''): df_disp['equipo_nombre'],
        ('Victorias', ''): df_disp['W'], ('Derrotas', ''): df_disp['L'], ('%Victorias', ''): df_disp['Win_Pct'],
        ('EWT', ''): df_disp['Exp_Total'], ('EWA', ''): df_disp['Exp_Current'],
        ('EWD', 'Rank'): df_disp['Rk_Diff'], ('EWD', ''): df_disp['Diff_Wins'],
        ('ORtg', 'Rank'): df_disp['Rk_Off'], ('ORtg', ''): df_disp['Off_Rtg'],
        ('DRtg', 'Rank'): df_disp['Rk_Def'], ('DRtg', ''): df_disp['Def_Rtg'],
        ('NRtg', 'Rank'): df_disp['Rk_Net'], ('NRtg', ''): df_disp['Net_Rtg'],
        ('Vict U5', ''): df_disp['L5_W'], ('Derr U5', ''): df_disp['L5_L'],
        ('ORtg U5', 'Rank'): df_disp['Rk_L5_Off'], ('ORtg U5', ''): df_disp['L5_Off'],
        ('DRtg U5', 'Rank'): df_disp['Rk_L5_Def'], ('DRtg U5', ''): df_disp['L5_Def'],
        ('NRtg U5', 'Rank'): df_disp['Rk_L5_Net'], ('NRtg U5', ''): df_disp['L5_Net'],
    }
    df_multi = pd.DataFrame(data_struct)

    formats = {
        ('Victorias', ''): "{:.0f}", ('Derrotas', ''): "{:.0f}", ('%Victorias', ''): "{:.1%}",
        ('EWT', ''): "{:.1f}", ('EWA', ''): "{:.1f}", ('EWD', ''): "{:+.2f}", 
        ('ORtg', ''): "{:.1f}", ('DRtg', ''): "{:.1f}", ('NRtg', ''): "{:+.1f}",
        ('Vict U5', ''): "{:.0f}", ('Derr U5', ''): "{:.0f}", 
        ('ORtg U5', ''): "{:.1f}", ('DRtg U5', ''): "{:.1f}", ('NRtg U5', ''): "{:+.1f}",
        ('EWD', 'Rank'): "{:.0f}", ('ORtg', 'Rank'): "{:.0f}", ('DRtg', 'Rank'): "{:.0f}", 
        ('NRtg', 'Rank'): "{:.0f}", ('ORtg U5', 'Rank'): "{:.0f}", ('DRtg U5', 'Rank'): "{:.0f}", 
        ('NRtg U5', 'Rank'): "{:.0f}",
    }

    subset_ranks = [col for col in df_multi.columns if col[1] == 'Rank']
    colores = ["#00D46B", "#ffffff", "#FF4534"]
    soft_cmap = mcolors.LinearSegmentedColormap.from_list("SoftBlueRed", colores)

    st.dataframe(
        df_multi.style.format(formats).background_gradient(subset=subset_ranks, cmap=soft_cmap, vmin=1, vmax=len(df_multi)),
        height=(len(df_multi) * 35) + 75, use_container_width=True, hide_index=True
    )