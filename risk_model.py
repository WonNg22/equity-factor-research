"""Estimate size interaction intercepts conditional on market, size and value."""
import sqlite3
import numpy as np
import pandas as pd
from data import DB, OUT, SORTS
from research import spread


def fit(y, factors, lags=6):
    x = np.column_stack([np.ones(len(y)), factors])
    coef = np.linalg.lstsq(x,y,rcond=None)[0]
    scores = x*(np.asarray(y)-x@coef)[:,None]
    meat = scores.T@scores
    for k in range(1,lags+1):
        covariance = scores[k:].T@scores[:-k]
        meat += (1-k/(lags+1))*(covariance+covariance.T)
    bread = np.linalg.inv(x.T@x)
    se = np.sqrt((bread@meat@bread)[0,0])
    return dict(ann_intercept=12*coef[0], hac_t=coef[0]/se,
                market=coef[1], SMB=coef[2], HML=coef[3])


def run():
    with sqlite3.connect(DB) as conn:
        df = pd.read_sql_query("SELECT * FROM portfolios",conn)
        factors = pd.read_sql_query('SELECT month,"Mkt-RF",SMB,HML FROM benchmarks ORDER BY month',
                                    conn,index_col="month")
    rows = []
    for signal in SORTS:
        grid = df[df.signal==signal].pivot(index="month",columns=["size_q","signal_q"],values="ret")
        gap = spread(grid[1],signal)-spread(grid[5],signal)
        rows.append(dict(signal=signal,**fit(gap,factors.loc[gap.index])))
    pd.DataFrame(rows).to_csv(OUT/"risk_adjusted_size_gap.csv",index=False)


if __name__ == "__main__":
    run()
