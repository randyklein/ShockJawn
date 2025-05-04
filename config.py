from pathlib import Path
import os

# ---------- paths ----------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = PROJECT_ROOT / "data" / "raw"       # 1-min bars
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"  # optional caches
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ---------- back-test defaults ----------
START_CASH = 10_000
RISK_BUDGET = 0.05          # 5 % of equity at risk per trade
ATR_MULT = 2                # for stop/profit
SHOCK_SIGMA = 2.5           # daily drop ≥ 2.5σ triggers candidate
HOLD_DAYS = 30              # evaluation horizon / max hold

# ─── Alpaca credentials ───────────────────────────────────────────── ─────────────────────────────────────────────
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")
ALPACA_PAPER = True  # False → live trading