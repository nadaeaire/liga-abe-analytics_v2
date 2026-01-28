# modules/data_loader.py
import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client, Client
from datetime import datetime

# --- UTILIDAD INTERNA ---
def vectorizar_minutos(series):
    """Convierte minutos formato texto/float a float decimal."""
    mask_is_float = ~series.astype(str).str.contains(':')
    result_minutes = pd.Series(0.0, index=series.index)
    result_minutes.loc[mask_is_float] = pd.to_numeric(series.loc[mask_is_float], errors='coerce').fillna(0.0)
    m_s_part = series.loc[~mask_is_float].astype(str).str.split(':').str[:2].str.join(':')
    try:
        duration = pd.to_timedelta('00:' + m_s_part)
        result_minutes.loc[~mask_is_float] = duration.dt.total_seconds() / 60.0
    except:
        result_minutes.loc[~mask_is_float] = 0.0
    return result_minutes.fillna(0.0)

# --- CONEXIÓN SUPABASE ---
@st.cache_resource
def get_supabase_client() -> Client:
    try:
        url = st.secrets["supabase_config"]["url"]
        key = st.secrets["supabase_config"]["anon_key"]
        # DEBUG: Mostrar que las credenciales se leyeron (sin mostrar valores sensibles)
        st.sidebar.success(f"🔧 Supabase URL: {url[:30]}...")
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error Supabase Client: {e}")
        st.stop()

# --- CARGA 1: JUGADORES Y ESTADÍSTICAS (VISTA MAESTRA) ---
@st.cache_data(ttl=600)
def cargar_base_datos():
    supabase = get_supabase_client()
    try:
        # Descargar TODO (Límite alto)
        response = (
            supabase.table("vista_analitica_master")
            .select("*")
            .limit(100000) 
            .execute()
        )
        
        if not response.data: return pd.DataFrame()
        
        df_master = pd.DataFrame(response.data)

        # Limpieza de Minutos
        if 'sMinutes' in df_master.columns:
             if df_master['sMinutes'].dtype == object or df_master['sMinutes'].dtype == str:
                 df_master['sMinutes'] = vectorizar_minutos(df_master['sMinutes'])
             else:
                 df_master['sMinutes'] = pd.to_numeric(df_master['sMinutes'], errors='coerce').fillna(0)

        if 'Tm_MIN' in df_master.columns:
             if df_master['Tm_MIN'].dtype == object:
                 df_master['Tm_MIN'] = vectorizar_minutos(df_master['Tm_MIN'])
             else:
                 df_master['Tm_MIN'] = pd.to_numeric(df_master['Tm_MIN'], errors='coerce').fillna(0)

        # Fechas
        if 'Fecha' in df_master.columns:
            df_master['Fecha'] = pd.to_datetime(df_master['Fecha'], errors='coerce')
        else:
             df_master['Fecha'] = datetime.now()

        # --- CORRECCIÓN AQUÍ ---
        # Sanitización Numérica (EXCLUYENDO Opp_Name)
        cols_numericas = [c for c in df_master.columns if c.startswith('s') or c.startswith('Tm_') or c.startswith('Opp_')]
        
        for col in cols_numericas:
             # Agregamos 'Opp_Name' a las excepciones para que NO lo convierta a número
             if col not in ['sMinutes', 'Tm_MIN', 'Opp_Name']:
                df_master[col] = pd.to_numeric(df_master[col], errors='coerce').fillna(0)

        # Limpieza específica para Opp_Name (Asegurar que sea Texto)
        if 'Opp_Name' in df_master.columns:
            df_master['Opp_Name'] = df_master['Opp_Name'].astype(str).replace(['nan', 'None', '0', '0.0'], '-')

        return df_master

    except Exception as e:
        st.error(f"⚠️ Error cargando datos de Jugadores: {e}")
        return pd.DataFrame()

# --- CARGA 2: EQUIPOS (CARRIL B - SIN DUPLICADOS) ---
@st.cache_data(ttl=600)
def cargar_datos_equipos_only():
    """Carga datos optimizados solo para la tabla de posiciones."""
    supabase = get_supabase_client()
    try:
        response = supabase.table("vista_equipos_master").select("*").limit(10000).execute()
        # DEBUG
        st.write(f"🔧 DEBUG data_loader: response.data tiene {len(response.data) if response.data else 0} registros")
        if not response.data: return pd.DataFrame()
        
        df = pd.DataFrame(response.data)
        
        # LIMPIEZA DE DUPLICADOS (Vital para evitar 73 wins)
        if not df.empty and 'id_abe' in df.columns and 'equipo_nombre' in df.columns:
            df = df.drop_duplicates(subset=['id_abe', 'equipo_nombre']) 
        
        # Tipos
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
            
        cols_num = ['Tm_Score', 'Opp_Score', 'Tm_FG', 'Tm_FGA', 'Tm_3PM', 'Tm_FTM', 
                    'Tm_FTA', 'Tm_ORB', 'Tm_DRB', 'Tm_TOV', 'Opp_DRB', 'Opp_ORB', 
                    'Opp_FG', 'Opp_FGA', 'Opp_FTA', 'Opp_TOV', 'Opp_PF']
        
        for c in cols_num:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                
        return df
    except Exception as e:
        st.error(f"Error cargando vista equipos: {e}")
        return pd.DataFrame()
    
# --- CARGA 3: METADATA (PLAYERS & ROSTERS) ---
# Usamos un TTL más largo (ej. 1 hora) porque la estatura/peso no cambian seguido
@st.cache_data(ttl=3600) 
def cargar_metadata_jugadores():
    """
    Carga las tablas de dimensiones: players (bio) y rosters (equipos/posiciones).
    Retorna dos DataFrames: (df_players, df_rosters)
    """
    supabase = get_supabase_client()
    try:
        # 1. Fetch tabla 'players'
        # Asegúrate de que tu tabla en Supabase se llame "players"
        resp_p = supabase.table("players").select("*").execute()
        df_players = pd.DataFrame(resp_p.data) if resp_p.data else pd.DataFrame()

        # 2. Fetch tabla 'rosters'
        # Asegúrate de que tu tabla en Supabase se llame "rosters"
        resp_r = supabase.table("rosters").select("*").execute()
        df_rosters = pd.DataFrame(resp_r.data) if resp_r.data else pd.DataFrame()

        # --- Limpieza Preventiva ---
        
        # Convertir numéricos en Players
        if not df_players.empty:
            cols_bio = ['height_cm', 'weight_kg'] 
            for c in cols_bio:
                if c in df_players.columns:
                    df_players[c] = pd.to_numeric(df_players[c], errors='coerce').fillna(0)

        # Convertir fechas en Rosters (importante para ordenar por la más reciente)
        if not df_rosters.empty:
            if 'effective_start_date' in df_rosters.columns:
                df_rosters['effective_start_date'] = pd.to_datetime(df_rosters['effective_start_date'], errors='coerce')

        return df_players, df_rosters

    except Exception as e:
        st.error(f"⚠️ Error cargando Metadata (Players/Rosters): {e}")
        # Retornar DFs vacíos para no romper la app
        return pd.DataFrame(), pd.DataFrame()
    
@st.cache_data(ttl=3600)
def cargar_catalogo_equipos():
    """Carga solo el catálogo de equipos (ID y Nombre) para cruces."""
    supabase = get_supabase_client()
    try:
        # Pedimos explícitamente la tabla 'equipos'
        response = supabase.table("equipos").select("equipo_id, nombre").execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error cargando catálogo equipos: {e}")
        return pd.DataFrame()