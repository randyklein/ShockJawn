"""Load 1-min Parquet bars and resample to daily OHLCV."""
import pandas as pd
import pyarrow.parquet as pq
from loguru import logger
from pathlib import Path
from .config import DATA_RAW

def load_symbol_minute(symbol: str, columns=None) -> pd.DataFrame:
    """Return a tz-aware minute-level DataFrame indexed by timestamp."""
    file = DATA_RAW / f"{symbol}.parquet"
    if not file.exists():
        raise FileNotFoundError(file)
    logger.debug(f"Reading {file}")
    table = pq.read_table(file, columns=columns)
    df = table.to_pandas()
    if "timestamp" in df.columns:
        df = df.set_index("timestamp")
    df.index = pd.to_datetime(df.index, utc=True)
    return df.sort_index()

def minute_to_daily(df_min: pd.DataFrame) -> pd.DataFrame:
    """Aggregate minute bars into daily OHLCV."""
    o = df_min["open"].resample("1D").first()
    h = df_min["high"].resample("1D").max()
    l = df_min["low"].resample("1D").min()
    c = df_min["close"].resample("1D").last()
    v = df_min["volume"].resample("1D").sum()
    daily = pd.concat({"open": o, "high": h, "low": l, "close": c, "volume": v}, axis=1)
    return daily.dropna(subset=["open"])  # skip holidays

def load_daily(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Load & cache daily bars for a list of symbols."""
    return {sym: minute_to_daily(load_symbol_minute(sym)) for sym in symbols}
