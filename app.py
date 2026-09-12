import streamlit as st
import pandas as pd
import numpy as np
import itertools, random, os

st.set_page_config(page_title="Quiniela Chaqueña Pro", layout="wide")
st.title("🎯 Quiniela Chaqueña Pro - Análisis y Generador")
st.caption("Análisis estadístico, backtesting y generación de líneas. No representa una predicción garantizada.")

# --- BARRA LATERAL: CARGA DE ARCHIVO Y CONFIGURACIÓN ---
st.sidebar.header("📁 Carga de Datos")
uploaded = st.sidebar.file_uploader("Cargá el Excel de sorteos", type=["xlsx", "xls"])

st.sidebar.header("⚙️ Filtros Globales")
numeros_excluidos_input = st.sidebar.text_input("Números Excluidos manualmente (separados por coma)", "05, 12, 88")

# Procesar lista de números excluidos manualmente
manual_exclude = set()
if numeros_excluidos_input:
    try:
        manual_exclude = {int(n.strip()) for n in numeros_excluidos_input.split(",") if n.strip().isdigit() and 0 <= int(n.strip()) <= 99}
    except ValueError:
        st.sidebar.error("Ingresá números válidos entre 00 y 99.")

def prepare(df):
    cols = [f"{i}°" for i in range(1, 21)]
    if not all(c in df.columns for c in cols):
        raise ValueError("El Excel debe contener las columnas 1° a 20°.")
    X = df[cols].apply(pd.to_numeric, errors="coerce").dropna(how="all")
    return X.astype(int).values

def get_adaptive_weights(vals, lookback=15):
    """
    Evalúa qué métricas tuvieron mayor precisión en los últimos 'lookback' sorteos
    y retorna pesos optimizados dinámicamente.
    """
    if len(vals) < lookback + 30:
        return {"w_freq": 0.30, "w_rc10": 0.25, "w_rc30": 0.15, "w_rc20": 0.10, "w_gap": 0.15, "w_last": 0.05}

    scores = {"freq": 0, "rc10": 0, "rc30": 0, "rc20": 0, "gap": 0, "last": 0}
    nums = range(100)

    for i in range(1, lookback + 1):
        hist = vals[i:]
        actual = set(vals[i-1])
        n = len(hist)

        f = pd.Series(hist.ravel()).value_counts().reindex(nums, fill_value=0)
        r10 = pd.Series(hist[:min(10, n)].ravel()).value_counts().reindex(nums, fill_value=0)
        r20 = pd.Series(hist[:min(20, n)].ravel()).value_counts().reindex(nums, fill_value=0)
        r30 = pd.Series(hist[:min(30, n)].ravel()).value_counts().reindex(nums, fill_value=0)

        gaps = {}
        for x in nums:
            rows = np.where((hist == x).any(axis=1))[0]
            gaps[x] = int(rows[0]) if len(rows) else n
        g_series = pd.Series({x: 1 / (gaps[x] + 1) for x in nums})

        last_set = pd.Series({x: int(x in set(hist[0])) for x in nums})

        scores["freq"] += len(set(f.nlargest(20).index) & actual)
        scores["rc10"] += len(set(r10.nlargest(20).index) & actual)
        scores["rc20"] += len(set(r20.nlargest(20).index) & actual)
        scores["rc30"] += len(set(r30.nlargest(20).index) & actual)
        scores["gap"] += len(set(g_series.nlargest(20).index) & actual)
        scores["last"] += len(set(last_set.nlargest(20).index) & actual)

    total = sum(scores.values())
    if total == 0:
        return {"w_freq": 0.30, "w_rc10": 0.25, "w_rc30": 0.15, "w_rc20": 0.10, "w_gap": 0.15, "w_last": 0.05}

    return {
        "w_freq": round(scores["freq"] / total, 3),
        "w_rc10": round(scores["rc10"] / total, 3),
        "w_rc30": round(scores["rc30"] / total, 3),
        "w_rc20": round(scores["rc20"] / total, 3),
        "w_gap": round(scores["gap"] / total, 3),
        "w_last": round(scores["last"] / total, 3)
    }

def model(vals, weights=None):
    n = len(vals)
    nums = range(100)
    freq = pd.Series(vals.ravel()).value_counts().reindex(nums, fill_value=0)
    rc = {w: pd.Series(vals[:min(w, n)].ravel()).value_counts().reindex(nums, fill_value=0) for w in [5, 10, 20, 30]}
    gaps = {}
    for x in nums:
        rows = np.where((vals == x).any(axis=1))[0]
        gaps[x] = int(rows[0]) if len(rows) else n
    last = set(vals[0])
    pct = lambda s: s.rank(pct=True, method="average")

    if weights is None:
        weights = {"w_freq": 0.30, "w_rc10": 0.25, "w_rc30": 0.15, "w_rc20": 0.10, "w_gap": 0.15, "w_last": 0.05}

    score = 100 * (
        weights["w_freq"] * pct(freq) +
        weights["w_rc10"] * pct(rc[10]) +
        weights["w_rc30"] * pct(rc[30]) +
        weights["w_rc20"] * pct(rc[20]) +
        weights["w_gap"] * pct(pd.Series({x: 1 / (gaps[x] + 1) for x in nums})) +
        weights["w_last"] * pct(pd.Series({x: int(x in last) for x in nums}))
    )
    return freq, rc, gaps, last, score.sort_values(ascending=False)

def analyze_rep_inter(vals, n):
    sub = vals[:min(len(vals), n)]
    rep = set()
    for i in range(len(sub) - 1):
        rep.update(set(sub[i]) & set(sub[i+1]))
    return rep

def analyze_rep_intra(vals, n):
    sub = vals[:min(len(vals), n)]
    rep = set()
    for row in sub:
        counts = pd.Series(row).value_counts()
        rep.update(counts[counts > 1].index)
    return rep

def analyze_consecutivos(vals, n):
    sub = vals[:min(len(vals), n)]
    cons = set()
    for row in sub:
        sorted_row = sorted(set(row))
        for a, b in zip(sorted_row, sorted_row[1:]):
            if b == a + 1:
                cons.add(a)
                cons.add(b)
    return cons

def select_by_strategy(score, freq, gaps, last, vals, line_size, strategy, exclude_nums):
    available_score = score[~score.index.isin(exclude_nums)]
    available = list(available_score.index)

    if len(available) < line_size:
        return []

    if strategy == "🤖 Conclusión / Selección del Algoritmo (Predicción Directa)":
        candidates = available[:line_size]
    elif strategy == "🔥 Números Calientes":
        candidates = list(available_score.head(max(line_size * 2, 20)).index)
    elif strategy == "🧊 Fríos / Atrasados":
        sorted_by_gap = pd.Series(gaps)[available].sort_values(ascending=False)
        candidates = list(sorted_by_gap.head(max(line_size * 2, 20)).index)
    elif strategy == "⚖️ Mixta Equilibrada":
        p1 = available[:max(1, int(len(available)*0.3))]
        p2 = available[int(len(available)*0.3):int(len(available)*0.7)]
        p3 = available[int(len(available)*0.7):]
        candidates = p1 + p2 + p3
    elif strategy == "🎯 Zonas Activas":
        decenas = pd.Series([x // 10 for x in available]).value_counts()
        top_decenas = decenas.head(4).index
        candidates = [x for x in available if x // 10 in top_decenas]
    elif strategy == "🔗 Arrastres Recientes":
        pair_counts = {}
        for row in vals[:20]:
            for x in set(row):
                if x in available:
                    pair_counts[x] = pair_counts.get(x, 0) + 1
        sorted_arrastre = sorted(pair_counts.keys(), key=lambda k: pair_counts[k], reverse=True)
        candidates = sorted_arrastre if len(sorted_arrastre) >= line_size else available
    elif strategy == "🔄 Repetición Sorteo Anterior":
        last_avail = [x for x in vals[0] if x in available]
        candidates = last_avail + [x for x in available if x not in last_avail]
    else:
        candidates = available

    if len(candidates) < line_size:
        candidates = available

    return candidates

def generate(score, freq, gaps, last, vals, amount, seed, line_size=20, strategy="⚖️ Mixta Equilibrada", exclude_nums=set()):
    rng = random.Random(int(seed))
    candidates = select_by_strategy(score, freq, gaps, last, vals, line_size, strategy, exclude_nums)

    if len(candidates) < line_size:
        st.error(f"No hay suficientes números candidatos ({len(candidates)}) para armar líneas de {line_size} números.")
        return []

    lines = []
    for _ in range(amount):
        for _try in range(10000):
            sample_k = min(len(candidates), max(line_size + 5, int(line_size * 1.5)))
            pool = rng.sample(candidates[:sample_k], line_size)
            comb = set(pool)

            if len(comb) != line_size:
                continue

            odd = sum(x % 2 for x in comb)
            min_odd = int(line_size * 0.35)
            max_odd = int(line_size * 0.65) + 1

            if min_odd <= odd <= max_odd and not any(len(comb & set(o)) >= line_size for o in lines):
                lines.append(sorted(comb))
                break

    return lines

def backtest(vals, cases, exclude_nums=set(), weights=None):
    rows = []
    for i in range(1, min(len(vals) - 1, cases) + 1):
        hist = vals[i + 1:]
        if len(hist) < 30:
            break
        _, _, _, _, s = model(hist, weights=weights)

        s_filtered = s[~s.index.isin(exclude_nums)]
        top20 = list(s_filtered.index[:20])

        ganadores = list(vals[i])
        coincidencias = sorted(list(set(top20) & set(ganadores)))

        rows.append({
            "Indice_sorteo": i,
            "Aciertos_Top20": len(coincidencias),
            "Esperado_azar": 4.0,
            "Top20_Sugeridos": ", ".join(f"{x:02d}" for x in top20),
            "Ganadores": ", ".join(f"{x:02d}" for x in ganadores),
            "Coincidencias": ", ".join(f"{x:02d}" for x in coincidencias)
        })
    return pd.DataFrame(rows)

# Carga de archivo Excel
if uploaded:
    df = pd.read_excel(uploaded)
else:
    default = "Extracto_Loteria_Chaquena_Ultimas_2_Cifras_para análisis.xlsx"
    if os.path.exists(default):
        df = pd.read_excel(default)
    else:
        st.info("Por favor, cargá un archivo Excel desde la barra lateral para comenzar el análisis.")
        st.stop()

try:
    vals = prepare(df)
except Exception as e:
    st.error(f"Error al procesar el archivo Excel: {e}")
    st.stop()

# Sidebar - Modo de Auto-Aprendizaje
st.sidebar.header("🤖 Modo de Auto-Aprendizaje")
use_auto_weights = st.sidebar.toggle("Activar Auto-Optimización de Pesos", value=True)

if use_auto_weights:
    lookback_eval = st.sidebar.slider("Sorteos de evaluación para aprendizaje", 5, 50, 15)
    auto_weights = get_adaptive_weights(vals, lookback=lookback_eval)
    active_weights = auto_weights
    st.sidebar.success("✅ Pesos ajustados según aciertos recientes")
else:
    active_weights = {"w_freq": 0.30, "w_rc10": 0.25, "w_rc30": 0.15, "w_rc20": 0.10, "w_gap": 0.15, "w_last": 0.05}

# Sidebar - Filtros de Descarte Dinámicos
st.sidebar.header("🧹 Filtros de Descarte Dinámicos")
n_inter = st.sidebar.number_input("Sorteos (Rep. entre sorteos)", 2, len(vals), 15, key="n_inter")
f_inter = st.sidebar.checkbox("Excluir rep. entre sorteos", value=False, key="f_inter")

n_intra = st.sidebar.number_input("Sorteos (Rep. internas)", 1, len(vals), 10, key="n_intra")
f_intra = st.sidebar.checkbox("Excluir rep. internas", value=False, key="f_intra")

n_cons = st.sidebar.number_input("Sorteos (Consecutivos)", 1, len(vals), 15, key="n_cons")
f_cons = st.sidebar.checkbox("Excluir consecutivos", value=False, key="f_cons")

f_ult1 = st.sidebar.checkbox("Excluir ÚLTIMO sorteo", value=False, key="f_ult1")
f_ult2 = st.sidebar.checkbox("Excluir PENÚLTIMO sorteo", value=False, key="f_ult2")

# Unificar exclusiones manuales y dinámicas
nums_a_excluir = set(manual_exclude)
if f_inter: nums_a_excluir.update(analyze_rep_inter(vals, n_inter))
if f_intra: nums_a_excluir.update(analyze_rep_intra(vals, n_intra))
if f_cons: nums_a_excluir.update(analyze_consecutivos(vals, n_cons))
if f_ult1: nums_a_excluir.update(vals[0])
if f_ult2 and len(vals) > 1: nums_a_excluir.update(vals[1])

if nums_a_excluir:
    st.sidebar.warning(f"🚫 {len(nums_a_excluir)} números excluidos de los 100.")

freq, rc, gaps, last, score = model(vals, weights=active_weights)

# --- PESTAÑAS PRINCIPALES ---
t1, t2, t3, t4, t5, t6 = st.tabs([
    "🏆 Ranking", 
    "🔗 Patrones", 
    "🧹 Filtros/Descarte", 
    "🧪 Backtesting", 
    "🎟️ Generador", 
    "🤖 Auto-Optimización"
])

with t1:
    st.header("🏆 Ranking General y Números Validados")
    st.subheader(f"Vista previa: Se cargaron {len(df)} sorteos correctamente.")
    
    r_full = pd.DataFrame({
        "Ranking Gral": range(1, 101),
        "Número": [f"{x:02d}" for x in score.index],
        "Estado": ["⛔ Excluido" if x in nums_a_excluir else "✅ Activo" for x in score.index],
        "Índice": [round(score[x], 2) for x in score.index],
        "Histórico": [int(freq[x]) for x in score.index],
        "Últ.10": [int(rc[10][x]) for x in score.index],
        "Últ.30": [int(rc[30][x]) for x in score.index],
        "Atraso": [gaps[x] for x in score.index],
        "Último": ["SI" if x in last else "NO" for x in score.index]
    })

    score_clean = score[~score.index.isin(nums_a_excluir)]
    r_clean = pd.DataFrame({
        "Ranking Activo": range(1, len(score_clean) + 1),
        "Número": [f"{x:02d}" for x in score_clean.index],
        "Índice": [round(score_clean[x], 2) for x in score_clean.index],
        "Histórico": [int(freq[x]) for x in score_clean.index],
        "Últ.10": [int(rc[10][x]) for x in score_clean.index],
        "Últ.30": [int(rc[30][x]) for x in score_clean.index],
        "Atraso": [gaps[x] for x in score_clean.index],
        "Último": ["SI" if x in last else "NO" for x in score_clean.index]
    })

    col_rk1, col_rk2 = st.columns(2)
    with col_rk1:
        st.subheader("📊 Ranking Completo (100 números)")
        st.dataframe(r_full, use_container_width=True, height=600)
    with col_rk2:
        st.subheader(f"✨ Ranking Filtrado ({len(r_clean)} números activos)")
        st.dataframe(r_clean, use_container_width=True, height=600)

    st.download_button("Descargar Ranking Filtrado CSV", r_clean.to_csv(index=False).encode(), "ranking_filtrado.csv")

with t2:
    rep = [len(set(vals[i]) & set(vals[i+1])) for i in range(len(vals)-1)]
    internal = [20 - len(set(x)) for x in vals]
    odd = [sum(x % 2 for x in row) for row in vals]
    cons = [sum(1 for a, b in zip(sorted(set(row)), sorted(set(row))[1:]) if b == a + 1) for row in vals]
    a, b, c, d = st.columns(4)
    a.metric("Repetidos entre sorteos", f"{np.mean(rep):.2f}")
    b.metric("Repeticiones internas", f"{np.mean(internal):.2f}")
    c.metric("Impares por sorteo", f"{np.mean(odd):.2f}")
    d.metric("Consecutivos", f"{np.mean(cons):.2f}")

    pair = {}
    for row in vals:
        for a1, b1 in itertools.combinations(sorted(set(row)), 2):
            pair[(a1, b1)] = pair.get((a1, b1), 0) + 1
    top = sorted(pair.items(), key=lambda z: z[1], reverse=True)[:50]
    st.dataframe(pd.DataFrame({
        "Pareja": [f"{a1:02d}-{b1:02d}" for (a1, b1), _ in top],
        "Veces": [v for _, v in top]
    }), use_container_width=True)

with t3:
    st.header("🧹 Resumen de Filtros de Descarte Aplicados")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("🔄 Rep. entre sorteos")
        rep_i = analyze_rep_inter(vals, n_inter)
        st.info(", ".join(f"{x:02d}" for x in sorted(rep_i)) if rep_i else "Ninguno")
    with col2:
        st.subheader("🔁 Rep. internas")
        rep_a = analyze_rep_intra(vals, n_intra)
        st.info(", ".join(f"{x:02d}" for x in sorted(rep_a)) if rep_a else "Ninguno")
    with col3:
        st.subheader("🔢 Consecutivos")
        c_set = analyze_consecutivos(vals, n_cons)
        st.info(", ".join(f"{x:02d}" for x in sorted(c_set)) if c_set else "Ninguno")

    st.divider()
    st.subheader(f"🚫 Total descartados ({len(nums_a_excluir)} de 100):")
    st.warning(", ".join(f"{x:02d}" for x in sorted(nums_a_excluir)) if nums_a_excluir else "Sin descartes activos.")

with t4:
    st.header("🧪 Backtesting")
    cases = st.slider("Cantidad de sorteos históricos a evaluar", 20, 300, 100)
    bt = backtest(vals, cases, exclude_nums=nums_a_excluir, weights=active_weights)
    if len(bt):
        avg = bt.Aciertos_Top20.mean()
        over = (bt.Aciertos_Top20 > 4).mean() * 100
        a, b, c = st.columns(3)
        a.metric("Promedio Top-20", f"{avg:.2f}")
        b.metric("Esperado aleatorio", "4.00")
        c.metric("Casos > 4 aciertos", f"{over:.1f}%")
        st.dataframe(bt, use_container_width=True, height=500)
        st.download_button("Descargar backtesting CSV", bt.to_csv(index=False).encode(), "backtesting.csv")

with t5:
    st.header("💡 Conclusión y Recomendación del Algoritmo")
    
    candidatos_validos = [n for n in score.index if n not in nums_a_excluir]
    top_5 = candidatos_validos[:5]
    top_10 = candidatos_validos[:10]
    
    st.markdown(f"""
    > **📌 Veredicto del Sistema para el Próximo Sorteo:**  
    > Basado en la ponderación estadística avanzada (descontando los **{len(nums_a_excluir)}** números excluidos), los números con mayor probabilidad técnica son:
    """)
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        st.metric(label="🎯 Números Clave (Top 5)", value=", ".join([f"{n:02d}" for n in top_5]))
    with col_v2:
        st.metric(label="📊 Bloque Recomendado (Top 10)", value=", ".join([f"{n:02d}" for n in top_10]))

    st.divider()

    st.header("🎟️ Generador Avanzado de Líneas")
    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        line_size = st.number_input("Tamaño de línea (Números por jugada)", min_value=5, max_value=20, value=20, step=1)
    with col_g2:
        strategy = st.selectbox("Estrategia de Generación", [
            "🤖 Conclusión / Selección del Algoritmo (Predicción Directa)",
            "⚖️ Mixta Equilibrada",
            "🔥 Números Calientes",
            "🧊 Fríos / Atrasados",
            "🎯 Zonas Activas",
            "🔗 Arrastres Recientes",
            "🔄 Repetición Sorteo Anterior"
        ])
    with col_g3:
        amount = st.slider("Cantidad de líneas", 5, 100, 20)

    seed = st.number_input("Semilla de aleatoriedad", value=20260911, step=1)

    lines = generate(score, freq, gaps, last, vals, amount, seed, line_size=line_size, strategy=strategy, exclude_nums=nums_a_excluir)
    if lines:
        cols = ["Línea"] + [f"N{i}" for i in range(1, line_size + 1)]
        out = pd.DataFrame(
            [[i + 1] + [f"{x:02d}" for x in line] for i, line in enumerate(lines)],
            columns=cols
        )
        st.dataframe(out, use_container_width=True, height=500)
        st.download_button("Descargar líneas CSV", out.to_csv(index=False).encode(), "lineas.csv")

with t6:
    st.header("🤖 Evaluación de Aciertos y Optimización Adaptativa")
    st.write("El sistema analiza la efectividad de cada factor en los sorteos pasados para recalibrar la importancia asignada a cada indicador estadístico.")

    if use_auto_weights:
        st.subheader("📊 Pesos Activos Calculados por Auto-Aprendizaje:")
        w_df = pd.DataFrame({
            "Indicador": ["Frecuencia Histórica", "Rendimiento Últimos 10", "Rendimiento Últimos 30", "Rendimiento Últimos 20", "Atrasos (Gaps)", "Presencia Último Sorteo"],
            "Peso Ponderado": [f"{v*100:.1f}%" for v in active_weights.values()]
        })
        st.table(w_df)
    else:
        st.info("Para activar la optimización automática, habilitá la opción 'Activar Auto-Optimización de Pesos' en el panel lateral.")
