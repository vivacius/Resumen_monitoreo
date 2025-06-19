import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="Monitoreo de Productividad de Equipos", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #f9fbfc; color: #222; font-family: 'Segoe UI', sans-serif; }
[data-testid="stSidebar"] { width: 280px; background-color: #1f4e79; color: white; font-weight: bold; }
[data-testid="stSidebar"] .css-1d391kg, .stRadio label { color: white !important; }
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

    pestaña = st.sidebar.radio("Seleccione una vista", [
        "📊 Análisis de Productividad",
        "🚨 Alertas equipos parados o en mantenimiento"
    ])

    if pestaña == "📊 Análisis de Productividad":
        st.header("📊 Análisis de Productividad Acumulada y Horaria")

        tabs = st.tabs(["📌 Último Estado", "📈 % Productivo por Equipo", "⏳ Evolución Horaria", "📋 Clasificación Acumulada"])

        with tabs[0]:
            st.subheader("📌 Resumen por Grupo de Operación a una Hora Específica")
            hora_opciones = sorted(df['Hora'].dt.time.unique())
            hora_str = st.selectbox("Seleccione la hora de evaluación", options=hora_opciones)
            fecha = st.date_input("Seleccione la fecha", value=df['Fecha/Hora'].min().date())
            hora_obj = pd.Timestamp.combine(fecha, hora_str.replace(minute=0, second=0, microsecond=0))

            df_hora = df[df['Hora'] == hora_obj]
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
                fig, ax = plt.subplots(figsize=(8, 4))
                sns.barplot(data=resumen, x='Grupo Operacion', y='Cantidad', palette=colores_personalizados, ax=ax)
                ax.set_title("Equipos por Estado Operativo")
                ax.set_ylim(0, resumen['Cantidad'].max() * 1.2)
                for container in ax.containers:
                    ax.bar_label(container, label_type='edge', padding=3)
                st.pyplot(fig)
                st.dataframe(resumen)

        with tabs[1]:
            st.subheader("📈 % del Tiempo que los Equipos Fueron Productivos")

            tiempo_total = df.groupby('Equipo')['tiempo_seg'].sum().reset_index(name='tiempo_total_seg')
            tiempo_prod = df[df['Grupo Operacion'] == 'PRODUCTIVO'].groupby('Equipo')['tiempo_seg'].sum().reset_index(name='tiempo_productivo_seg')
            resumen = pd.merge(tiempo_total, tiempo_prod, on='Equipo', how='left').fillna(0)
            resumen['porcentaje_productivo'] = (resumen['tiempo_productivo_seg'] / resumen['tiempo_total_seg']) * 100
            resumen['tiempo_total_horas'] = resumen['tiempo_total_seg'] / 3600
            resumen['tiempo_productivo_horas'] = resumen['tiempo_productivo_seg'] / 3600

            fig, ax = plt.subplots()
            ax.hist(resumen['porcentaje_productivo'], bins=10, color='#4fc3f7', edgecolor='black')
            ax.set_title('Distribución de Productividad (%)')
            ax.set_xlabel('% Productivo')
            ax.set_ylabel('Cantidad de Equipos')
            st.pyplot(fig)
            st.dataframe(resumen[['Equipo', 'tiempo_total_horas', 'tiempo_productivo_horas', 'porcentaje_productivo']])

        with tabs[2]:
            st.subheader("⏳ Productividad por Hora")

            grupo_opciones = ["Todos"] + sorted(df['grupo_equipo'].dropna().unique())
            grupo_filtro = st.selectbox("Filtrar por Grupo de Equipo / Frente", options=grupo_opciones)

            df_filtrado = df if grupo_filtro == "Todos" else df[df['grupo_equipo'] == grupo_filtro]

            tiempos = df_filtrado.groupby(['Hora', 'Grupo Operacion'])['tiempo_seg'].sum().reset_index()
            total_hora = tiempos.groupby('Hora')['tiempo_seg'].sum().reset_index(name='tiempo_total')
            tiempos_prod = tiempos[tiempos['Grupo Operacion'] == 'PRODUCTIVO']
            resumen_hora = tiempos_prod.merge(total_hora, on='Hora', how='right').fillna(0)
            resumen_hora['porcentaje_productivo'] = (resumen_hora['tiempo_seg'] / resumen_hora['tiempo_total']) * 100

            st.line_chart(resumen_hora.set_index('Hora')['porcentaje_productivo'])

        with tabs[3]:
            st.subheader("📋 Clasificación de Rendimiento Acumulado")

            df_prod = df[df['Grupo Operacion'] == 'PRODUCTIVO']
            tiempo_prod = df_prod.groupby('Equipo')['tiempo_seg'].sum().reset_index(name='tiempo_productivo_seg')
            tiempo_total = df.groupby('Equipo')['tiempo_seg'].sum().reset_index(name='tiempo_total_seg')
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
                fig1, ax1 = plt.subplots(figsize=(4, 4))
                ax1.pie(clasif_counts, labels=clasif_counts.index, autopct='%1.1f%%',
                        colors=['#ef5350', '#ffa726', '#66bb6a'], startangle=90)
                ax1.axis('equal')
                st.pyplot(fig1)
            with col2:
                     # Fusionar clasificación con el dataframe original
                    resumen_equipo_clasif = resumen[['Equipo', 'clasificacion']]
                    df_con_clasif = df.merge(resumen_equipo_clasif, on='Equipo', how='left')

                    # Crear columna de tiempo productivo
                    df_con_clasif['tiempo_prod_seg'] = 0
                    df_con_clasif.loc[df_con_clasif['Grupo Operacion'] == 'PRODUCTIVO', 'tiempo_prod_seg'] = df_con_clasif['tiempo_seg']

                    # Agrupar por grupo y clasificación
                    resumen_grupo = df_con_clasif.groupby(['grupo_equipo', 'clasificacion'])[['tiempo_prod_seg']].sum().reset_index()

                    # Calcular el tiempo total productivo por grupo
                    total_por_grupo = resumen_grupo.groupby('grupo_equipo')['tiempo_prod_seg'].sum().reset_index()
                    total_por_grupo = total_por_grupo.rename(columns={'tiempo_prod_seg': 'tiempo_total_grupo'})

                    # Unir para tener el total del grupo en cada fila
                    resumen_grupo = resumen_grupo.merge(total_por_grupo, on='grupo_equipo')

                    # Calcular porcentaje dentro del grupo
                    resumen_grupo['porcentaje_productivo'] = (resumen_grupo['tiempo_prod_seg'] / resumen_grupo['tiempo_total_grupo']) * 100

                    # Pivot para gráfico
                    tabla_pivot = resumen_grupo.pivot(index='grupo_equipo', columns='clasificacion', values='porcentaje_productivo').fillna(0)
                    tabla_pivot = tabla_pivot[['Bajo', 'Medio', 'Alto']]  # asegúrate de que existan las columnas

                    # Graficar
                    fig2, ax2 = plt.subplots(figsize=(6, 4))
                    tabla_pivot.plot(kind='bar', stacked=True, color=['#ef5350', '#ffa726', '#66bb6a'], ax=ax2)
                    ax2.set_ylabel('Porcentaje Productivo (%)')
                    ax2.set_title('Clasificación por Grupo de Equipo')
                    st.pyplot(fig2)

            resumen_sorted = resumen.sort_values(by='porcentaje_productivo', ascending=False)
            st.dataframe(resumen_sorted[['Equipo', 'porcentaje_productivo', 'clasificacion']], use_container_width=True)

    elif pestaña == "🚨 Alertas equipos parados o en mantenimiento":
        st.header("🚨 Equipos con Alta Inactividad")

        tiempo_total = df.groupby('Equipo')['tiempo_seg'].sum()
        mant = df[df['Grupo Operacion'] == 'MANTENIMIENTO'].groupby('Equipo')['tiempo_seg'].sum()
        parado = df[~df['Grupo Operacion'].isin(['PRODUCTIVO', 'MANTENIMIENTO'])].groupby('Equipo')['tiempo_seg'].sum()

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
            # Agrupamos por comentario y juntamos los equipos en una lista
            agrupado = alertas.groupby('comentario').apply(lambda df: ', '.join(df.index.astype(str))).reset_index(name='equipos')
        
        # Mostramos mensajes resumidos
            for _, fila in agrupado.iterrows():
                st.markdown(f"- **Equipos {fila['equipos']}**: {fila['comentario']}")
        else:
            st.info("No se detectaron equipos con inactividad crítica.")

        st.dataframe(alertas)

else:
    st.info("⬅️ Por favor, cargue un archivo para comenzar.")
#python -m streamlit run c:/Users/sacor/Downloads/resumen_monitoreo3.py
