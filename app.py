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

def analyze_patterns(vals, n_sorteos):
    # Analizar solo los últimos n_sorteos
    sub_vals = vals[:min(len(vals), n_sorteos)]
    
    # Repetidos entre sorteos consecutivos
    rep_inter = set()
    for i in range(len(sub_vals) - 1):
        inter = set(sub_vals[i]) & set(sub_vals[i+1])
        rep_inter.update(inter)
        
    # Repeticiones internas (números repetidos dentro del mismo extracto)
    rep_intra = set()
    for row in sub_vals:
        counts = pd.Series(row).value_counts()
        rep_intra.update(counts[counts > 1].index)
        
    # Consecutivos
    consecutivos = set()
    for row in sub_vals:
        sorted_row = sorted(set(row))
        for a, b in zip(sorted_row, sorted_row[1:]):
            if b == a + 1:
                consecutivos.add(a)
                consecutivos.add(b)
                
    return rep_inter, rep_intra, consecutivos

def generate(score, amount, seed, exclude_nums=set()):
    rng = random.Random(int(seed))
    # Filtrar el ranking para remover los números excluidos
    filtered_score = score[~score.index.isin(exclude_nums)]
    top = list(filtered_score.index)
    
    if len(top) < 20:
        st.error("Se descartaron demasiados números. No quedan suficientes candidatos para armar combinaciones de 20 números.")
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
            
            # Completar hasta 20 si faltan por límites de tamaño
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

def backtest(vals, cases):
    rows = []
    for i in range(1, min(len(vals) - 1, cases) + 1):
        hist = vals[i + 1:]
        if len(hist) < 30: 
            break
        _, _, _, _, s = model(hist)
        top20 = list(s.index[:20])
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
t1, t2, t3, t4, t5 = st.tabs(["🏆 Ranking", "🔗 Patrones", "🧹 Filtros/Descarte", "🧪 Backtesting", "🎟️ Generador"])

with t1:
    r = pd.DataFrame({
        "Ranking": range(1, 101),
        "Número": [f"{x:02d}" for x in score.index],
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
    st.header("🧹 Descarte de Números por Patrones Recientes")
    n_sorteos = st.number_input("Cantidad de últimos sorteos a analizar", min_value=1, max_value=len(vals), value=15, step=1)
    
    rep_inter, rep_intra, consecutivos = analyze_patterns(vals, n_sorteos)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("🔄 Repetidos entre sorteos")
        st.write(f"Aparecieron en sorteos consecutivos en los últimos {n_sorteos} sorteos:")
        st.info(", ".join(f"{x:02d}" for x in sorted(rep_inter)) if rep_inter else "Ninguno")
        filt_inter = st.checkbox("Excluir estos números del Generador", value=False, key="f_inter")
        
    with col2:
        st.subheader("🔁 Repeticiones internas")
        st.write(f"Salió repetido dentro del mismo extracto en los últimos {n_sorteos} sorteos:")
        st.info(", ".join(f"{x:02d}" for x in sorted(rep_intra)) if rep_intra else "Ninguno")
        filt_intra = st.checkbox("Excluir estos números del Generador", value=False, key="f_intra")
        
    with col3:
        st.subheader("🔢 Consecutivos")
        st.write(f"Formaron parejas consecutivas en los últimos {n_sorteos} sorteos:")
        st.info(", ".join(f"{x:02d}" for x in sorted(consecutivos)) if consecutivos else "Ninguno")
        filt_cons = st.checkbox("Excluir estos números del Generador", value=False, key="f_cons")

    # Armar lista final de números excluidos
    nums_a_excluir = set()
    if filt_inter: nums_a_excluir.update(rep_inter)
    if filt_intra: nums_a_excluir.update(rep_intra)
    if filt_cons: nums_a_excluir.update(consecutivos)
    
    st.divider()
    st.subheader(f"🚫 Total de números descartados ({len(nums_a_excluir)} de 100):")
    st.warning(", ".join(f"{x:02d}" for x in sorted(nums_a_excluir)) if nums_a_excluir else "Sin números descartados.")

with t4:
    cases = st.slider("Cantidad de sorteos históricos a evaluar", 20, 300, 100)
    bt = backtest(vals, cases)
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
    amount = st.slider("Cantidad de líneas", 5, 100, 20)
    seed = st.number_input("Semilla", value=20260911, step=1)
    
    # Recuperar lista de exclusión si está activa
    nums_excluidos_gen = nums_a_excluir if 'nums_a_excluir' in locals() else set()
    if nums_excluidos_gen:
        st.info(f"ℹ️ Generando líneas excluyendo {len(nums_excluidos_gen)} números marcados en la pestaña 'Filtros/Descarte'.")
        
    lines = generate(score, amount, seed, exclude_nums=nums_excluidos_gen)
    if lines:
        out = pd.DataFrame(
            [[i + 1] + [f"{x:02d}" for x in line] for i, line in enumerate(lines)],
            columns=["Línea"] + [f"N{i}" for i in range(1, 21)]
        )
        st.dataframe(out, use_container_width=True, height=650)
        st.download_button("Descargar líneas CSV", out.to_csv(index=False).encode(), "lineas.csv")
