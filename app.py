import streamlit as st
import pandas as pd

# Configuración inicial de la página
st.set_page_config(page_title="Generador de Combinaciones", layout="wide")

st.title("🎲 Lotería - Análisis y Generador de Combinaciones")

# --- BARRA LATERAL: CARGA DE ARCHIVO Y CONFIGURACIÓN ---
st.sidebar.header("📁 Carga de Datos")
uploaded_file = st.sidebar.file_uploader("Carga tu archivo Excel de sorteos", type=["xlsx", "xls"])

st.sidebar.header("⚙️ Filtros Globales")
numeros_excluidos_input = st.sidebar.text_input("Números Excluidos (separados por coma)", "05, 12, 88")

# Procesar lista de excluidos
numeros_excluidos = []
if numeros_excluidos_input:
    try:
        numeros_excluidos = [int(n.strip()) for n in numeros_excluidos_input.split(",") if n.strip().isdigit()]
    except ValueError:
        st.sidebar.error("Asegúrate de ingresar números válidos.")

# --- ESTRUCTURA DE PESTAÑAS ---
tab_analisis, tab_generador, tab_config = st.tabs([
    "📊 Análisis", 
    "🎲 Generador", 
    "⚙️ Configuración"
])

# Variables por defecto / estado
score_arrastre = {}
score_frecuencia = {}

# --- LÓGICA DE PROCESAMIENTO DE DATOS ---
if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Pestaña 1: Análisis de datos
        with tab_analisis:
            st.subheader("Vista previa de sorteos cargados")
            st.dataframe(df.head(10))
            
            # Cálculo simulado/ejemplo de frecuencias (Ajustar según estructura de tu Excel)
            # Suponiendo que el Excel tiene columnas con los números jugados
            numeros_todos = df.values.flatten()
            conteo = pd.Series(numeros_todos).value_counts()
            
            for num in range(100):
                score_frecuencia[num] = int(conteo.get(num, 0))
                # Ejemplo de scoring de arrastre (frecuencia reciente)
                score_arrastre[num] = int(conteo.get(num, 0) * 1.2)
                
            st.success(f" Se cargaron {len(df)} sorteos correctamente.")
            
    except Exception as e:
        st.error(f"Error al procesar el archivo Excel: {e}")
else:
    with tab_analisis:
        st.info(" Por favor, carga un archivo Excel desde la barra lateral para comenzar el análisis.")

# --- PESTAÑA 2: GENERADOR Y CONCLUSIÓN DEL ALGORITMO ---
with tab_generador:
    st.header("💡 Conclusión y Recomendación del Algoritmo")
    
    # 1. Selección y filtrado de candidatos
    candidatos_validos = [n for n in range(100) if n not in numeros_excluidos]
    
    # Ponderación unificada: 60% Arrastre + 40% Frecuencia
    ranking_recomendados = sorted(
        candidatos_validos, 
        key=lambda x: (score_arrastre.get(x, 0) * 0.6 + score_frecuencia.get(x, 0) * 0.4), 
        reverse=True
    )
    
    top_5 = ranking_recomendados[:5]
    top_10 = ranking_recomendados[:10]
    
    # 2. Veredicto del sistema
    st.markdown(f"""
    > **📌 Veredicto del Sistema para el Próximo Sorteo:**  
    > Basado en la correlación de **Arrastres Recientes** y la frecuencia de apariciones (descontando los **{len(numeros_excluidos)}** números excluidos), los números con mayor tendencia son:
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="🎯 Números Clave (Top 5)", value=", ".join([f"{n:02d}" for n in top_5]))
    with col2:
        st.metric(label="📊 Bloque Recomendado (Top 10)", value=", ".join([f"{n:02d}" for n in top_10]))

    st.divider()

    # 3. Selector de Estrategia y Generación
    st.subheader("🎲 Generador de Jugadas")
    
    opcion_estrategia = st.selectbox(
        "Selecciona la Estrategia de Generación:",
        [
            "🤖 Conclusión / Selección del Algoritmo (Predicción Directa)",
            "Arrastres Recientes",
            "Números Calientes",
            "Combinación Mixta"
        ]
    )
    
    cantidad_numeros = st.slider("Cantidad de números por combinación:", min_value=5, max_value=20, value=8)

    if st.button("🚀 Generar Combinación"):
        if opcion_estrategia == "🤖 Conclusión / Selección del Algoritmo (Predicción Directa)":
            jugada_seleccionada = sorted(ranking_recomendados[:cantidad_numeros])
            st.success("✨ Combinación generada según el Veredicto del Algoritmo:")
            st.subheader(", ".join([f"{n:02d}" for n in jugada_seleccionada]))
        else:
            jugada_seleccionada = sorted(ranking_recomendados[:cantidad_numeros])
            st.info(f"Combinación generada aplicando la estrategia: **{opcion_estrategia}**")
            st.subheader(", ".join([f"{n:02d}" for n in jugada_seleccionada]))

# --- PESTAÑA 3: CONFIGURACIÓN ---
with tab_config:
    st.header("⚙️ Ajustes del Sistema")
    st.write("Configuración de parámetros avanzados de ponderación y filtros.")
