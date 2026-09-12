import streamlit as st
import pandas as pd
import numpy as np
import itertools, random, os

st.set_page_config(page_title="Quiniela Chaqueña Pro", layout="wide")
st.title("🎯 Quiniela Chaqueña Pro")
st.caption("Análisis estadístico, backtesting y generación de líneas. No representa una predicción garantizada.")

uploaded = st.file_uploader("Cargá el Excel de sorteos", type=["xlsx", "xls"])

def prepare(df):
    cols = [f"{i}°" for i in range(1, 21)]
    if not all(c in df.columns for c in cols):
        raise ValueError("El Excel debe contener las columnas 1° a 20°.")
    X = df[cols].apply(pd.to_numeric, errors="coerce").dropna(how="all")
    return X.astype(int).values

def model(vals):
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
    score = 100 * (.30 * pct(freq) + .25 * pct(rc[10]) + .15 * pct(rc[30]) + .10 * pct(rc[20]) +
                   .15 * pct(pd.Series({x: 1 / (gaps[x] + 1) for x in nums})) +
                   .05 * pct(pd.Series({x: int(x in last) for x in nums})))
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

def generate(score, amount, seed, exclude_nums=set()):
    rng = random.Random(int(seed))
    filtered_score = score[~score.index.isin(exclude_nums)]
    top = list(filtered_score.index)
    
    if len(top) < 20:
        st.error(f"Se descartaron demasiado números ({len(exclude_nums)} números excluidos). Quedan {len(top)} candidatos, pero se necesitan al menos 20 para armar las líneas.")
        return []

    lines = []
    p1 = max(1, int(len(top) * 0.35))
    p2 = max(1, int(len(top) * 0.70))
    
    for _ in range(amount):
        for _try in range(10000):
            s1 = min(12, len(top[:p1]))
            s2 = min(5, len(top[p1:p2]))
            s3 = min(3, len(top[p2:]))
            
            comb = set(rng.sample(top[:p1], s1) + rng.sample(top[p1:p2], s2) + rng.sample(top[p2:], s3))
            
            if len(comb) < 20:
                rem = list(set(top) - comb)
                comb.update(rng.sample(rem, 20 - len(comb)))

            if len(comb) != 20: 
                continue
            odd = sum(x % 2 for x in comb)
            dc = pd.Series([x // 10 for x in comb]).value_counts()
            if 8 <= odd <= 12 and dc.max() <= 4 and len(dc) >= 7 and not any(len(comb & set(o)) > 15 for o in lines):
                lines.append(sorted(comb))
                break
    return lines

def backtest(vals, cases, exclude_nums=set()):
    rows = []
    for i in range(1, min(len(vals) - 1, cases) + 1):
        hist = vals[i + 1:]
        if len(hist) < 30: 
            break
        _, _, _, _, s = model(hist)
        
        # Filtrar score eliminando los números descartados
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

if uploaded:
    df = pd.read_excel(uploaded)
else:
    default = "/mnt/data/Extracto_Loteria_Chaquena_Ultimas_2_Cifras_para análisis.xlsx"
    if os.path.exists(default): 
        df = pd.read_excel(default)
    else: 
        st.stop()

try: 
    vals = prepare(df)
except Exception as e: 
    st.error(str(e))
    st.stop()

freq, rc, gaps, last, score = model(vals)

# --- CONFIGURACIÓN DE FILTROS Y DESCARTE EN SIDEBAR O ANTES DE TABS ---
st.sidebar.header("🧹 Filtros de Descarte Global")

n_inter = st.sidebar.number_input("Sorteos (Rep. entre sorteos)", 2, len(vals), 15, key="n_inter")
f_inter = st.sidebar.checkbox("Excluir rep. entre sorteos", value=False, key="f_inter")

n_intra = st.sidebar.number_input("Sorteos (Rep. internas)", 1, len(vals), 10, key="n_intra")
f_intra = st.sidebar.checkbox("Excluir rep. internas", value=False, key="f_intra")

n_cons = st.sidebar.number_input("Sorteos (Consecutivos)", 1, len(vals), 15, key="n_cons")
f_cons = st.sidebar.checkbox("Excluir consecutivos", value=False, key="f_cons")

f_ult1 = st.sidebar.checkbox("Excluir ÚLTIMO sorteo", value=False, key="f_ult1")
f_ult2 = st.sidebar.checkbox("Excluir PENÚLTIMO sorteo", value=False, key="f_ult2")

# Calcular conjunto de descartes
nums_a_excluir = set()
if f_inter: nums_a_excluir.update(analyze_rep_inter(vals, n_inter))
if f_intra: nums_a_excluir.update(analyze_rep_intra(vals, n_intra))
if f_cons: nums_a_excluir.update(analyze_consecutivos(vals, n_cons))
if f_ult1: nums_a_excluir.update(vals[0])
if f_ult2 and len(vals) > 1: nums_a_excluir.update(vals[1])

if nums_a_excluir:
    st.sidebar.warning(f"🚫 {len(nums_a_excluir)} números excluidos de los 100.")

t1, t2, t3, t4, t5 = st.tabs(["🏆 Ranking", "🔗 Patrones", "🧹 Filtros/Descarte", "🧪 Backtesting", "🎟️ Generador"])

with t1:
    r = pd.DataFrame({
        "Ranking": range(1, 101),
        "Número": [f"{x:02d}" for x in score.index],
        "Excluido": ["SI" if x in nums_a_excluir else "NO" for x in score.index],
        "Índice": [round(score[x], 2) for x in score.index],
        "Histórico": [int(freq[x]) for x in score.index],
        "Últ.5": [int(rc[5][x]) for x in score.index],
        "Últ.10": [int(rc[10][x]) for x in score.index],
        "Últ.20": [int(rc[20][x]) for x in score.index],
        "Últ.30": [int(rc[30][x]) for x in score.index],
        "Atraso": [gaps[x] for x in score.index],
        "Último": ["SI" if x in last else "NO" for x in score.index]
    })
    st.dataframe(r, use_container_width=True, height=650)
    st.download_button("Descargar ranking CSV", r.to_csv(index=False).encode(), "ranking.csv")

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
    st.write("Los controles de descarte se encuentran activos en la **barra lateral (Sidebar)** a la izquierda para aplicarse globalmente a todas las pestañas.")
    
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
    if nums_a_excluir:
        st.info(f"ℹ️ Evaluando rendimiento excluyendo {len(nums_a_excluir)} números marcados en los filtros.")
    
    cases = st.slider("Cantidad de sorteos históricos a evaluar", 20, 300, 100)
    bt = backtest(vals, cases, exclude_nums=nums_a_excluir)
    if len(bt):
        avg = bt.Aciertos_Top20.mean()
        over = (bt.Aciertos_Top20 > 4).mean() * 100
        a, b, c = st.columns(3)
        a.metric("Promedio Top-20", f"{avg:.2f}")
        b.metric("Esperado aleatorio", "4.00")
        c.metric("Casos > 4 aciertos", f"{over:.1f}%")
        st.dataframe(bt, use_container_width=True, height=500)
        st.download_button("Descargar backtesting CSV", bt.to_csv(index=False).encode(), "backtesting.csv")
    else: 
        st.warning("No hay suficientes sorteos.")

with t5:
    st.header("🎟️ Generador de Líneas")
    amount = st.slider("Cantidad de líneas", 5, 100, 20)
    seed = st.number_input("Semilla", value=20260911, step=1)
    
    if nums_a_excluir:
        st.info(f"ℹ️ Generando líneas excluyendo {len(nums_a_excluir)} números descartados.")
        
    lines = generate(score, amount, seed, exclude_nums=nums_a_excluir)
    if lines:
        out = pd.DataFrame(
            [[i + 1] + [f"{x:02d}" for x in line] for i, line in enumerate(lines)],
            columns=["Línea"] + [f"N{i}" for i in range(1, 21)]
        )
        st.dataframe(out, use_container_width=True, height=650)
        st.download_button("Descargar líneas CSV", out.to_csv(index=False).encode(), "lineas.csv")
