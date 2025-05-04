#!/usr/bin/env python
"""Run strategy vs. SPY benchmark, after-tax returns baked in."""
import argparse
import sys

import pandas as pd
import backtrader as bt

from ibot.config import START_CASH
from ibot.data import load_symbol_minute, minute_to_daily
from ibot.strategy import ShockReboundStrategy
from ibot.model import load_or_train
from ibot.reporting import write as write_report
from loguru import logger

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--from",    dest="start", required=True)
    ap.add_argument("--to",      dest="end",   required=True)
    args = ap.parse_args(argv)

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(START_CASH)

    # Load or train model
    model = load_or_train(args.symbols, "2014-01-02", args.start)
    cerebro.addstrategy(ShockReboundStrategy, model=model)

    # Strategy data feeds (for entry/exit signals)
    for sym in args.symbols:
        daily = minute_to_daily(load_symbol_minute(sym)).loc[args.start:args.end]
        cerebro.adddata(bt.feeds.PandasData(dataname=daily), name=sym)

    # Add SPY feed too (so strategy can see its timeline, though it won't trade it)
    spy_daily = minute_to_daily(load_symbol_minute("SPY")).loc[args.start:args.end]
    cerebro.adddata(bt.feeds.PandasData(dataname=spy_daily), name="SPY")

    logger.info("Running back-test …")
    results = cerebro.run()
    strat   = results[0]

    # Build bot equity curve from strategy.value_hist
    dates, values = zip(*strat.value_hist)
    bot_eq = pd.Series(values, index=pd.DatetimeIndex(dates, tz="UTC"))

    # Build SPY curve directly from DataFrame
    spy_curve = spy_daily["close"] / spy_daily["close"].iloc[0] * START_CASH

    # NOTE: trades DataFrame still empty until we wire up a proper trade logger
    write_report(
        bot_eq,
        spy_curve,
        trades=pd.DataFrame(),
        params=dict(start=args.start, end=args.end, symbols=",".join(args.symbols))
    )

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
