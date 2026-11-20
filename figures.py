"""Generate the research exhibits from the machine-readable outputs."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd
from data import OUT, SORTS
from research import drawdown

COLORS = ["#14756c","#ae5b2e","#334b80"]


def run():
    frame = pd.read_csv(OUT/"spreads.csv")
    large = pd.read_csv(OUT/"large_monthly.csv",index_col=0,parse_dates=True)
    fig, ax = plt.subplots(figsize=(8.4,3.5),layout="constrained")
    for (s,c) in zip(SORTS,COLORS):
        sample = frame[(frame.signal==s)&(frame.window=="Full sample")].sort_values("size")
        ax.plot(sample["size"],sample.ann_mean,marker="o",label=s,color=c,lw=2)
    ax.axhline(0,color="#899298",lw=.8)
    ax.yaxis.set_major_formatter(PercentFormatter(1,0))
    ax.set(xticks=range(1,6),xticklabels=["1 · Smallest","2","3","4","5 · Largest"],
           ylabel="Annualized mean gross spread")
    ax.legend(frameon=False,ncol=3,loc="upper right")
    ax.spines[["right","top"]].set_visible(False)
    fig.savefig(OUT/"size_profile.png",dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(2,1,figsize=(9,6),sharex=True,layout="constrained")
    for s,c in zip(SORTS,COLORS):
        axes[0].plot((1+large[s]).cumprod(),color=c,label=s,lw=1.4)
        axes[1].plot(drawdown(large[s]),color=c,lw=1.4)
    axes[0].legend(frameon=False,ncol=3)
    axes[0].set_ylabel("Gross spread wealth ($1 initial)")
    axes[1].set_ylabel("Drawdown from peak")
    axes[1].yaxis.set_major_formatter(PercentFormatter(1,0))
    for ax in axes:
        ax.spines[["right","top"]].set_visible(False)
    fig.savefig(OUT/"spread_paths.png",dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    run()
