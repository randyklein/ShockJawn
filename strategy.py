# ibot/strategy.py
import backtrader as bt
from .config import RISK_BUDGET, ATR_MULT, HOLD_DAYS
from .taxes import TaxLots


class ShockReboundStrategy(bt.Strategy):
    params = dict(
        model=None,            # a fitted scikit-learn-like regressor (not used yet)
        risk_budget=RISK_BUDGET,
        atr_mult=ATR_MULT,
        hold_days=HOLD_DAYS,
    )

    def __init__(self):
        # set up FIFO tax‐lot accounting
        self.tax = TaxLots()

        # indicators per data feed
        self.inds = {}
        for d in self.datas:
            atr   = bt.ind.ATR(d, period=14)
            ret   = bt.ind.PercentChange(d.close, period=1)
            sigma = bt.ind.StdDev(ret, period=20)
            shock = ret < (-self.p.atr_mult) * sigma

            self.inds[d] = dict(atr=atr, ret=ret, sigma=sigma, shock=shock)
            d.shock = shock  # expose for logic below

    def next(self):
        for d in self.datas:
            pos = self.getposition(d)
            i   = self.inds[d]
            dt  = d.datetime.datetime(0)
            price = d.close[0]

            # ENTRY: no position + shock detected
            if not pos and i["shock"][0]:
                risk_per_share = i["atr"][0] * self.p.atr_mult
                stake = int((self.broker.getcash() * self.p.risk_budget) / risk_per_share)
                if stake > 0:
                    # record the lot
                    self.tax.buy(d._name, stake, price, dt)
                    # execute
                    self.buy(data=d, size=stake)
                    d.entry_price = price
                    d.entry_bar   = len(d)

            # EXIT: position exists
            elif pos:
                gross = (price - d.entry_price) * pos.size

                # time stop
                if len(d) - d.entry_bar >= self.p.hold_days:
                    net = self.tax.sell(d._name, pos.size, price, dt)
                    tax = gross - net
                    self.close(data=d)
                    # subtract tax from cash so equity curve is net of taxes
                    self.broker.addcash(-tax)

                else:
                    # profit‐take or hard stop
                    stop  = d.entry_price - i["atr"][0] * self.p.atr_mult
                    limit = d.entry_price + i["atr"][0] * self.p.atr_mult
                    if price <= stop or price >= limit:
                        net = self.tax.sell(d._name, pos.size, price, dt)
                        tax = gross - net
                        self.close(data=d)
                        self.broker.addcash(-tax)
