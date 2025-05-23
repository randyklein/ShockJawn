# ibot/model.py

"""Train / load the LightGBM rebound-prediction model."""
from pathlib import Path
import lightgbm as lgb
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from loguru import logger
from .config import HOLD_DAYS, SHOCK_SIGMA, DATA_PROCESSED, PROJECT_ROOT
from .data import load_daily
from .features import label_shocks

MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = MODEL_DIR / "shock_rebound.lgb"

FEATURES = [
    "ret", "sigma20", "atr14",
    # cross-sectional (z-score) relatives can be appended later
]

def build_dataset(symbols: list[str], date_from: str, date_to: str) -> pd.DataFrame:
    """Return a concatenated DataFrame (multi-symbol) of shock rows only."""
    dfs = []
    # compute minimum rows needed for rolling windows + hold
    min_rows = max(20, 14) + HOLD_DAYS + 1

    for sym, df in load_daily(symbols).items():
        df = df.loc[date_from:date_to]
        if df.empty:
            logger.warning("No data for {} in {}–{}", sym, date_from, date_to)
            continue

        if len(df) < min_rows:
            logger.warning(
                "Not enough data for {}: {} rows (< {})",
                sym, len(df), min_rows
            )
            continue

        try:
            df_labeled = label_shocks(df, SHOCK_SIGMA)
        except Exception as e:
            logger.error("Failed to label shocks for {}: {}", sym, e)
            continue

        shocks = df_labeled[df_labeled["is_shock"] == 1].copy()
        if shocks.empty:
            logger.debug("No shocks found for {}", sym)
            continue

        shocks["symbol"] = sym
        dfs.append(shocks)

    if not dfs:
        raise ValueError("No shock data found across all symbols; nothing to train on")

    dataset = pd.concat(dfs)
    logger.info("Built dataset with {} shock rows across {} symbols", len(dataset), len(dfs))
    return dataset

def train(symbols: list[str], date_from: str, date_to: str):
    data = build_dataset(symbols, date_from, date_to)
    X = data[FEATURES]
    y = data["target_r"]

    tscv = TimeSeriesSplit(n_splits=5)
    lgb_params = dict(
        objective="regression",
        metric="l2",
        n_estimators=500,
        learning_rate=0.03,
        num_leaves=63,
        subsample=0.8,
        colsample_bytree=0.8,
    )
    model = lgb.LGBMRegressor(**lgb_params)

    # Manual CV loop so we can log each fold
    rmses = []
    for k, (tr, va) in enumerate(tscv.split(X)):
        model.fit(X.iloc[tr], y.iloc[tr])
        p = model.predict(X.iloc[va])
        rmse = ((p - y.iloc[va]) ** 2).mean() ** 0.5
        logger.info("Fold {} RMSE={:.5f}", k + 1, rmse)
        rmses.append(rmse)

    logger.info("CV avg RMSE {:.5f}", sum(rmses) / len(rmses))

    model.fit(X, y)        # final fit on all data
    model.booster_.save_model(str(MODEL_PATH))
    logger.success("Model saved ➜ {}", MODEL_PATH)
    return model

def load_or_train(symbols: list[str], date_from: str, date_to: str):
    if MODEL_PATH.exists():
        logger.info("Loading cached model {}", MODEL_PATH)
        return lgb.Booster(model_file=str(MODEL_PATH))
    logger.info("Cached model not found—training anew")
    return train(symbols, date_from, date_to)
