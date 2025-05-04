"""Markdown report writer for a back-test run."""
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

    # --- plot ---
    plt.figure()
    equity_curve.plot(label="Bot")
    spy_curve.plot(label="SPY TR")
    plt.legend(); plt.tight_layout()
    plt.savefig(img_path)
    plt.close()

    # --- summary stats ---
    def cagr(s: pd.Series) -> float | None:
        start, end = s.index[0], s.index[-1]
        yrs = (end - start).days / 365.25
        if yrs <= 0:
            return None
        return (s.iloc[-1] / s.iloc[0]) ** (1/yrs) - 1

    bot_cagr = cagr(equity_curve)
    spy_cagr = cagr(spy_curve)

    summary = {
        "Bot CAGR":   f"{bot_cagr:.2%}" if bot_cagr is not None else "N/A",
        "SPY CAGR":   f"{spy_cagr:.2%}" if spy_cagr is not None else "N/A",
        "Max DD":     f"{(equity_curve / equity_curve.cummax() - 1).min():.2%}",
        "Trades":     len(trades),
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
        f.write("## Trades (head)\n\n")
        f.write(trades.head(10).to_markdown() + "\n")

    logger.success("Report saved ➜ {}", md_path)
