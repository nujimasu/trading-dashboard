"""Validate logic5 entries with resistance target and EMA20 runner."""
import pickle
import sys
from pathlib import Path
import pandas as pd
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.swing_strategy_research import CACHE, indicators


def sim(d, sig_date, stop, max_hold=30, cost_bps=10, min_rr=.50):
    try: i=d.index.get_loc(sig_date)
    except KeyError:return None
    if i+1>=len(d) or i<60:return None
    e=i+1;entry=float(d.Open.iloc[e]);risk=entry-stop
    resistance=float(d.High.iloc[i-60:i].max())*.995
    rr=(resistance-entry)/risk if risk>0 else -1
    if risk<=0 or risk/entry>.15 or rr<min_rr:return None
    hit=False;curstop=stop;j=e;pending=False
    for j in range(e,min(e+max_hold,len(d))):
        o,h,l,c=map(float,(d.Open.iloc[j],d.High.iloc[j],d.Low.iloc[j],d.Close.iloc[j]))
        if pending:
            px=o;status='ema20_runner';break
        if o<=curstop: px=o;status='gap_stop';break
        if l<=curstop: px=curstop;status='be' if hit else 'stop';break
        if not hit and (o>=resistance or h>=resistance):
            hit=True;curstop=entry
        if hit and c<float(d.ema20.iloc[j]):pending=True
    else: px=float(d.Close.iloc[j]);status='time'
    exit_r=(px-entry)/risk;target_r=(resistance-entry)/risk
    r=(2/3*target_r+1/3*exit_r) if hit else exit_r
    r-=2*cost_bps/10000*entry/risk
    return dict(entry_date=d.index[e],exit_date=d.index[j],r=r,planned_rr=rr,
                status=status,hit_target=hit)


def main():
    src=pd.read_csv('research/results/logic5_validation/trades.csv',parse_dates=['signal_date'])
    with CACHE.open('rb') as f:raw=pickle.load(f)
    data={t:indicators(d[['Open','High','Low','Close','Volume']]) for t,d in raw.items()}
    # Strict point-in-time regime.
    flags=[]
    for t in ('SPY','QQQ'):
        d=data[t];flags.append(((d.Close>d.ema200)&(d.ema50>d.ema200)).rename(t))
    regime=pd.concat(flags,axis=1).all(axis=1)
    out=[]
    for z in src.itertuples():
        if not bool(regime.get(z.signal_date,False)):continue
        tr=sim(data[z.ticker],z.signal_date,z.entry-z.risk)
        if tr:tr.update(ticker=z.ticker,signal_date=z.signal_date,pa=z.pa,osc=z.osc);out.append(tr)
    x=pd.DataFrame(out).drop_duplicates(['ticker','signal_date'])
    x=x.sort_values(['entry_date','osc','pa'],ascending=[True,False,True])
    active=[];accepted=[]
    for z in x.itertuples():
        active=[a for a in active if a[0]>z.entry_date]
        if len(active)>=30 or z.ticker in {a[1] for a in active}:continue
        active.append((z.exit_date,z.ticker));accepted.append(z)
    a=pd.DataFrame(accepted);dest=Path('research/results/logic5_structural_exit');dest.mkdir(parents=True,exist_ok=True)
    a.to_csv(dest/'trades.csv',index=False);rows=[]
    for label,q in [('train',a[a.entry_date<'2025-01-01']),('validation',a[(a.entry_date>='2025-01-01')&(a.entry_date<'2026-01-01')]),('holdout',a[a.entry_date>='2026-01-01']),('oos',a[a.entry_date>='2025-01-01'])]:
        r=q.r;rows.append(dict(part=label,n=len(q),win_rate=(r>0).mean(),avg_r=r.mean(),pf=r[r>0].sum()/-r[r<0].sum(),avg_win=r[r>0].mean(),avg_loss=-r[r<0].mean(),payoff=r[r>0].mean()/-r[r<0].mean()))
    s=pd.DataFrame(rows);s.to_csv(dest/'summary.csv',index=False);print(s.to_string(index=False))

if __name__=='__main__':main()
