# Dentro del bloque de la pestaña "Generador"
with tab_generador:
    st.header("💡 Conclusión y Recomendación del Algoritmo")
    
    # 1. Selección/Cálculo de los mejores candidatos según métricas combinadas
    # Se filtran los números que no están en la lista global de excluidos
    candidatos_validos = [n for n in range(100) if n not in numeros_excluidos]
    
    # Ejemplo de scoring combinando Arrastre + Frecuencia Reciente
    # (Ajusta 'score_arrastre' y 'score_frecuencia' según tus variables)
    ranking_recomendados = sorted(
        candidatos_validos, 
        key=lambda x: (score_arrastre.get(x, 0) * 0.6 + score_frecuencia.get(x, 0) * 0.4), 
        reverse=True
    )
    
    top_5 = ranking_recomendados[:5]
    top_10 = ranking_recomendados[:10]
    
    # 2. Presentación visual del veredicto
    st.markdown(f"""
    > **📌 Veredicto del Sistema para el Próximo Sorteo:**  
    > Basado en la correlación de **Arrastres Recientes** y la frecuencia de las últimas jugadas (descontando los {len(numeros_excluidos)} números excluidos por filtros globales), los números con mayor probabilidad de salir son:
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="🎯 Números Clave (Top 5)", value=", ".join([f"{n:02d}" for n in top_5]))
    with col2:
        st.metric(label="📊 Bloque Recomendado (Top 10)", value=", ".join([f"{n:02d}" for n in top_10]))

    st.divider()

    # 3. Integración con una nueva estrategia del selector
    opcion_estrategia = st.selectbox(
        "Selecciona la Estrategia de Generación:",
        [
            "Arrastres Recientes",
            "Números Calientes",
            "🤖 Conclusión / Selección del Algoritmo (Predicción Directa)",
            "Combinación Mixta"
        ]
    )

    if opcion_estrategia == "🤖 Conclusión / Selección del Algoritmo (Predicción Directa)":
        st.success("Esta estrategia utilizará prioritariamente el Top de números concluidos por el sistema.")
        # Lógica para armar la jugada (5, 6, 8, etc. números) basada en 'top_10' o 'ranking_recomendados'
