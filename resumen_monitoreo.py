import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium import Marker, Icon
from folium.plugins import MarkerCluster, AntPath
from streamlit_folium import st_folium
from geopy.distance import geodesic

# 🎨 Estilos CSS fijos (claro, como original + mejoras solicitadas)
st.markdown("""
<style>
.stApp { background-color: #f9fbfc; color: #222; font-family: 'Segoe UI', sans-serif; }

/* Sidebar completo: fondo azul oscuro y texto blanco en TODO */
[data-testid="stSidebar"] {
    width: 280px;
    background-color: #1f4e79;
    color: white;
    font-weight: bold;
}
[data-testid="stSidebar"] * {
    color: white !important;
    font-weight: 500;
}

/* Estilos de las pestañas principales */
.stTabs [data-baseweb="tab"] {
    background-color: #e8f0f7; color: #000; border-radius: 10px 10px 0 0; padding: 10px;
}
.stTabs [data-baseweb="tab"]:hover { color: #1f4e79; }
.stTabs [aria-selected="true"] { background-color: #1f4e79; color: white; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def cargar_datos(archivo):
    df = pd.read_csv(archivo, sep=';', encoding='utf-8')
    df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Fecha/Hora'])
    df['Equipo'] = df['Equipo'].astype(str)
    df['Hora'] = df['Fecha/Hora'].dt.floor('H')
    df = df.sort_values(['Equipo','Fecha/Hora'])
    df['tiempo_seg'] = df.groupby('Equipo')['Fecha/Hora'].diff().shift(-1).dt.total_seconds().fillna(0)
    df.loc[df['Grupo Operacion'] == 'AUXILIAR', 'Grupo Operacion'] = 'PRODUCTIVO'
    df.rename(columns={'Grupo Equipo/Frente': 'grupo_equipo'}, inplace=True)
    return df.dropna(axis=1, how='all')

st.sidebar.title("🔧 Panel de Control")
archivo_cargado = st.sidebar.file_uploader("📁 Cargar archivo .txt", type=["txt"])

if archivo_cargado:
    df = cargar_datos(archivo_cargado)
    st.success("✅ Archivo cargado correctamente")

    # ================================
    # 🔍 FILTRO MULTIPLE POR GRUPO EQUIPO/FRENTE
    # ================================
    grupos_disponibles = sorted(df['grupo_equipo'].dropna().unique())
    grupos_seleccionados = st.sidebar.multiselect(
        "🏗️ Filtrar por Grupo Equipo/Frente",
        options=grupos_disponibles,
        default=grupos_disponibles
    )

    if not grupos_seleccionados:
        grupos_seleccionados = grupos_disponibles

    df_filtrado_global = df[df['grupo_equipo'].isin(grupos_seleccionados)].copy()

    # ================================
    # 📑 SELECCIÓN DE PESTAÑA
    # ================================
    pestaña = st.sidebar.radio("Seleccione una vista", [
        "📊 Análisis de Productividad",
        "🚨 Alertas equipos parados o en mantenimiento",
        "📍 Recorrido y Hora Inicio Labor"
    ])

    if pestaña == "📊 Análisis de Productividad":
        st.header("📊 Análisis de Productividad Acumulada y Horaria")

        tabs = st.tabs(["📌 Último Estado", "📈 % Productivo por Equipo", "⏳ Evolución Horaria", "📋 Clasificación Acumulada"])

        with tabs[0]:
            st.subheader("📌 Resumen por Grupo de Operación a una Hora Específica")
            hora_opciones = sorted(df_filtrado_global['Hora'].dt.time.unique())
            if not hora_opciones:
                st.warning("No hay horas disponibles con los filtros aplicados.")
            else:
                hora_str = st.selectbox("Seleccione la hora de evaluación", options=hora_opciones)
                fecha = st.date_input("Seleccione la fecha", value=df_filtrado_global['Fecha/Hora'].min().date())
                hora_obj = pd.Timestamp.combine(fecha, hora_str.replace(minute=0, second=0, microsecond=0))

                df_hora = df_filtrado_global[df_filtrado_global['Hora'] == hora_obj]
                if df_hora.empty:
                    st.warning(f"No hay datos para la fecha y hora seleccionada: {hora_obj}")
                else:
                    ultimo_registro = df_hora.sort_values(['Equipo', 'Fecha/Hora']).groupby('Equipo').tail(1)
                    resumen = ultimo_registro.groupby(['Grupo Operacion'])['Equipo'].nunique().reset_index(name='Cantidad')
                    colores_personalizados = {
                        'MANTENIMIENTO': 'blue',
                        'PERDIDA': 'red',
                        'PRODUCTIVO': 'green',
                        'NAO CADASTRADO':'grey'
                    }
                    fig, ax = plt.subplots(figsize=(8, 2))  # Gráfico más pequeño
                    sns.barplot(data=resumen, x='Grupo Operacion', y='Cantidad', palette=colores_personalizados, ax=ax)
                    ax.set_title("Equipos por Estado Operativo")
                    ax.set_ylim(0, resumen['Cantidad'].max() * 1.2)
                    for container in ax.containers:
                        ax.bar_label(container, label_type='edge', padding=3)
                    st.pyplot(fig)
                    st.dataframe(resumen)

        with tabs[1]:
            st.subheader("📈 % del Tiempo que los Equipos Fueron Productivos")

            tiempo_total = df_filtrado_global.groupby('Equipo')['tiempo_seg'].sum().reset_index(name='tiempo_total_seg')
            tiempo_prod = df_filtrado_global[df_filtrado_global['Grupo Operacion'] == 'PRODUCTIVO'].groupby('Equipo')['tiempo_seg'].sum().reset_index(name='tiempo_productivo_seg')
            resumen = pd.merge(tiempo_total, tiempo_prod, on='Equipo', how='left').fillna(0)
            resumen['porcentaje_productivo'] = (resumen['tiempo_productivo_seg'] / resumen['tiempo_total_seg']) * 100
            resumen['tiempo_total_horas'] = resumen['tiempo_total_seg'] / 3600
            resumen['tiempo_productivo_horas'] = resumen['tiempo_productivo_seg'] / 3600

            fig, ax = plt.subplots(figsize=(8, 2))  # Gráfico más pequeño
            ax.hist(resumen['porcentaje_productivo'], bins=10, color='#4fc3f7', edgecolor='black')
            ax.set_title('Distribución de Productividad (%)')
            ax.set_xlabel('% Productivo')
            ax.set_ylabel('Cantidad de Equipos')
            st.pyplot(fig)
            st.dataframe(resumen[['Equipo', 'tiempo_total_horas', 'tiempo_productivo_horas', 'porcentaje_productivo']])

        with tabs[2]:
            st.subheader("⏳ Productividad por Hora")

            grupo_opciones = ["Todos"] + sorted(df_filtrado_global['grupo_equipo'].dropna().unique())
            grupo_filtro = st.selectbox("Filtrar por Grupo de Equipo / Frente", options=grupo_opciones)

            df_filtrado = df_filtrado_global if grupo_filtro == "Todos" else df_filtrado_global[df_filtrado_global['grupo_equipo'] == grupo_filtro]

            tiempos = df_filtrado.groupby(['Hora', 'Grupo Operacion'])['tiempo_seg'].sum().reset_index()
            total_hora = tiempos.groupby('Hora')['tiempo_seg'].sum().reset_index(name='tiempo_total')
            tiempos_prod = tiempos[tiempos['Grupo Operacion'] == 'PRODUCTIVO']
            resumen_hora = tiempos_prod.merge(total_hora, on='Hora', how='right').fillna(0)
            resumen_hora['porcentaje_productivo'] = (resumen_hora['tiempo_seg'] / resumen_hora['tiempo_total']) * 100

            st.line_chart(resumen_hora.set_index('Hora')['porcentaje_productivo'])

        with tabs[3]:
            st.subheader("📋 Clasificación de Rendimiento Acumulado")

            df_prod = df_filtrado_global[df_filtrado_global['Grupo Operacion'] == 'PRODUCTIVO']
            tiempo_prod = df_prod.groupby('Equipo')['tiempo_seg'].sum().reset_index(name='tiempo_productivo_seg')
            tiempo_total = df_filtrado_global.groupby('Equipo')['tiempo_seg'].sum().reset_index(name='tiempo_total_seg')
            resumen = pd.merge(tiempo_total, tiempo_prod, on='Equipo', how='left').fillna(0)
            resumen['porcentaje_productivo'] = (resumen['tiempo_productivo_seg'] / resumen['tiempo_total_seg']) * 100

            resumen['clasificacion'] = pd.cut(
                resumen['porcentaje_productivo'],
                bins=[-1, 60, 80, 100],
                labels=['Bajo', 'Medio', 'Alto']
            )

            col1, col2 = st.columns(2)
            with col1:
                clasif_counts = resumen['clasificacion'].value_counts().sort_index()
                fig1, ax1 = plt.subplots(figsize=(5, 3))  # Gráfico más pequeño
                ax1.pie(clasif_counts, labels=clasif_counts.index, autopct='%1.1f%%',
                        colors=['#ef5350', '#ffa726', '#66bb6a'], startangle=90)
                ax1.axis('equal')
                st.pyplot(fig1)
            with col2:
                resumen_equipo_clasif = resumen[['Equipo', 'clasificacion']]
                df_con_clasif = df_filtrado_global.merge(resumen_equipo_clasif, on='Equipo', how='left')

                df_con_clasif['tiempo_prod_seg'] = 0
                df_con_clasif.loc[df_con_clasif['Grupo Operacion'] == 'PRODUCTIVO', 'tiempo_prod_seg'] = df_con_clasif['tiempo_seg']

                resumen_grupo = df_con_clasif.groupby(['grupo_equipo', 'clasificacion'])[['tiempo_prod_seg']].sum().reset_index()

                total_por_grupo = resumen_grupo.groupby('grupo_equipo')['tiempo_prod_seg'].sum().reset_index()
                total_por_grupo = total_por_grupo.rename(columns={'tiempo_prod_seg': 'tiempo_total_grupo'})

                resumen_grupo = resumen_grupo.merge(total_por_grupo, on='grupo_equipo')
                resumen_grupo['porcentaje_productivo'] = (resumen_grupo['tiempo_prod_seg'] / resumen_grupo['tiempo_total_grupo']) * 100

                tabla_pivot = resumen_grupo.pivot(index='grupo_equipo', columns='clasificacion', values='porcentaje_productivo').fillna(0)
                tabla_pivot = tabla_pivot[['Bajo', 'Medio', 'Alto']]

                fig2, ax2 = plt.subplots(figsize=(5, 3))  # Gráfico más pequeño
                tabla_pivot.plot(kind='bar', stacked=True, color=['#ef5350', '#ffa726', '#66bb6a'], ax=ax2)
                ax2.set_ylabel('Porcentaje Productivo (%)')
                ax2.set_title('Clasificación por Grupo de Equipo')
                st.pyplot(fig2)

            resumen_sorted = resumen.sort_values(by='porcentaje_productivo', ascending=False)
            st.dataframe(resumen_sorted[['Equipo', 'porcentaje_productivo', 'clasificacion']], use_container_width=True)

    elif pestaña == "🚨 Alertas equipos parados o en mantenimiento":
        st.header("🚨 Equipos con Alta Inactividad")

        tiempo_total = df_filtrado_global.groupby('Equipo')['tiempo_seg'].sum()
        mant = df_filtrado_global[df_filtrado_global['Grupo Operacion'] == 'MANTENIMIENTO'].groupby('Equipo')['tiempo_seg'].sum()
        parado = df_filtrado_global[~df_filtrado_global['Grupo Operacion'].isin(['PRODUCTIVO', 'MANTENIMIENTO'])].groupby('Equipo')['tiempo_seg'].sum()

        resumen = pd.DataFrame({
            'tiempo_total_horas': tiempo_total / 3600,
            'tiempo_mantenimiento_horas': mant / 3600,
            'tiempo_parado_horas': parado / 3600
        }).fillna(0)

        resumen['% mantenimiento'] = resumen['tiempo_mantenimiento_horas'] / resumen['tiempo_total_horas'] * 100
        resumen['% parado'] = resumen['tiempo_parado_horas'] / resumen['tiempo_total_horas'] * 100
        resumen['% alerta total'] = resumen['% mantenimiento'] + resumen['% parado']
        resumen['comentario'] = resumen.apply(lambda r: '🛠 100% mantenimiento' if r['% mantenimiento'] == 100 else ('🟥 100% parado' if r['% parado'] == 100 else '🚨 Inactivo >80%' if r['% alerta total'] >= 80 else '🔔 Alta inactividad'), axis=1)

        alertas = resumen[resumen['% alerta total'] > 60]
        comentarios = alertas[alertas['comentario'] != '']

        if not comentarios.empty:
            st.subheader("🔔 Equipos con Inactividad Total o Crítica")
            agrupado = alertas.groupby('comentario').apply(lambda df: ', '.join(df.index.astype(str))).reset_index(name='equipos')
            for _, fila in agrupado.iterrows():
                st.markdown(f"- **Equipos {fila['equipos']}**: {fila['comentario']}")
        else:
            st.info("No se detectaron equipos con inactividad crítica.")

        st.dataframe(alertas)

    elif pestaña == "📍 Recorrido y Hora Inicio Labor":
        st.header("📍 Visualización de Recorridos y Hora de Inicio de Labores")

        columnas_requeridas = ['Latitud', 'Longitud', 'Velocidad']
        faltantes = [col for col in columnas_requeridas if col not in df_filtrado_global.columns]

        if faltantes:
            st.error(f"❌ Faltan columnas requeridas en el archivo: {', '.join(faltantes)}")
            st.stop()

        for col in columnas_requeridas:
            df_filtrado_global[col] = pd.to_numeric(df_filtrado_global[col], errors='coerce')

        df_filtrado_global = df_filtrado_global.dropna(subset=['Latitud', 'Longitud'])

        st.subheader("📋 Resumen de Inicio de Labores por Grupo Equipo / Frente")

        def obtener_hora_inicio_grupo(equipo_df):
            datos_labor = equipo_df[equipo_df['Velocidad'] > 7]
            if not datos_labor.empty:
                return datos_labor['Fecha/Hora'].iloc[0]
            else:
                return "Equipo sin inicio de labor"

        inicio_por_equipo = []
        for grupo, grupo_df in df_filtrado_global.groupby('grupo_equipo'):
            for equipo in grupo_df['Equipo'].unique():
                equipo_df = df_filtrado_global[df_filtrado_global['Equipo'] == equipo]
                hora_inicio = obtener_hora_inicio_grupo(equipo_df)
                inicio_por_equipo.append({
                    'Grupo Equipo/Frente': grupo,
                    'Equipo': equipo,
                    'Hora Inicio': hora_inicio
                })

        inicio_por_equipo_df = pd.DataFrame(inicio_por_equipo)
        st.dataframe(inicio_por_equipo_df, use_container_width=True)

        equipos_disponibles = df_filtrado_global['Equipo'].unique()
        if len(equipos_disponibles) == 0:
            st.warning("No hay equipos disponibles con datos geográficos.")
        else:
            equipo_seleccionado = st.selectbox("Selecciona un equipo para ver su recorrido", equipos_disponibles)

            datos_equipo = df_filtrado_global[df_filtrado_global['Equipo'] == equipo_seleccionado].sort_values(by='Fecha/Hora')

            if datos_equipo.empty:
                st.error("No hay datos para este equipo.")
            else:
                centro = [datos_equipo['Latitud'].mean(), datos_equipo['Longitud'].mean()]
                mapa = folium.Map(location=centro, zoom_start=13)

                puntos_linea = [[row['Latitud'], row['Longitud']] for _, row in datos_equipo.iterrows()]
                if len(puntos_linea) >= 2:
                    AntPath(locations=puntos_linea, color='green', weight=4, delay=800).add_to(mapa)
                else:
                    st.warning("No hay suficientes puntos para trazar la ruta.")

                cluster = MarkerCluster().add_to(mapa)
                paradas = []

                for _, row in datos_equipo.iterrows():
                    estado = str(row['Grupo Operacion']).strip().upper()
                    if estado in ['PERDIDA', 'MANTENIMIENTO']:
                        paradas.append([row['Latitud'], row['Longitud']])

                if paradas:
                    Marker(
                        location=[datos_equipo['Latitud'].mean(), datos_equipo['Longitud'].mean()],
                        popup=f"Total de Paradas: {len(paradas)}",
                        icon=Icon(color='red', icon='cloud', prefix='fa')
                    ).add_to(cluster)

                datos_labor = datos_equipo[datos_equipo['Velocidad'] > 7]
                if not datos_labor.empty:
                    inicio = datos_labor['Fecha/Hora'].iloc[0]
                    fin = datos_labor['Fecha/Hora'].iloc[-1]
                    duracion = fin - inicio

                    puntos_labor = list(zip(datos_labor['Latitud'], datos_labor['Longitud']))
                    distancia = sum(geodesic(p1, p2).meters for p1, p2 in zip(puntos_labor[:-1], puntos_labor[1:]))

                    Marker(
                        location=[datos_labor['Latitud'].iloc[0], datos_labor['Longitud'].iloc[0]],
                        icon=Icon(color='green', icon='play')
                    ).add_to(mapa)
                    Marker(
                        location=[datos_labor['Latitud'].iloc[-1], datos_labor['Longitud'].iloc[-1]],
                        icon=Icon(color='red', icon='stop')
                    ).add_to(mapa)

                    st.subheader("📊 Estadísticas de Labor")
                    st.write(f"**Hora de inicio:** {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
                    st.write(f"**Hora de fin:** {fin.strftime('%d/%m/%Y %H:%M:%S')}")
                    st.write(f"**Duración estimada:** {duracion}")
                    st.write(f"**Distancia recorrida:** {distancia / 1000:.2f} km")
                else:
                    st.warning("No se encontró velocidad > 7 km/h para este equipo. No se pueden calcular inicio/fin de labores.")

                # 🗺️ MAPA REDIMENSIONADO — más compacto
                st_folium(mapa, width=1700, height=600)

else:
    st.info("⬅️ Por favor, cargue un archivo para comenzar.")
#python -m streamlit run c:/Users/sacor/Downloads/resumen_monitoreo3.py






