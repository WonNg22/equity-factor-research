"""Evaluate historical spreads across size buckets and report sampling uncertainty."""
import sqlite3
import numpy as np
import pandas as pd
from data import DB, OUT, SORTS


def hac_se(x, lags=6):
    x = np.asarray(x, dtype=float)
    u = x - x.mean()
    variance = np.dot(u, u) / len(x)
    for k in range(1, min(lags, len(x)-1)+1):
        variance += 2*(1-k/(lags+1))*np.dot(u[k:], u[:-k])/len(x)
    return np.sqrt(max(0, variance)/len(x))


def drawdown(r):
    wealth = (1+r).cumprod()
    return wealth / wealth.cummax().clip(lower=1)-1


def metrics(r):
    se = hac_se(r)
    vol = r.std()*np.sqrt(12)
    return dict(months=len(r), ann_mean=12*r.mean(), ann_vol=vol,
                gross_sharpe=12*r.mean()/vol, max_drawdown=drawdown(r).min(),
                positive_months=(r>0).mean(), hac_t=r.mean()/se if se else np.nan,
                ci_low=12*(r.mean()-1.96*se), ci_high=12*(r.mean()+1.96*se))


def spread(legs, signal):
    return legs[5]-legs[1] if signal == "Momentum" else legs[1]-legs[5]


def run():
    OUT.mkdir(exist_ok=True)
    with sqlite3.connect(DB) as conn:
        p = pd.read_sql_query("SELECT * FROM portfolios ORDER BY month", conn)
        b = pd.read_sql_query("SELECT * FROM benchmarks ORDER BY month", conn, index_col="month")
    rows, bins, gaps, all_spreads = [], [], [], {}
    windows = {"Full sample": ("2005-01","2026-09"), "2005–12": ("2005-01","2012-12"),
               "2013–19": ("2013-01","2019-12"), "2020–Sep 2026": ("2020-01","2026-09")}
    for (signal, size), panel in p.groupby(["signal","size_q"]):
        legs = panel.pivot(index="month", columns="signal_q", values="ret")
        r = spread(legs, signal)
        all_spreads[signal,size] = r
        for window, (start,end) in windows.items():
            rows.append(dict(signal=signal, size=size, window=window, **metrics(r.loc[start:end])))
        for q in legs:
            excess = legs[q] - b.RF
            bins.append(dict(signal=signal,size=size,quintile=q, ann_mean=12*legs[q].mean(),
                             ann_vol=legs[q].std()*np.sqrt(12),
                             sharpe=excess.mean()/excess.std()*np.sqrt(12)))
    for signal in SORTS:
        diff = all_spreads[signal,1]-all_spreads[signal,5]
        gaps.append(dict(signal=signal, **metrics(diff)))
    pd.DataFrame(gaps).to_csv(OUT/"small_minus_big.csv", index=False)
    pd.DataFrame(rows).to_csv(OUT/"spreads.csv", index=False)
    pd.DataFrame(bins).to_csv(OUT/"quintiles.csv", index=False)
    large = pd.DataFrame({s:all_spreads[s,5] for s in SORTS})
    large.to_csv(OUT/"large_monthly.csv")
    large.join(b[["Mom","ST_Rev","Mkt-RF"]]).corr().to_csv(OUT/"correlations.csv")
    events = {"Financial crisis 2008–09":("2008-01","2009-12"),
              "April 2009":("2009-04","2009-04"),"March 2020":("2020-03","2020-03"),
              "Calendar 2022":("2022-01","2022-12")}
    pd.DataFrame({k:(1+large.loc[a:z]).prod()-1 for k,(a,z) in events.items()}).T.to_csv(OUT/"events.csv")
    scenarios = []
    for signal in SORTS:
        for traded in (0.5,1,2,4):
            for bps in (5,10,20):
                net = large[signal] - traded*bps/10000
                scenarios.append(dict(signal=signal, assumed_traded_per_nav=traded,
                                      one_way_bps=bps, **metrics(net)))
    pd.DataFrame(scenarios).to_csv(OUT/"cost_scenarios.csv",index=False)


if __name__ == "__main__":
    run()
