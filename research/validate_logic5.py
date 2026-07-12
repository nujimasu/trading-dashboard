"""Independent replay of the production logic5 signal and exit rules."""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.logic4_scan import _ema, _sma, _atr, _rsi
from pipeline.logic5_scan import _stoch, _macd_hist, _price_action, _oscillators
from research.swing_strategy_research import CACHE


def evaluate(d, i, stop, tp1, target, max_hold=30, cost_bps=10):
    e = i + 1
    if e >= len(d): return None
    entry = float(d.Open.iloc[e]); risk = entry - stop
    if risk <= 0 or risk / entry > .25: return None
    hit1 = False; current_stop = stop; j = e
    for j in range(e, min(e + max_hold, len(d))):
        o,h,l = map(float,(d.Open.iloc[j],d.High.iloc[j],d.Low.iloc[j]))
        if o <= current_stop:
            px=o; status='gap_stop'; break
        if l <= current_stop:
            px=current_stop; status='be' if hit1 else 'stop'; break
        if o >= target or h >= target:
            px=o if o>=target else target; status='target'; break
        if not hit1 and (o >= tp1 or h >= tp1):
            hit1=True; current_stop=entry
    else:
        px=float(d.Close.iloc[j]); status='time'
    tp1_r=(tp1-entry)/risk
    exit_r=(px-entry)/risk
    if status=='target': r=(.5*tp1_r+.5*exit_r) if hit1 else exit_r
    elif hit1: r=.5*tp1_r+.5*exit_r
    else: r=exit_r
    r -= 2*cost_bps/10000*entry/risk
    return dict(entry_date=d.index[e],exit_date=d.index[j],entry=entry,exit=px,risk=risk,
                r=r,status=status,days=j-e+1)


def main():
    with CACHE.open('rb') as f: data=pickle.load(f)
    trades=[]
    for n,(ticker,d) in enumerate(data.items(),1):
        if ticker in ('SPY','QQQ'): continue
        O=d.Open.to_list();H=d.High.to_list();L=d.Low.to_list();C=d.Close.to_list();V=d.Volume.to_list()
        if len(C)<250: continue
        e20,e50,e200=_ema(C,20),_ema(C,50),_ema(C,200)
        atr=_atr(H,L,C);rsi=_rsi(C);k,sd=_stoch(H,L,C);hist=_macd_hist(C);v20=_sma(V,20)
        next_free=201
        for i in range(201,len(C)-1):
            if i<next_free or None in (e20[i],e50[i],e200[i],atr[i],v20[i]): continue
            if not(C[i]>e200[i] and e50[i]>e200[i]):continue
            if C[i]<=C[i-63] or v20[i]<1_000_000:continue
            if min(abs(C[i]/e20[i]-1),abs(C[i]/e50[i]-1))>.05:continue
            pa,pan=_price_action(O,H,L,C,i);osc,oscn=_oscillators(rsi,k,sd,hist,i)
            if pan<4 or oscn<1:continue
            sl=min(L[i-19:i+1])-.1*atr[i]; plan_entry=C[i];R=plan_entry-sl
            if R<=0:continue
            tr=evaluate(d,i,sl,plan_entry+R,plan_entry+4*R)
            if tr:
                tr.update(ticker=ticker,signal_date=d.index[i],pa=pan,osc=oscn)
                trades.append(tr);next_free=i+tr['days']+1
        if n%100==0:print(n,len(trades))
    x=pd.DataFrame(trades);out=Path('research/results/logic5_validation');out.mkdir(parents=True,exist_ok=True)
    x.to_csv(out/'trades.csv',index=False)
    rows=[]
    for split in ('2024-01-01','2025-01-01'):
      for label,q in [('IS',x[x.entry_date<pd.Timestamp(split)]),('OOS',x[x.entry_date>=pd.Timestamp(split)])]:
        r=q.r;eq=r.cumsum();dd=eq-eq.cummax();rows.append(dict(split=split,part=label,n=len(q),win_rate=(r>0).mean(),avg_r=r.mean(),pf=r[r>0].sum()/-r[r<0].sum(),max_dd_r=dd.min()))
    for y,q in x.groupby(x.entry_date.dt.year):
        r=q.r;rows.append(dict(split='year',part=str(y),n=len(q),win_rate=(r>0).mean(),avg_r=r.mean(),pf=r[r>0].sum()/-r[r<0].sum(),max_dd_r=np.nan))
    s=pd.DataFrame(rows);s.to_csv(out/'summary.csv',index=False);print(s.to_string(index=False))

if __name__=='__main__':main()
