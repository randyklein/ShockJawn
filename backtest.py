#!/usr/bin/env python
import argparse
import sys
from pathlib import Path

import pandas as pd
import backtrader as bt
from loguru import logger

from ibot.config import START_CASH, SLIPPAGE_PERC
from ibot.data import load_symbol_minute, minute_to_daily
from ibot.strategy import ShockReboundStrategy
from ibot.model import load_or_train
from ibot.reporting import write as write_report

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True,
                    help="List of tickers, or 'all' to run full universe")
    ap.add_argument("--from",    dest="start", required=True)
    ap.add_argument("--to",      dest="end",   required=True)
    args = ap.parse_args(argv)

    # Expand "all" into your universe
    if args.symbols == ["all"]:
        uni_csv = Path("universe/top200.csv")
        symbols = pd.read_csv(uni_csv)["symbol"].tolist()
    else:
        symbols = args.symbols

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(START_CASH)
    cerebro.broker.set_slippage_perc(perc=SLIPPAGE_PERC)

    # Train or load model
    model = load_or_train(symbols, "2014-01-02", args.start)
    cerebro.addstrategy(ShockReboundStrategy, model=model)

    # Minimum bars needed to compute ATR14 and StdDev20
    min_bars = max(14, 20) + 1  # +1 for percent-change

    # Keep track of which made it in
    added = []

    # Add data feeds for each symbol
    for sym in symbols:
        daily = minute_to_daily(load_symbol_minute(sym)).loc[args.start:args.end]
        if len(daily) < min_bars:
            logger.warning("Skipping {}: only {} days (<{} required)", sym, len(daily), min_bars)
            continue
        cerebro.adddata(bt.feeds.PandasData(dataname=daily), name=sym)
        added.append(sym)

    # Add SPY as benchmark (should always have enough data)
    spy_daily = minute_to_daily(load_symbol_minute("SPY")).loc[args.start:args.end]
    cerebro.adddata(bt.feeds.PandasData(dataname=spy_daily), name="SPY")

    logger.info("Running back-test with {} symbols: {}", len(added), ", ".join(added))
    results = cerebro.run()
    strat   = results[0]

    # Build bot equity curve
    dates, values = zip(*strat.value_hist)
    bot_eq = pd.Series(values, index=pd.DatetimeIndex(dates, tz="UTC"))

    # Build SPY curve directly from DataFrame
    spy_curve = spy_daily["close"] / spy_daily["close"].iloc[0] * START_CASH

    spy_curve *= (1 - 0.15)

    # Write detailed report (now with full universe subset and slippage/tax)
    write_report(
        bot_eq,
        spy_curve,
        trades=pd.DataFrame(strat.trade_log),
        params=dict(
            start=args.start,
            end=args.end,
            symbols=",".join(added)
        )
    )

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
