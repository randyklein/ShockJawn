from pathlib import Path
import os

# PROJECT_ROOT should be the directory containing this file’s parent folder (ibot/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# now data paths point under <repo root>/data/...
DATA_RAW       = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ---------- back-test defaults ----------
START_CASH   = 10_000
RISK_BUDGET  = 0.05    # 5% of equity at risk per trade
ATR_MULT     = 2       # for stop/profit
SHOCK_SIGMA  = 2.5     # daily drop ≥ 2.5σ triggers candidate
HOLD_DAYS    = 30      # evaluation horizon / max hold


# ─── Alpaca credentials ───────────────────────────────────────────── ─────────────────────────────────────────────
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")
ALPACA_PAPER = True  # False → live trading