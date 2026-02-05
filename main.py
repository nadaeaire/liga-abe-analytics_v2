import streamlit as st
import pandas as pd
import modules.utils as utils
import modules.auth as auth
# Importamos las funciones de carga desde tu data_loader actualizado
from modules.data_loader import cargar_base_datos, cargar_metadata_jugadores, cargar_catalogo_equipos

# Importamos las Vistas
import views.players_avg as view_players_avg
import views.players_adv as view_players_adv
import views.equipos_smry as view_equipos_smry
import views.equipos_4f as view_equipos_4f
import views.players_prfl as view_players_prfl

# 1. Configuración Global
st.set_page_config(
    page_title="Analytics LMBPF — GravityStats x Nada Está en el Aire",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Cargar estilos y tracking
utils.cargar_estilos_css()
utils.inyectar_ga()

# 2. Autenticación (Bloqueante)
if not auth.check_password():
    st.stop()

# --- INICIALIZACIÓN DE ESTADO ---
if 'selected_player_id' not in st.session_state:
    st.session_state.selected_player_id = 190 

if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'main' # 'main' o 'profile'

# 3. Carga de Datos Global
try:
    with st.spinner('Cargando base de datos...'):
        # A) Carga de Stats (Games) - Carril A
        df_raw = cargar_base_datos()
        
        # B) Carga de Metadata (Bio y Rosters) desde Supabase - Carril C (Nuevo)
        df_players, df_rosters = cargar_metadata_jugadores()
        
        # C) Carga de Catálogo de Equipos
        df_equipos_cat = cargar_catalogo_equipos()

except Exception as e:
    st.error(f"Error técnico cargando datos: {e}")
    st.stop()

# 4. Sidebar y Navegación
st.sidebar.image("GravityStats_Logo.png", width=300)
st.sidebar.markdown(
    """
    <div style="margin-top: -20px;">
        <h1 style="margin-top: 20px; margin-bottom: 0px; font-size: 25px; color: #dc362a;">Analytics LMBPF</h1>
        <h3 style="margin-top: -25px; font-weight: bold; color: #0a173c;">GravityStats</h3>
        <h3 style="margin-top: -33px; font-weight: normal; color: #0a173c; font-size: 14px">Nada Está en el Aire</h3>
    </div>
    """,
    unsafe_allow_html=True
)

# LMBPF: Sin selector de categoría (liga de una sola rama)
# Usamos todos los datos disponibles
if not df_raw.empty:
    df = df_raw.copy()
else:
    df = pd.DataFrame()

# Aviso si no hay jugadores
if df.empty:
    st.sidebar.warning("No hay datos de stats disponibles.")

st.sidebar.divider()

# --- CALLBACK PARA RESETEAR LA VISTA ---
# Si el usuario hace click en el menú lateral, salimos del modo "Perfil"
def reset_view():
    st.session_state.view_mode = 'main'

# Menú Principal (SIN "Perfil Jugador")
opcion = st.sidebar.radio(
    "Ir a:", 
    ["🤝 Equipos", "4️⃣ Four Factors", "📊 Por partido", "🛸 Avanzadas"],
    on_change=reset_view # Activamos el reset al cambiar
)
utils.rastrear_cambio("Vista Principal", opcion)

# --- LIMPIEZA DE NOMBRES (Alias) ---
alias_equipos = {
    "ANAHUAC QUERETARO": "Anáhuac QRO", "ANAHUAC XALAPA": "Anáhuac XAL",
    "AUTONOMA DE CHIHUAHUA": "UACH", "CETYS MEXICALI": "CETYS",
    "CEU MONTERREY": "CEU", "INTERAMERICANA": "Inter",
    "TEC MTY GUADALAJARA": "Tec GDL", "TEC MTY HIDALGO": "Tec HGO",
    "TEC MTY MONTERREY": "Tec MTY", "TEC MTY PUEBLA": "Tec PUE",
    "TEC MTY SANTA FE": "Tec CSF", "TEC MTY TOLUCA": "Tec TOL",
    "UANE": "UANE", "UANL": "UANL", "UDLAP": "UDLAP",
    "UMAD": "UMAD", "UNIVERSIDAD MONTRER": "Montrer",
    "UP MEXICO": "UP MX", "UPAEP": "UPAEP",
    "ANAHUAC NORTE": "Anáhuac NTE", "CETYS TIJUANA": "CETYS",
    "MODELO MERIDA": "Modelo", "TEC MTY AGUASCALIENTES": "Tec AGS",
    "TEC MTY CEM": "Tec CEM", "TEC MTY QUERETARO": "Tec QRO",
    "UVAQ MORELIA": "UVAQ"
}

if not df.empty:
    df['equipo_nombre'] = df['equipo_nombre'].replace(alias_equipos)

# 5. Enrutador de Vistas (LÓGICA DRILL-DOWN)

# A) Si estamos en modo Perfil, mostramos SOLO el perfil (Overlay)
if st.session_state.view_mode == 'profile':
    # Botón para regresar
    if st.button("⬅️ Volver a la lista", type="secondary"):
        st.session_state.view_mode = 'main'
        st.rerun()
    
    # Renderizamos el perfil
    current_pid = st.session_state.selected_player_id
    view_players_prfl.render_view(current_pid, df_raw, df_players, df_rosters, df_equipos_cat)

# B) Si estamos en modo Normal, mostramos lo que diga el menú
else:
    # LMBPF: Pasamos "LMBPF" como categoría fija
    categoria_lmbpf = "LMBPF"

    if opcion == "📊 Por partido":
        if df.empty:
            st.error("No hay datos disponibles.")
        else:
            view_players_avg.render_view(df, df_players, df_rosters, categoria_lmbpf)

    elif opcion == "🛸 Avanzadas":
        if df.empty:
            st.error("No hay datos disponibles.")
        else:
            view_players_adv.render_view(df, df_players, df_rosters, categoria_lmbpf)

    elif opcion == "🤝 Equipos":
        view_equipos_smry.render_view(df, categoria_lmbpf)

    elif opcion == "4️⃣ Four Factors":
        view_equipos_4f.render_view(df, categoria_lmbpf)