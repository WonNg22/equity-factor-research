"""Optional diagnostics for a user-supplied point-in-time security panel."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def signals(history):
    """Formation month t close; next monthly total return is scored separately."""
    returns = history.set_index("month").monthly_ret
    months = pd.period_range(returns.index.min(), returns.index.max(), freq="M")
    returns = returns.reindex(months)
    result = pd.DataFrame(index=months)
    result["Momentum"] = (1+returns.shift(1)).rolling(11).apply(np.prod, raw=True)-1
    result["Reversal"] = -returns
    result["Low volatility"] = -history.set_index("month").vol60.reindex(months)
    result["forward_ret"] = returns.shift(-1)
    return result.rename_axis("month")


def evaluate(panel):
    panel = panel.copy()
    panel["month"] = pd.PeriodIndex(panel.month, freq="M")
    if panel.duplicated(["security_id","month"]).any():
        raise ValueError("Duplicate security-month")
    if not panel.eligible.isin([0,1]).all():
        raise ValueError("eligible must be 0 or 1")
    if (panel.vol60.dropna()<0).any() or (panel.monthly_ret.dropna()<-1).any():
        raise ValueError("Invalid security return or volatility")
    formed = []
    for security, history in panel.groupby("security_id"):
        sample = signals(history)
        sample["eligible"] = history.set_index("month").eligible
        formed.append(sample.assign(security_id=security).reset_index())
    data = pd.concat(formed)
    data = data[(data.eligible==1)&(data.month<panel.month.max())]
    rows = []
    for month, group in data.groupby("month"):
        for name in ("Momentum","Reversal","Low volatility"):
            # Select on formation data before checking outcomes. Missing delisting
            # observations should stop the experiment, not silently drop the stock.
            g = group.dropna(subset=[name])
            if g.forward_ret.isna().any():
                raise ValueError(f"Missing holding return at formation {month} ({name})")
            if len(g)>=5 and g[name].nunique()>1 and g.forward_ret.nunique()>1:
                ic = g[name].rank().corr(g.forward_ret.rank())
                rows.append(dict(formation=str(month), holding=str(month+1),
                                 signal=name, n=len(g), rank_ic=ic))
    return pd.DataFrame(rows,columns=["formation","holding","signal","n","rank_ic"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel",type=Path)
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    evaluate(pd.read_csv(args.panel)).to_csv(args.output,index=False)
