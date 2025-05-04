# ibot/strategy.py

import backtrader as bt
from loguru import logger
from .config import RISK_BUDGET, ATR_MULT, HOLD_DAYS, SLIPPAGE_PERC
from .taxes import TaxLots


class ShockReboundStrategy(bt.Strategy):
    params = dict(
        model=None,
        risk_budget=RISK_BUDGET,
        atr_mult=ATR_MULT,
        hold_days=HOLD_DAYS,
    )

    def __init__(self):
        # FIFO tax‐lot accounting & P&L tracking
        self.tax        = TaxLots()
        self.value_hist = []   # list of (datetime, equity)
        self.trade_log  = []   # one dict per round‐trip
        self.slip_total = 0.0

        # Precompute indicators per data feed
        self.inds = {}
        for d in self.datas:
            atr   = bt.ind.ATR(d, period=14)
            ret   = bt.ind.PercentChange(d.close, period=1)
            sigma = bt.ind.StdDev(ret, period=20)
            shock = ret < (-self.p.atr_mult) * sigma
            self.inds[d] = dict(atr=atr, ret=ret, sigma=sigma, shock=shock)
            d.shock = shock

    def start(self):
        dt = self.datas[0].datetime.datetime(0)
        self.value_hist.append((dt, self.broker.getvalue()))

    def next(self):
        dt = self.datas[0].datetime.datetime(0)
        self.value_hist.append((dt, self.broker.getvalue()))

        for d in self.datas:
            pos   = self.getposition(d)
            i     = self.inds[d]
            price = d.close[0]

            # ENTRY: no position + shock
            if not pos and i["shock"][0]:
                risk_per_share = i["atr"][0] * self.p.atr_mult
                stake = int((self.broker.getcash() * self.p.risk_budget) / risk_per_share)
                if stake > 0:
                    # generate order; actual recording happens in notify_order
                    self.buy(data=d, size=stake)

            # EXIT: position exists, check stops or time
            elif pos:
                held = len(d) - getattr(d, "entry_bar", len(d))
                stop = d.entry_price - i["atr"][0] * self.p.atr_mult
                limit = d.entry_price + i["atr"][0] * self.p.atr_mult

                if price <= stop or price >= limit or held >= self.p.hold_days:
                    self.close(data=d)

    def notify_order(self, order):
        # ignore interim statuses
        if order.status in (order.Submitted, order.Accepted):
            return

        data   = order.data
        symbol = data._name
        dt     = data.datetime.datetime(0)

        # Completed orders
        if order.status == order.Completed:
            size_signed = order.executed.size
            size = abs(size_signed)          # ALWAYS positive share count
            price = order.executed.price

            # BUY fills
            if order.isbuy():
                # record lot
                self.tax.buy(symbol, size, price, dt)
                # slippage cost (positive)
                slip = size * price * SLIPPAGE_PERC
                self.slip_total += slip
                self.broker.add_cash(-slip)
                # tag for exit logic
                data.entry_price = price
                data.entry_bar   = len(data)
                # new trade log entry
                self.trade_log.append({
                    "symbol":      symbol,
                    "entry_date":  dt,
                    "exit_date":   None,
                    "size":        size,
                    "entry_price": price,
                    "exit_price":  None,
                    "gross":       None,
                    "tax":         None,
                    "slippage":    None,
                    "net":         None,
                })

            # SELL fills
            elif order.issell():
                entry_price = data.entry_price
                gross       = (price - entry_price) * size
                # FIFO tax‐lot accounting returns after-tax proceeds
                net         = self.tax.sell(symbol, size, price, dt)
                tax         = gross - net       # positive if gross>net
                # slippage
                slip = size * price * SLIPPAGE_PERC
                self.slip_total += slip
                self.broker.add_cash(-slip)
                # deduct tax
                self.broker.add_cash(-tax)

                # backfill trade_log
                for rec in reversed(self.trade_log):
                    if rec["symbol"] == symbol and rec["exit_date"] is None:
                        rec.update({
                            "exit_date":   dt,
                            "exit_price":  price,
                            "gross":       gross,
                            "tax":         tax,
                            "slippage":    slip,
                            "net":         gross - tax - slip,
                        })
                        break

            else:
                logger.warning("Order {} for {} completed with unknown side", 
                               order.getordername(), symbol)

        # Canceled/margin/rejected → debug
        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            logger.debug("Order {} for {} status {}", 
                         order.getordername(), symbol, order.status)
