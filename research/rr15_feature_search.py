"""Search explainable entry filters for structural RR 1.5-2.0 trades."""
from __future__ import annotations
import itertools,pickle,sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.swing_strategy_research import CACHE,indicators

OUT=Path('research/results/rr15_search')

def outcome(d,i,stop,target,max_hold=30,cost_bps=10):
 e=i+1
 if e>=len(d):return None
 entry=float(d.Open.iloc[e]);risk=entry-stop;rr=(target-entry)/risk if risk>0 else -1
 if not 1.5<=rr<=2.0:return None
 j=e;status='time'
 for j in range(e,min(e+max_hold,len(d))):
  o,h,l=map(float,(d.Open.iloc[j],d.High.iloc[j],d.Low.iloc[j]))
  if o<=stop:px=o;status='gap_stop';break
  if l<=stop:px=stop;status='stop';break
  if o>=target:px=o;status='target';break
  if h>=target:px=target;status='target';break
 else:px=float(d.Close.iloc[j])
 r=(px-entry)/risk-2*cost_bps/10000*entry/risk
 return dict(entry_date=d.index[e],exit_date=d.index[j],r=r,planned_rr=rr,status=status)

def build():
 base=pd.read_csv('research/results/logic5_validation/trades.csv',parse_dates=['signal_date'])
 with CACHE.open('rb') as f:raw=pickle.load(f)
 data={t:indicators(d[['Open','High','Low','Close','Volume']]) for t,d in raw.items()}
 closes=pd.concat({t:d.Close for t,d in data.items()},axis=1)
 rs63=(closes/closes.shift(63)-1).rank(axis=1,pct=True)
 flags=[]
 for t in ('SPY','QQQ'):
  d=data[t];flags.append(((d.Close>d.ema200)&(d.ema50>d.ema200)).rename(t))
 regime=pd.concat(flags,axis=1).all(axis=1)
 rows=[]
 for z in base.itertuples():
  if z.ticker not in data or not bool(regime.get(z.signal_date,False)):continue
  d=data[z.ticker]
  try:i=d.index.get_loc(z.signal_date)
  except KeyError:continue
  if i<201:continue
  stop=z.entry-z.risk;target=float(d.High.iloc[i-60:i].max())*.995
  out=outcome(d,i,stop,target)
  if not out:continue
  o,h,l,c=map(float,(d.Open.iloc[i],d.High.iloc[i],d.Low.iloc[i],d.Close.iloc[i]));rng=max(h-l,1e-9)
  spy=data['SPY'].reindex(d.index);qqq=data['QQQ'].reindex(d.index)
  row=dict(ticker=z.ticker,signal_date=z.signal_date,pa=z.pa,osc=z.osc,
   rsi14=float(d.rsi.iloc[i]),mom21=float(c/d.Close.iloc[i-21]-1),mom63=float(c/d.Close.iloc[i-63]-1),mom126=float(c/d.Close.iloc[i-126]-1),
   rs63=float(rs63.at[z.signal_date,z.ticker]),atr_pct=float(d.atr.iloc[i]/c),ema20_dist=float(c/d.ema20.iloc[i]-1),ema50_dist=float(c/d.ema50.iloc[i]-1),
   vol_ratio=float(d.Volume.iloc[i]/d.Volume.iloc[i-20:i].mean()),body_pct=(c-o)/rng,lower_wick=(min(o,c)-l)/rng,close_location=(c-l)/rng,
   spy_strength=float(spy.Close.iloc[i]/spy.ema200.iloc[i]-1),qqq_strength=float(qqq.Close.iloc[i]/qqq.ema200.iloc[i]-1),stop_pct=float((z.risk)/z.entry),
   **out)
  rows.append(row)
 return pd.DataFrame(rows)

def metrics(x):
 if len(x)==0:return dict(n=0,win=0,avg=-9,pf=0,payoff=0)
 r=x.r;loss=-r[r<0].sum();aw=r[r>0].mean();al=-r[r<0].mean()
 return dict(n=len(x),win=float((r>0).mean()),avg=float(r.mean()),pf=float(r[r>0].sum()/loss) if loss else 99,payoff=float(aw/al) if al else 99)

def main():
 OUT.mkdir(parents=True,exist_ok=True);x=build();x.to_csv(OUT/'dataset.csv',index=False)
 train=x[x.entry_date<'2025-01-01'];valid=x[(x.entry_date>='2025-01-01')&(x.entry_date<'2026-01-01')];hold=x[x.entry_date>='2026-01-01']
 features=['rsi14','mom21','mom63','mom126','rs63','atr_pct','ema20_dist','ema50_dist','vol_ratio','body_pct','lower_wick','close_location','spy_strength','qqq_strength','stop_pct','pa','osc']
 conds=[]
 for f in features:
  for q in (.2,.4,.6,.8):
   v=float(train[f].quantile(q));conds.extend([(f,'>=',v),(f,'<=',v)])
 def mask(df,c):
  f,op,v=c;return df[f]>=v if op=='>=' else df[f]<=v
 candidates=[]
 for nconds in (1,2):
  combos=((c,) for c in conds) if nconds==1 else itertools.combinations(conds,2)
  for cs in combos:
   if len(cs)==2 and cs[0][0]==cs[1][0]:continue
   mt=np.ones(len(train),bool)
   for c in cs:mt&=mask(train,c).to_numpy()
   a=train[mt];m=metrics(a)
   if m['n']<60 or m['avg']<=0 or m['win']<.42:continue
   candidates.append((min(m['win'],.7)+m['avg']*.1,cs,m))
 candidates=sorted(candidates,key=lambda z:z[0],reverse=True)[:300]
 rows=[]
 for _,cs,tm in candidates:
  def select(df):
   m=np.ones(len(df),bool)
   for c in cs:m&=mask(df,c).to_numpy()
   return df[m]
  vm=metrics(select(valid));hm=metrics(select(hold))
  rows.append(dict(rule=' AND '.join(f'{f}{op}{v:.6g}' for f,op,v in cs),**{f'train_{k}':v for k,v in tm.items()},**{f'valid_{k}':v for k,v in vm.items()},**{f'hold_{k}':v for k,v in hm.items()}))
 s=pd.DataFrame(rows);s['selection_score']=np.minimum(s.train_win,s.valid_win)+np.minimum(s.train_avg,s.valid_avg)*.1;s=s.sort_values('selection_score',ascending=False);s.to_csv(OUT/'rules.csv',index=False)
 print('base',metrics(train),metrics(valid),metrics(hold));print(s.head(30).to_string(index=False))

if __name__=='__main__':main()
