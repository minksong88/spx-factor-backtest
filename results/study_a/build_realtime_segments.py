import json, os
import numpy as np, pandas as pd
from scipy import sparse
from scipy.sparse.linalg import spsolve
SRC="/root/.claude/projects/-home-user-macro-reaction-backtest/c950405a-5afc-5c3f-91ea-7afa2909e2de/tool-results/mcp-Supabase-execute_sql-1784782608465.txt"
res=json.loads(open(SRC).read())["result"]; arr=res[res.index("["):res.rindex("]")+1]
df=pd.DataFrame(json.loads(arr)); df["d"]=pd.to_datetime(df["d"])
df["real"]=pd.to_numeric(df["real"]); df["nominal"]=pd.to_numeric(df["nominal"])
df=df.sort_values("d").reset_index(drop=True)
df["bei"]=df["nominal"]-df["real"]
LAM=5000; SLOPE_K=21; REBAL=5; START=pd.Timestamp("2018-06-01")
def causal_dir(y):
    y=np.asarray(y,float); n=len(y)
    if n<SLOPE_K+5: return None
    D=sparse.diags([1.,-2.,1.],[0,1,2],shape=(n-2,n)); I=sparse.identity(n)
    tr=spsolve((I+LAM*(D.T@D)).tocsc(),y)
    return "up" if tr[-1]-tr[-1-SLOPE_K]>0 else "down"
# quadrant map: (real_up, bei_up)
QUAD={(True,True):"RF",(False,True):"ST",(False,False):"RC",(True,False):"TG"}
rv=df["real"].values; bv=df["bei"].values; idx=df["d"]
lab=[None]*len(df); cur=None
for i in range(len(df)):
    if i%REBAL==0:
        rd=causal_dir(rv[:i+1]); bd=causal_dir(bv[:i+1])
        if rd and bd: cur=QUAD[(rd=="up", bd=="up")]
    lab[i]=cur
s=pd.Series(lab,index=idx)
# 압축: 라벨 바뀔 때마다 segment
segs=[]; st=0
for i in range(1,len(s)):
    if lab[i]!=lab[i-1]:
        if lab[i-1] is not None: segs.append((idx[st], idx[i-1], lab[i-1]))
        st=i
if lab[-1] is not None: segs.append((idx[st], idx.iloc[-1], lab[-1]))
seg=pd.DataFrame(segs,columns=["start","end","quadrant"])
seg=seg[seg["end"]>=START].reset_index(drop=True)
HERE=os.path.dirname(os.path.abspath(__file__))
seg.to_csv(os.path.join(HERE,"realtime_segments.csv"),index=False)
print("segments:",len(seg),"| range",seg.start.min().date(),"~",seg.end.max().date())
print("quadrant counts:\n", seg.quadrant.value_counts().to_string())
# SQL VALUES 출력
vals=",".join(f"('{q}',DATE '{st.date()}',DATE '{en.date()}')" for st,en,q in zip(seg.start,seg.end,seg.quadrant))
open(os.path.join(HERE,"realtime_segments_values.txt"),"w").write(vals)
print("nchars VALUES:",len(vals))
