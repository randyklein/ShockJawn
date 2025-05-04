"""Feature engineering & shock label utilities."""
import pandas as pd
import numpy as np
from ta.volatility import AverageTrueRange  # pip install ta
from .config import SHOCK_SIGMA, HOLD_DAYS

def add_volatility(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ret"] = df["close"].pct_change()
    df["sigma20"] = df["ret"].rolling(20).std(ddof=0)
    atr = AverageTrueRange(df["high"], df["low"], df["close"], window=14)
    df["atr14"] = atr.average_true_range()
    return df

def label_shocks(df: pd.DataFrame, sigma=SHOCK_SIGMA) -> pd.DataFrame:
    df = add_volatility(df)
    cond = df["ret"] <= -sigma * df["sigma20"]
    df["is_shock"] = cond.astype(int)
    # target = forward % change over HOLD_DAYS
    df["target_r"] = df["close"].shift(-HOLD_DAYS) / df["close"] - 1.0
    return df
