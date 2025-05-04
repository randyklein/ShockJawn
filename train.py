#!/usr/bin/env python
"""CLI to train LightGBM model."""
import argparse, sys
from ibot.model import train

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["all"],
                    help="'all' = universe/top200.csv else list")
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to",   dest="end",   required=True)
    args = ap.parse_args(argv)

    if args.symbols == ["all"]:
        import pandas as pd, pathlib
        symbols = pd.read_csv(pathlib.Path("universe/top200.csv"))["symbol"].tolist()
    else:
        symbols = args.symbols

    train(symbols, args.start, args.end)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
