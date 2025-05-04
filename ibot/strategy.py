# ibot/strategy.py
import backtrader as bt
from loguru import logger
from .config import RISK_BUDGET, ATR_MULT, HOLD_DAYS, SLIPPAGE_PERC
from .taxes import TaxLots


class ShockReboundStrategy(bt.Strategy):
    params = dict(model=None,
                  risk_budget=RISK_BUDGET,
                  atr_mult=ATR_MULT,
                  hold_days=HOLD_DAYS)

    # ------------------------------------------------------------------ init
    def __init__(self):
        self.tax        = TaxLots()
        self.value_hist = []         # [(datetime, equity)]
        self.trade_log  = []         # one dict per round-trip

        self.inds = {}
        for d in self.datas:
            atr   = bt.ind.ATR(d, period=14)
            ret   = bt.ind.PercentChange(d.close, period=1)
            sigma = bt.ind.StdDev(ret, period=20)
            shock = ret < (-self.p.atr_mult) * sigma
            self.inds[d] = dict(atr=atr, shock=shock)
            d.shock = shock

    # ----------------------------------------------------------- bookkeeping
    def start(self):
        self.value_hist.append((self.datas[0].datetime.datetime(0),
                                self.broker.getvalue()))

    def next(self):
        self.value_hist.append((self.datas[0].datetime.datetime(0),
                                self.broker.getvalue()))

        for d in self.datas:
            pos   = self.getposition(d)
            atr14 = self.inds[d]["atr"][0]

            # ------------- entry -------------
            if not pos and d.shock[0]:
                risk = atr14 * self.p.atr_mult
                shares = int(self.broker.getcash() * self.p.risk_budget / risk)
                if shares > 0:
                    self.buy(data=d, size=shares)

            # ------------- exit --------------
            elif pos:
                held = len(d) - getattr(d, "entry_bar", len(d))
                stop  = d.entry_price - atr14 * self.p.atr_mult
                limit = d.entry_price + atr14 * self.p.atr_mult
                if d.close[0] <= stop or d.close[0] >= limit or held >= self.p.hold_days:
                    self.close(data=d)

    # -------------------------------------------------------- force close all
    def stop(self):
        dt = self.datas[0].datetime.datetime(0)

        for d in self.datas:
            pos = self.getposition(d)
            if not pos:
                continue                              # already flat

            if d.close[0] != d.close[0]:             # price is NaN
                logger.warning("Skip final close for %s – last price NaN", d._name)
                continue

            size  = abs(pos.size)
            price = d.close[0]
            gross = (price - d.entry_price) * size

            # sell only what we still hold
            net_after_tax = self.tax.sell(d._name, size, price, dt)
            tax  = gross - net_after_tax
            slip = size * price * SLIPPAGE_PERC
            self.broker.add_cash(-tax - slip)

            # ---------- update existing open trade row ----------
            for rec in reversed(self.trade_log):
                if rec["symbol"] == d._name and rec.get("exit_date") is None:
                    rec.update(exit_date=dt, exit_price=price,
                               gross=gross, tax=tax,
                               slippage=slip, net=gross - tax - slip)
                    break
            else:
                # (should not happen) – create a row if none exists
                self.trade_log.append(dict(
                    symbol=d._name, entry_date=d.entry_dt,
                    exit_date=dt, size=size,
                    entry_price=d.entry_price, exit_price=price,
                    gross=gross, tax=tax, slippage=slip,
                    net=gross - tax - slip
                ))

        # record equity after everything is realised
        self.value_hist.append((dt, self.broker.getvalue()))

    # -------------------------------------------------------------- order fill
    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return

        d, sym = order.data, order.data._name
        dt, px = d.datetime.datetime(0), order.executed.price
        size   = abs(order.executed.size)

        # ---------------------- BUY ----------------------
        if order.status == order.Completed and order.isbuy():
            self.tax.buy(sym, size, px, dt)
            self.broker.add_cash(-size * px * SLIPPAGE_PERC)

            d.entry_price, d.entry_dt, d.entry_bar = px, dt, len(d)
            self.trade_log.append({
                "symbol":      sym,
                "entry_date":  dt,
                "exit_date":   None,
                "size":        size,
                "entry_price": px
            })

        # ---------------------- SELL ---------------------
        elif order.status == order.Completed and order.issell():
            gross = (px - d.entry_price) * size
            after = self.tax.sell(sym, size, px, dt)
            tax   = gross - after
            slip  = size * px * SLIPPAGE_PERC
            self.broker.add_cash(-tax - slip)

            for rec in reversed(self.trade_log):
                if rec["symbol"] == sym and rec.get("exit_date") is None:
                    rec.update(exit_date=dt, exit_price=px,
                               gross=gross, tax=tax,
                               slippage=slip, net=gross - tax - slip)
                    break
