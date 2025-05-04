#!/usr/bin/env python
"""Run strategy vs. SPY benchmark, after-tax returns baked in."""
import argparse, sys, pandas as pd, backtrader as bt
from config import START_CASH
from data import load_symbol_minute, minute_to_daily
from strategy import ShockReboundStrategy
from model import load_or_train
from reporting import write as write_report
from loguru import logger

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to",   dest="end",   required=True)
    args = ap.parse_args(argv)

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(START_CASH)

    # --- load trained model (train on-demand if absent) ---
    model = load_or_train(args.symbols, "2014-01-02", args.start)

    cerebro.addstrategy(ShockReboundStrategy, model=model)

    # --- add data feeds ---
    for sym in args.symbols + ["SPY"]:
        daily = minute_to_daily(load_symbol_minute(sym)).loc[args.start:args.end]
        cerebro.adddata(bt.feeds.PandasData(dataname=daily), name=sym)

    logger.info("Running back-test …")
    cerebro.run()
    bot_eq = pd.Series(cerebro.broker._value_history,
                       index=pd.to_datetime(cerebro.broker._value_history_times, unit="s", utc=True))
    spy = cerebro.datas[-1]  # last feed added is SPY
    spy_px = spy.close.array
    spy_idx = pd.to_datetime(spy.datetime.array, unit="s", utc=True)
    spy_curve = pd.Series(spy_px, index=spy_idx).ffill()
    spy_curve = spy_curve / spy_curve.iloc[0] * START_CASH

    # dummy empty trade log for now (Backtrader trade list easier later)
    write_report(bot_eq, spy_curve, trades=pd.DataFrame(), params=dict(
        start=args.start, end=args.end, symbols=",".join(args.symbols)
    ))

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
