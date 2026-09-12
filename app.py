
import streamlit as st
import pandas as pd
import numpy as np
import itertools, random, os

st.set_page_config(page_title="Quiniela Chaqueña Pro", layout="wide")
st.title("🎯 Quiniela Chaqueña Pro")
st.caption("Análisis estadístico, backtesting y generación de líneas. No representa una predicción garantizada.")

uploaded=st.file_uploader("Cargá el Excel de sorteos",type=["xlsx","xls"])

def prepare(df):
    cols=[f"{i}°" for i in range(1,21)]
    if not all(c in df.columns for c in cols):
        raise ValueError("El Excel debe contener las columnas 1° a 20°.")
    X=df[cols].apply(pd.to_numeric,errors="coerce").dropna(how="all")
    return X.astype(int).values

def model(vals):
    n=len(vals); nums=range(100)
    freq=pd.Series(vals.ravel()).value_counts().reindex(nums,fill_value=0)
    rc={w:pd.Series(vals[:min(w,n)].ravel()).value_counts().reindex(nums,fill_value=0) for w in [5,10,20,30]}
    gaps={}
    for x in nums:
        rows=np.where((vals==x).any(axis=1))[0]
        gaps[x]=int(rows[0]) if len(rows) else n
    last=set(vals[0])
    pct=lambda s:s.rank(pct=True,method="average")
    score=100*(.30*pct(freq)+.25*pct(rc[10])+.15*pct(rc[30])+.10*pct(rc[20])+
               .15*pct(pd.Series({x:1/(gaps[x]+1) for x in nums}))+
               .05*pct(pd.Series({x:int(x in last) for x in nums})))
    return freq,rc,gaps,last,score.sort_values(ascending=False)

def generate(score,amount,seed):
    rng=random.Random(int(seed)); top=list(score.index); lines=[]
    for _ in range(amount):
        for _try in range(10000):
            comb=set(rng.sample(top[:35],12)+rng.sample(top[35:70],5)+rng.sample(top[70:],3))
            if len(comb)!=20: continue
            odd=sum(x%2 for x in comb)
            dc=pd.Series([x//10 for x in comb]).value_counts()
            if 8<=odd<=12 and dc.max()<=4 and len(dc)>=7 and not any(len(comb&set(o))>15 for o in lines):
                lines.append(sorted(comb)); break
    return lines

def backtest(vals, cases):
    rows=[]
    # Data are newest-first. For target row i, only rows i+1 onward are allowed.
    for i in range(1,min(len(vals)-1,cases)+1):
        hist=vals[i+1:]
        if len(hist)<30: break
        _,_,_,_,s=model(hist)
        hits=len(set(s.index[:20]) & set(vals[i]))
        rows.append({"Indice_sorteo":i,"Aciertos_Top20":hits,"Esperado_azar":4.0})
    return pd.DataFrame(rows)

if uploaded:
    df=pd.read_excel(uploaded)
else:
    default="/mnt/data/Extracto_Loteria_Chaquena_Ultimas_2_Cifras_para análisis.xlsx"
    if os.path.exists(default): df=pd.read_excel(default)
    else: st.stop()

try: vals=prepare(df)
except Exception as e: st.error(str(e)); st.stop()

freq,rc,gaps,last,score=model(vals)
t1,t2,t3,t4=st.tabs(["🏆 Ranking","🔗 Patrones","🧪 Backtesting","🎟️ Generador"])

with t1:
    r=pd.DataFrame({"Ranking":range(1,101),"Número":[f"{x:02d}" for x in score.index],
      "Índice":[round(score[x],2) for x in score.index],
      "Histórico":[int(freq[x]) for x in score.index],
      "Últ.5":[int(rc[5][x]) for x in score.index],
      "Últ.10":[int(rc[10][x]) for x in score.index],
      "Últ.20":[int(rc[20][x]) for x in score.index],
      "Últ.30":[int(rc[30][x]) for x in score.index],
      "Atraso":[gaps[x] for x in score.index],
      "Último":["SI" if x in last else "NO" for x in score.index]})
    st.dataframe(r,use_container_width=True,height=650)
    st.download_button("Descargar ranking CSV",r.to_csv(index=False).encode(),"ranking.csv")

with t2:
    rep=[len(set(vals[i])&set(vals[i+1])) for i in range(len(vals)-1)]
    internal=[20-len(set(x)) for x in vals]
    odd=[sum(x%2 for x in row) for row in vals]
    cons=[sum(1 for a,b in zip(sorted(set(row)),sorted(set(row))[1:]) if b==a+1) for row in vals]
    a,b,c,d=st.columns(4)
    a.metric("Repetidos entre sorteos",f"{np.mean(rep):.2f}")
    b.metric("Repeticiones internas",f"{np.mean(internal):.2f}")
    c.metric("Impares por sorteo",f"{np.mean(odd):.2f}")
    d.metric("Consecutivos",f"{np.mean(cons):.2f}")
    pair={}
    for row in vals:
        for a1,b1 in itertools.combinations(sorted(set(row)),2):
            pair[(a1,b1)]=pair.get((a1,b1),0)+1
    top=sorted(pair.items(),key=lambda z:z[1],reverse=True)[:50]
    st.dataframe(pd.DataFrame({"Pareja":[f"{a1:02d}-{b1:02d}" for (a1,b1),_ in top],
                               "Veces":[v for _,v in top]}),use_container_width=True)

with t3:
    cases=st.slider("Cantidad de sorteos históricos a evaluar",20,300,100)
    bt=backtest(vals,cases)
    if len(bt):
        avg=bt.Aciertos_Top20.mean()
        over=(bt.Aciertos_Top20>4).mean()*100
        a,b,c=st.columns(3)
        a.metric("Promedio Top-20",f"{avg:.2f}")
        b.metric("Esperado aleatorio","4.00")
        c.metric("Casos > 4 aciertos",f"{over:.1f}%")
        st.dataframe(bt,use_container_width=True,height=500)
        st.download_button("Descargar backtesting CSV",bt.to_csv(index=False).encode(),"backtesting.csv")
    else: st.warning("No hay suficientes sorteos.")

with t4:
    amount=st.slider("Cantidad de líneas",5,100,20)
    seed=st.number_input("Semilla",value=20260911,step=1)
    lines=generate(score,amount,seed)
    out=pd.DataFrame([[i+1]+[f"{x:02d}" for x in line] for i,line in enumerate(lines)],
                     columns=["Línea"]+[f"N{i}" for i in range(1,21)])
    st.dataframe(out,use_container_width=True,height=650)
    st.download_button("Descargar líneas CSV",out.to_csv(index=False).encode(),"lineas.csv")
