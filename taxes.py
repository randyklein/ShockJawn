"""Lot-tracking tax helper (FIFO).  Called from Strategy."""
from collections import deque
from datetime import datetime, timedelta
from loguru import logger

ST_CG_RATE = 0.24
LT_CG_RATE = 0.15
LT_HOLD_DAYS = 365

class TaxLots:
    """Maintains FIFO lots per symbol and computes after-tax P&L on exit."""

    def __init__(self):
        self.lots = {}   # symbol → deque([(shares, cost, entry_date)])

    def buy(self, sym: str, shares: int, price: float, date: datetime):
        self.lots.setdefault(sym, deque()).append([shares, price, date])

    def sell(self, sym: str, shares: int, price: float, date: datetime) -> float:
        gain_net = 0.0
        q = self.lots.get(sym, deque())
        while shares > 0 and q:
            lot_shares, cost, entry_date = q[0]
            take = min(shares, lot_shares)
            gross = (price - cost) * take
            held_days = (date - entry_date).days
            tax_rate = LT_CG_RATE if held_days >= LT_HOLD_DAYS else ST_CG_RATE
            tax = max(gross, 0) * tax_rate    # only gains are taxed
            gain_net += gross - tax

            lot_shares -= take
            shares -= take
            if lot_shares == 0:
                q.popleft()
            else:
                q[0][0] = lot_shares
        if shares > 0:
            logger.warning("Selling more than we own? {} shares left", shares)
        return gain_net
