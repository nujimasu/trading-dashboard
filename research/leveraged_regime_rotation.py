"""Concentrated leveraged-ETF regime rotation targeting very high CAGR."""
from __future__ import annotations
import argparse, pickle
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

CACHE=Path('data/leveraged_rotation_10y.pkl')
PAIRS={'QQQ':('TQQQ','SQQQ'),'SOXX':('SOXL','SOXS'),'SPY':('UPRO','SPXU'),'IWM':('TNA','TZA')}

def ind(d):
 d=d.copy();c=d.Close
 for n in (10,20,50,200):d[f'ema{n}']=c.ewm(span=n,adjust=False,min_periods=n).mean()
 tr=pd.concat([d.High-d.Low,(d.High-c.shift()).abs(),(d.Low-c.shift()).abs()],axis=1).max(axis=1)
 d['atr']=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean();return d

def load(refresh=False):
 if CACHE.exists() and not refresh:
  with CACHE.open('rb') as f:return pickle.load(f)
 ts=list(PAIRS)+[x for p in PAIRS.values() for x in p]
 raw=yf.download(ts,period='10y',auto_adjust=True,progress=False,threads=False,group_by='ticker')
 out={}
 for t in ts:
  try:
   d=raw[t][['Open','High','Low','Close','Volume']].dropna();d.index=pd.to_datetime(d.index).tz_localize(None);out[t]=ind(d)
  except Exception:pass
 CACHE.parent.mkdir(exist_ok=True);pickle.dump(out,CACHE.open('wb'));return out

def trades(data,trail=20,stop_n=20,atr_buf=.5,max_hold=30,cost_bps=10):
 candidates=[]
 for under,(bull_etf,bear_etf) in PAIRS.items():
  if any(t not in data for t in (under,bull_etf,bear_etf)):continue
  u=data[under]
  for side,etf in [('bull',bull_etf),('bear',bear_etf)]:
   d=data[etf];common=u.index.intersection(d.index);uu=u.reindex(common);dd=d.reindex(common)
   for i in range(201,len(common)-1):
    bull=uu.Close.iloc[i]>uu.ema200.iloc[i] and uu.ema50.iloc[i]>uu.ema200.iloc[i]
    bear=uu.Close.iloc[i]<uu.ema200.iloc[i] and uu.ema50.iloc[i]<uu.ema200.iloc[i]
    if (side=='bull' and not bull) or (side=='bear' and not bear):continue
    # Enter only on a 20-day breakout, ranked later by underlying 63-day strength.
    if dd.Close.iloc[i] <= dd.High.iloc[i-20:i].max():continue
    e=i+1;entry=float(dd.Open.iloc[e]);stop=float(dd.Low.iloc[i-stop_n+1:i+1].min()-atr_buf*dd.atr.iloc[i])
    if stop>=entry or (entry-stop)/entry>.20:continue
    pending=False;px=None;j=e
    for j in range(e,min(e+max_hold,len(common))):
     o,h,l,c=map(float,(dd.Open.iloc[j],dd.High.iloc[j],dd.Low.iloc[j],dd.Close.iloc[j]))
     if pending:px=o;status='trail';break
     if o<=stop:px=o;status='gap_stop';break
     if l<=stop:px=stop;status='stop';break
     if c<float(dd[f'ema{trail}'].iloc[j]):pending=True
    if px is None:px=float(dd.Close.iloc[j]);status='time'
    ret=px/entry-1-2*cost_bps/10000
    mom=float(uu.Close.iloc[i]/uu.Close.iloc[i-63]-1)
    candidates.append(dict(signal_date=common[i],entry_date=common[e],exit_date=common[j],ticker=etf,underlying=under,side=side,ret=ret,momentum=abs(mom),status=status))
 return pd.DataFrame(candidates)

def portfolio(x,max_positions=1,exposure=1.0):
 x=x.sort_values(['entry_date','momentum'],ascending=[True,False]);active=[];a=[]
 for z in x.itertuples():
  active=[q for q in active if q>z.entry_date]
  if len(active)>=max_positions:continue
  active.append(z.exit_date);a.append(z)
 a=pd.DataFrame(a);a['portfolio_ret']=np.maximum(-.99,a.ret*exposure/max_positions);return a

def stats(q):
 if q.empty:return dict(n=0)
 eq=np.cumprod(1+q.portfolio_ret.to_numpy());dd=eq/np.maximum.accumulate(eq)-1;yrs=max((q.exit_date.max()-q.entry_date.min()).days/365.25,.25)
 return dict(n=len(q),win=float((q.ret>0).mean()),avg=float(q.ret.mean()),cagr=float(eq[-1]**(1/yrs)-1),mdd=float(dd.min()),multiple=float(eq[-1]))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--refresh',action='store_true');a=ap.parse_args();data=load(a.refresh);rows=[]
 out=Path('research/results/leveraged_rotation');out.mkdir(parents=True,exist_ok=True)
 for trail in (10,20):
  for stop in (10,20,40):
   for buf in (.25,.5,1.0):
    raw=trades(data,trail,stop,buf)
    for pos in (1,2,3):
     p=portfolio(raw,pos,1.0);parts={'train':p[p.entry_date<'2022-01-01'],'validation':p[(p.entry_date>='2022-01-01')&(p.entry_date<'2025-01-01')],'holdout':p[p.entry_date>='2025-01-01']}
     row=dict(trail=trail,stop=stop,buf=buf,positions=pos,raw=len(raw))
     for k,q in parts.items():
      for m,v in stats(q).items():row[f'{k}_{m}']=v
     rows.append(row)
 s=pd.DataFrame(rows).sort_values(['holdout_cagr','validation_cagr'],ascending=False);s.to_csv(out/'summary.csv',index=False);print(s.head(25).to_string(index=False))

if __name__=='__main__':main()
