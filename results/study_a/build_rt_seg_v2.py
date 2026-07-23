import json, os
import numpy as np, pandas as pd
from scipy import sparse
from scipy.sparse.linalg import spsolve
SRC="/root/.claude/projects/-home-user-macro-reaction-backtest/c950405a-5afc-5c3f-91ea-7afa2909e2de/tool-results/mcp-Supabase-execute_sql-1784783525989.txt"
res=json.loads(open(SRC).read())["result"]; arr=res[res.index("["):res.rindex("]")+1]
df=pd.DataFrame(json.loads(arr)); df["d"]=pd.to_datetime(df["d"])
df["real"]=pd.to_numeric(df["real"]); df["bei"]=pd.to_numeric(df["bei"])
df=df.sort_values("d").reset_index(drop=True)
LAM=5000; SLOPE_K=21; REBAL=5; START=pd.Timestamp("2018-06-01")
def cdir(y):
    y=np.asarray(y,float); n=len(y)
    if n<SLOPE_K+5: return None
    D=sparse.diags([1.,-2.,1.],[0,1,2],shape=(n-2,n)); I=sparse.identity(n)
    tr=spsolve((I+LAM*(D.T@D)).tocsc(),y)
    return "up" if tr[-1]-tr[-1-SLOPE_K]>0 else "down"
QUAD={(True,True):"RF",(False,True):"ST",(False,False):"RC",(True,False):"TG"}
rv=df["real"].values; bv=df["bei"].values; idx=df["d"]
lab=[None]*len(df); cur=None
for i in range(len(df)):
    if i%REBAL==0:
        rd=cdir(rv[:i+1]); bd=cdir(bv[:i+1])
        if rd and bd: cur=QUAD[(rd=="up",bd=="up")]
    lab[i]=cur
segs=[]; st=0
for i in range(1,len(lab)):
    if lab[i]!=lab[i-1]:
        if lab[i-1] is not None: segs.append((idx[st],idx[i-1],lab[i-1]))
        st=i
if lab[-1] is not None: segs.append((idx[st],idx.iloc[-1],lab[-1]))
seg=pd.DataFrame(segs,columns=["start","end","quadrant"]); seg=seg[seg["end"]>=START].reset_index(drop=True)
HERE=os.path.dirname(os.path.abspath(__file__)); seg.to_csv(os.path.join(HERE,"realtime_segments_v2.csv"),index=False)
vals=",".join(f"('{q}',DATE '{s.date()}',DATE '{e.date()}')" for s,e,q in zip(seg.start,seg.end,seg.quadrant))
open(os.path.join(HERE,"realtime_segments_v2_values.txt"),"w").write(vals)
print("segments:",len(seg),"| range",str(seg.start.min().date()),"~",str(seg.end.max().date()))
print(seg.quadrant.value_counts().to_string()); print("nchars:",len(vals))
