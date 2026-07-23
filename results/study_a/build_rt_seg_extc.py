import json, os
import numpy as np, pandas as pd
from scipy import sparse
from scipy.sparse.linalg import spsolve
SRC="/root/.claude/projects/-home-user-macro-reaction-backtest/c950405a-5afc-5c3f-91ea-7afa2909e2de/tool-results/mcp-Supabase-execute_sql-1784783525989.txt"
res=json.loads(open(SRC).read())["result"]; arr=res[res.index("["):res.rindex("]")+1]
df=pd.DataFrame(json.loads(arr)); df["d"]=pd.to_datetime(df["d"])
df["real"]=pd.to_numeric(df["real"]); df["bei"]=pd.to_numeric(df["bei"])
df=df.sort_values("d").reset_index(drop=True)
LAM=5000; MIN_DAYS_LEG=10; REBAL=5; START=pd.Timestamp("2018-06-01")
def whittaker_segs(y,lam,min_days):
    y=np.asarray(y,float); n=len(y)
    D=sparse.diags([1.,-2.,1.],[0,1,2],shape=(n-2,n)); I=sparse.identity(n)
    tr=spsolve((I+lam*(D.T@D)).tocsc(),y); sl=np.gradient(tr)
    arr=np.where(sl>1e-9,"up",np.where(sl<-1e-9,"down","flat"))
    def segs_of(a):
        s=[]; c=a[0]; st=0
        for i in range(1,len(a)):
            if a[i]!=c: s.append([st,i-1,c]); c=a[i]; st=i
        s.append([st,len(a)-1,c]); return s
    ch=True
    while ch:
        ch=False; s=segs_of(arr)
        for j,(a,b,k) in enumerate(s):
            if b-a+1<min_days and len(s)>1:
                ll=s[j-1][1]-s[j-1][0]+1 if j>0 else -1
                rl=s[j+1][1]-s[j+1][0]+1 if j<len(s)-1 else -1
                arr[a:b+1]=s[j-1][2] if ll>=rl else s[j+1][2]; ch=True; break
    segs=[]; cur=arr[0]; si=0
    for i in range(1,len(arr)):
        if arr[i]!=cur: segs.append([si,i-1,cur]); cur=arr[i]; si=i
    segs.append([si,len(arr)-1,cur]); return segs
def snap(segs,Mv):
    S=[list(s) for s in segs]
    for k in range(len(S)):
        a,b,kind=S[k]
        if kind=="up": S[k].append(a+int(np.argmax(Mv[a:b+1])))
        elif kind=="down": S[k].append(a+int(np.argmin(Mv[a:b+1])))
        else: S[k].append(None)
    out=[]
    for i in range(len(S)):
        a,b,kind,ext=S[i]
        if kind in("up","down") and ext is not None:
            out.append((a,ext,kind))
            if i+1<len(S):
                S[i+1][0]=ext+1
                if S[i+1][0]>S[i+1][1]: S[i+1][1]=S[i+1][0]
        else: out.append((a,b,kind))
    out=[(a,b,k) for a,b,k in out if a<=b]
    merged=[list(out[0])]
    for a,b,k in out[1:]:
        if k==merged[-1][2] and a==merged[-1][1]+1: merged[-1][1]=b
        else: merged.append([a,b,k])
    return [tuple(x) for x in merged]
def seg_dir(v):
    return snap(whittaker_segs(v,LAM,MIN_DAYS_LEG), np.asarray(v,float))[-1][2]
QUAD={(True,True):"RF",(False,True):"ST",(False,False):"RC",(True,False):"TG"}
rv=df["real"].values; bv=df["bei"].values; idx=df["d"]; lab=[None]*len(df); cur=None
for i in range(len(df)):
    if i%REBAL==0 and i>40:
        rd=seg_dir(rv[:i+1]); bd=seg_dir(bv[:i+1])
        if rd in("up","down") and bd in("up","down"): cur=QUAD[(rd=="up",bd=="up")]
    lab[i]=cur
segs=[]; st=0
for i in range(1,len(lab)):
    if lab[i]!=lab[i-1]:
        if lab[i-1] is not None: segs.append((idx[st],idx[i-1],lab[i-1]))
        st=i
if lab[-1] is not None: segs.append((idx[st],idx.iloc[-1],lab[-1]))
seg=pd.DataFrame(segs,columns=["start","end","quadrant"]); seg=seg[seg["end"]>=START].reset_index(drop=True)
HERE=os.path.dirname(os.path.abspath(__file__)); seg.to_csv(os.path.join(HERE,"rt_seg_extc.csv"),index=False)
vals=",".join(f"('{q}',DATE '{s.date()}',DATE '{e.date()}')" for s,e,q in zip(seg.start,seg.end,seg.quadrant))
open(os.path.join(HERE,"rt_seg_extc_values.txt"),"w").write(vals)
print("segments:",len(seg),"| range",str(seg.start.min().date()),"~",str(seg.end.max().date()))
print(seg.quadrant.value_counts().to_string()); print("nchars:",len(vals))
