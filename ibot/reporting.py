from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
from loguru import logger
from .config import PROJECT_ROOT

REPORT_DIR = PROJECT_ROOT / "reports"
IMG_DIR    = REPORT_DIR / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)


def write(equity_curve: pd.Series,
          spy_curve: pd.Series,
          trades: pd.DataFrame,
          params: dict):
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    img_path = IMG_DIR / f"equity_{ts}.png"

    # ---------- plot ----------
    plt.figure()
    equity_curve.plot(label="Bot")
    spy_curve.plot(label="SPY TR")
    plt.legend(); plt.tight_layout()
    plt.savefig(img_path); plt.close()

    # ---------- helper ----------
    def cagr(series):
        s = series.sort_index()
        s = s.loc[~s.index.normalize().duplicated(keep="first")]
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        return None if yrs <= 0 else (s.iloc[-1]/s.iloc[0])**(1/yrs) - 1

    bot_cagr = cagr(equity_curve)
    spy_cagr = cagr(spy_curve)

    # ---------- dollar aggregates ----------
    totals = (trades[["gross","tax","slippage","net"]]
              .sum()
              .rename({"gross":"Gross P&L",
                       "tax":"Taxes",
                       "slippage":"Slippage",
                       "net":"Net P&L"}))

    start_eq = equity_curve.iloc[0]
    end_eq   = equity_curve.iloc[-1]
    ret_abs  = end_eq - start_eq
    ret_pct  = end_eq / start_eq - 1

    summary = {
        "Start Equity":     f"${start_eq:,.2f}",
        "End Equity":       f"${end_eq:,.2f}",
        "Total Return $":   f"${ret_abs:,.2f}",
        "Total Return %":   f"{ret_pct:.2%}",
        "Bot CAGR (less tax & fees)":         f"{cagr(equity_curve):.2%}" if cagr(equity_curve) is not None else "N/A",
        "SPY CAGR (less 15% tax)":         f"{cagr(spy_curve):.2%}" if cagr(spy_curve)     is not None else "N/A",
        "Total Gross P&L $":f"${totals['Gross P&L']:,.0f}",
        "Total Taxes $":    f"${totals['Taxes']:,.0f}",
        "Total Slippage $": f"${totals['Slippage']:,.0f}",
        "Total Net P&L $":  f"${totals['Net P&L']:,.0f}",
        "Max DD":           f"{(equity_curve/ equity_curve.cummax() - 1).min():.2%}",
        "Trades":           len(trades),
        **params
    }

    md_path = REPORT_DIR / f"{ts}.md"
    with open(md_path, "w") as f:
        f.write(f"# Back-test report {ts}\n\n")
        f.write(f"![equity](img/{img_path.name})\n\n")
        f.write("## Summary\n")
        for k, v in summary.items():
            f.write(f"- **{k}**: {v}\n")
        f.write("\n---\n")
        f.write("## Trades\n\n")
        if trades.empty:
            f.write("_No trades executed_\n")
        else:
            f.write(trades.to_markdown(index=False))

    logger.success("Report saved ➜ {}", md_path)
