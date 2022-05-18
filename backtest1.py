import numpy as np
import pandas as pd
import database as db
import metrics as mt
import matplotlib.pyplot as plt
from math import floor
from collections import deque


class backtest(object):
    def __init__(self,                  
                 instrument=None,
                 freq='15min',
                 slippage=0, # In measure of ticks
                 acc_id='001',
                 capital=100000,
                 broker_rate=0,
                 ex_rebate=0, # Percentage
                 br_rebate=0,
                ):
        """
        Kwargs:
        1. instrument: str
        2. freq: str (xmins)
        3. slippage: int
        4. acc_id: str
        5. capital: float
        6. broker_rate: float
        7. ex_rebate: float, percentage
        8. br_rebate: float, percentage
        """
        assert instrument != None, 'Instrument Must be Valid'

        # Bacaktest Param
        self.open_fee       = db.GetFees(instrument, 'open')
        self.close_tdy_fee  = db.GetFees(instrument, 'closeT')
        self.close_yst_fee  = db.GetFees(instrument, 'closeN')
        self.ticksize       = db.GetTickSize(instrument)
        self.size           = db.GetContractSize(instrument)
        self.margin         = db.GetMargin(instrument)
        self.instrument     = instrument
        self.freq           = freq
        self.slippage       = slippage
        self.acc_id         = acc_id
        self.capital        = capital
        self.broker_rate    = broker_rate
        self.ex_rebate      = ex_rebate
        self.br_rebate      = br_rebate
        self.freeze_rate    = 0.4
        self.terminate      = False
        self.stoplosstick   = 3
        self.lot            = 1
        self.halt_time      = 15 * 60
        self.halt           = False
        self.dates          = []

        # Metric Param
        self.reports         = []
        self.lpos            = 0
        self.spos            = 0
        self.long_avg_price  = []
        self.short_avg_price = [] 
        self.realized        = 0
        self.unrealized      = 0
        self.yst_pos         = 0
        self.open_pos        = 0
        self.order_id        = 0
        self.ticks           = 0
        
    # Calculate Fees
    def GetFees(self, price, qty, action='open'):
        if action == 'open':
            fee = self.open_fee
        elif action == 'closeT':
            fee = self.close_tdy_fee
        elif action == 'closeN':
            fee = self.close_yst_fee
        else:
            print('Cannot understand action {}'.format(action))
            raise TypeError

        if fee < 1:
            ex_fee = round(price * qty * fee * self.size, 2) 
        else:    
            ex_fee = round(qty * fee, 2)
                
        if self.broker_rate < 1:
            br_fee = ex_fee * (1 + self.broker_rate)
        else:
            br_fee = qty * self.broker_rate
    
        rebate = ex_fee * self.ex_rebate * self.br_rebate
        return ex_fee, br_fee, rebate

    def GetMaxPos(self, price):
        """
        Calculate Max available position
        Current_capital: 当前资金（总资金）
        Used Margin: 已使用保证金
        Margin: 一份合约保证金
        """
        current_capital = self.capital + self.realized + self.unrealized
        used_margin     = (self.lpos + self.spos) * self.margin * price * self.size
        margin          = self.margin * self.size * price
        maxpos = floor((current_capital - used_margin) / margin)
        return maxpos

    def GetAvgPrice(self, q:list):
        if len(q) != 0:
            avg_price = sum(q) / len(q)
        else:
            avg_price = 0
        return avg_price

    def GetRealize(self, q, price, qty, side):
        x = q[:qty]
        avg = sum(x) / len(x)
        if side == 'long':
            realize = round((price - avg) * self.size * qty,2)
        elif side == 'short':
            realize = -1 * round((price - avg) * self.size * qty,2)
        else:
            raise ValueError('No such input side = {}'.format(side))
        return realize


    # 11 Actions
    def open_long(self, price, qty, i):
        """
        开多仓，当lpos >= 0， spos dont care
        """
        assert self.lpos >= 0, 'Failed to Open Long: lpos = {}'.format(self.lpos)
        open_price = price + self.slippage * self.ticksize 
        ex_fee, br_fee, rebate = self.GetFees(open_price, qty, action='open')
        total_fee = ex_fee + br_fee - rebate
        self.long_avg_price = self.long_avg_price + [open_price] * qty
        self.lpos += qty
        self.realized += -total_fee
        self.open_pos += qty
        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((open_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((open_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : open_price,
            'direction' : '多',
            'action'    : '开',
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : -1 * total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        return 0

    def open_short(self, price, qty, i):
        """
        开空仓。当 spos >= 0, lpos dont care
        """
        assert self.spos >= 0, 'Failed to Open Short: spos = {}'.format(self.spos)
        open_price = price - self.slippage * self.ticksize
        ex_fee, br_fee, rebate = self.GetFees(open_price, qty, action='open')
        total_fee = ex_fee + br_fee - rebate
        self.short_avg_price = self.short_avg_price + [open_price] * qty
        self.spos += qty
        self.realized += -total_fee
        self.open_pos += qty
        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((open_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((open_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : open_price,
            'direction' : '空',
            'action'    : '开',
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : -1 * total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        return 0

    def add_long(self, price, qty, i):
        """
        加多仓。lpos > 0
        """
        assert self.lpos > 0, 'Failed to Close Long: lpos = {}'.format(self.lpos)
        open_price = price + self.slippage * self.ticksize
        ex_fee, br_fee, rebate = self.GetFees(open_price, qty, action='open')
        total_fee = ex_fee + br_fee - rebate
        self.long_avg_price = self.long_avg_price + [open_price] * qty
        self.lpos += qty
        self.realized += -total_fee
        self.open_pos += qty
        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((open_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((open_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : open_price,
            'direction' : '多',
            'action'    : '加',
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : -1 * total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        return 0

    def add_short(self, price, qty, i):
        """
        加空仓。当 spos > 0, 
        """
        assert self.spos > 0, 'Failed to Open Short: spos = {}'.format(self.spos)
        open_price = price - self.slippage * self.ticksize
        ex_fee, br_fee, rebate = self.GetFees(open_price, qty, action='open')
        total_fee = ex_fee + br_fee - rebate
        self.short_avg_price = self.short_avg_price + [open_price] * qty
        self.spos += qty
        self.realized += -total_fee
        self.open_pos += qty
        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((open_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((open_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : open_price,
            'direction' : '空',
            'action'    : '加',
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : -1 * total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        return 0

    def minus_long(self, price, qty, i):
        """
        减多仓。 lpos > 0:
        """
        assert self.lpos > 0, 'Failed to Minus Long: lpos = {}'.format(self.lpos)
        close_price = price - self.slippage * self.ticksize
        #print('ML: qty {} yst_pos {} lpos {}'.format(qty, self.yst_pos, self.lpos))
        if self.yst_pos == 0: # That means no pos yst, close today. And do not reduce yst_pos
            ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
            total_fee = ex_fee + br_fee - rebate
            action = '减今'
        elif self.yst_pos > 0: # That means haven pos yst, close yst. Reduce yst_pos
            if self.yst_pos < qty:
                ex_fee1, br_fee1, rebate1 = self.GetFees(close_price, self.yst_pos, action='closeT')
                ex_fee2, br_fee2, rebate2 = self.GetFees(close_price, qty - self.yst_pos, action='closeN')
                ex_fee = ex_fee1 + ex_fee2
                total_fee = (ex_fee1 + br_fee2 - rebate1) + (ex_fee1 + br_fee2 - rebate2)
                action = '减昨今'
                self.yst_pos -= self.yst_pos
            else:
                ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                total_fee = ex_fee + br_fee - rebate
                action = '减昨'
                self.yst_pos -= qty
        else:
            raise TypeError('Case not addressed')

        # Realize PNL -> FIFO
        self.lpos -= qty
        realized = self.GetRealize(self.long_avg_price, close_price, qty, 'long')
        if self.lpos == 0:
            self.long_avg_price = []
            assert len(self.long_avg_price) == self.lpos, 'Queue and Pos length not match. Deque {}, lpos {}'.format(len(self.long_avg_price), self.lpos)
        else:
            self.long_avg_price = self.long_avg_price[qty:]

        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.realized   += (realized - total_fee)
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : close_price,
            'direction' : '多',
            'action'    : action,
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : realized - total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        return 0

    def minus_short(self, price, qty, i):
        """
        减空仓。 spos > 0
        """
        assert self.spos > 0, 'Failed to Minus Short: spos = {}'.format(self.spos)
        close_price = price + self.slippage * self.ticksize
        #print('MS: qty {} yst_pos {} spos {}'.format(qty, self.yst_pos, self.spos))
        if self.yst_pos == 0: # That means no pos yst, close today. And do not reduce yst_pos
            ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
            total_fee = ex_fee + br_fee - rebate
            action = '减今'
        elif self.yst_pos > 0: # That means haven pos yst, close yst. Reduce yst_pos
            if self.yst_pos < qty:
                ex_fee1, br_fee1, rebate1 = self.GetFees(close_price, self.yst_pos, action='closeT')
                ex_fee2, br_fee2, rebate2 = self.GetFees(close_price, qty - self.yst_pos, action='closeN')
                ex_fee = ex_fee1 + ex_fee2
                total_fee = (ex_fee1 + br_fee2 - rebate1) + (ex_fee1 + br_fee2 - rebate2)
                action = '减昨今'
                self.yst_pos -= self.yst_pos
            else:
                ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                total_fee = ex_fee + br_fee - rebate
                action = '减昨'
                self.yst_pos -= qty
        else:
            raise TypeError('Case not addressed')

        self.spos -= qty
        realized = self.GetRealize(self.short_avg_price, close_price, qty, 'short')
        if self.spos == 0:
            self.short_avg_price = []
            assert len(self.short_avg_price) == self.spos, 'Queue and Pos length not match. Deque {}, spos {}'.format(len(self.short_avg_price), self.spos)
        else:
            self.short_avg_price = self.short_avg_price[qty:]

        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.realized += (realized - total_fee)
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : close_price,
            'direction' : '空',
            'action'    : action,
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : realized - total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        return 0

    def close_long(self, price, i):
        """
        平多仓。 lpos > 0. -4
        """
        assert self.lpos > 0, 'Failed to Close Long: lpos = {}'.format(self.lpos)
        close_price = price - self.slippage * self.ticksize
        qty = abs(self.lpos)
        #print('CL: QTY {} YSTPOS {} LPOS {}'.format(qty, self.yst_pos, self.lpos))
        if self.yst_pos == 0: # That means no pos yst, close today. And do not reduce yst_pos
            ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
            total_fee = ex_fee + br_fee - rebate
            action = '平今'
        elif self.yst_pos > 0:
            if self.yst_pos < qty:
                ex_fee1, br_fee1, rebate1 = self.GetFees(close_price, self.yst_pos, action='closeT')
                ex_fee2, br_fee2, rebate2 = self.GetFees(close_price, qty - self.yst_pos, action='closeN')
                ex_fee = ex_fee1 + ex_fee2
                total_fee = (ex_fee1 + br_fee2 - rebate1) + (ex_fee1 + br_fee2 - rebate2)
                action = '平昨今'
                self.yst_pos -= self.yst_pos
            else:
                ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                total_fee = ex_fee + br_fee - rebate
                action = '平昨'
                self.yst_pos -= qty
        else:
            print(qty, self.yst_pos, self.lpos)
            raise TypeError('Case not addressed')

        self.lpos -= qty
        realized = self.GetRealize(self.long_avg_price, close_price, qty, 'long')
        if self.lpos == 0:
            self.long_avg_price = []
            assert len(self.long_avg_price) == self.lpos, 'Queue and Pos length not match. Deque {}, lpos {}'.format(len(self.long_avg_price), self.lpos)
        else:
            self.long_avg_price = self.long_avg_price[qty:]

        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.realized   += (realized - total_fee)
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : close_price,
            'direction' : '多',
            'action'    : action,
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : realized - total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        return 0

    def close_short(self, price, i):
        assert self.spos > 0, 'Failed to Close Short: spos = {}'.format(self.spos)
        close_price = price + self.slippage * self.ticksize
        qty = abs(self.spos)
        #print('CS: QTY {} YSTPOS {} SPOS {}'.format(qty, self.yst_pos, self.spos))
        if self.yst_pos == 0: # That means no pos yst, close today. And do not reduce yst_pos
            ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
            total_fee = ex_fee + br_fee - rebate
            action = '平今'
        elif self.yst_pos > 0:
            if self.yst_pos < qty:
                ex_fee1, br_fee1, rebate1 = self.GetFees(close_price, self.yst_pos, action='closeT')
                ex_fee2, br_fee2, rebate2 = self.GetFees(close_price, qty - self.yst_pos, action='closeN')
                ex_fee = ex_fee1 + ex_fee2
                total_fee = (ex_fee1 + br_fee2 - rebate1) + (ex_fee1 + br_fee2 - rebate2)
                action = '平昨今'
                self.yst_pos -= self.yst_pos
            else:
                ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                total_fee = ex_fee + br_fee - rebate
                action = '平昨'
                self.yst_pos -= qty
        else:
            raise TypeError('Case not addressed')

        self.spos -= qty
        realized = self.GetRealize(self.short_avg_price, close_price, qty, 'short')
        if self.spos == 0:
            self.short_avg_price = []
            assert len(self.short_avg_price) == self.spos, 'Queue and Pos length not match. Deque {}, spos {}'.format(len(self.short_avg_price), self.spos)
        else:
            self.short_avg_price = self.short_avg_price[qty:]

        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.realized   += (realized - total_fee)
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : close_price,
            'direction' : '空',
            'action'    : action,
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : realized - total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        return 0

    def close_all(self, bp1, ap1, i):
        assert self.lpos > 0 or self.spos > 0, 'Failed to Close All: No Position, lpos = {} spos = {}'.format(self.lpos, self.spos)
        if self.lpos > 0:
            close_price = bp1 - self.slippage * self.ticksize
            qty = abs(self.lpos)
            if self.yst_pos == 0: # That means no pos yst, close today. And do not reduce yst_pos
                ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                total_fee = ex_fee + br_fee - rebate
                action = '清今'
            elif self.yst_pos > 0:
                if self.yst_pos < qty:
                    ex_fee1, br_fee1, rebate1 = self.GetFees(close_price, self.yst_pos, action='closeT')
                    ex_fee2, br_fee2, rebate2 = self.GetFees(close_price, qty - self.yst_pos, action='closeN')
                    ex_fee = ex_fee1 + ex_fee2
                    total_fee = (ex_fee1 + br_fee2 - rebate1) + (ex_fee1 + br_fee2 - rebate2)
                    action = '清昨今'
                    self.yst_pos -= self.yst_pos
                else:
                    ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                    total_fee = ex_fee + br_fee - rebate
                    action = '清昨'
                    self.yst_pos -= qty
            else:
                print(qty, self.yst_pos, self.lpos)
                raise TypeError('Case not addressed')

            self.lpos -= qty
            realized = self.GetRealize(self.long_avg_price, close_price, qty, 'long')
            if self.lpos == 0:
                self.long_avg_price = []
                assert len(self.long_avg_price) == self.lpos, 'Queue and Pos length not match. Deque {}, lpos {}'.format(len(self.long_avg_price), self.lpos)
            else:
                self.long_avg_price = self.long_avg_price[qty:]

            lavg_price = self.GetAvgPrice(self.long_avg_price)
            savg_price = self.GetAvgPrice(self.short_avg_price)
            lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
            sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
            self.unrealized = lunrealize + sunrealize
            self.realized   += (realized - total_fee)
            self.reports.append({
                'account_id': self.acc_id,
                'order_id'  : self.order_id,
                'datetime'  : self.index[i],
                'code'      : self.contract,
                'price'     : close_price,
                'direction' : '多',
                'action'    : action,
                'volume'    : qty,
                'value'     : qty * bp1 * self.size,
                'ex_fee'    : ex_fee,
                'total_fee' : total_fee,
                'lpos'      : self.lpos,
                'spos'      : self.spos,
                'total_pos' : self.lpos + self.spos,
                'u_pnl'     : self.unrealized,
                'r_pnl'     : realized - total_fee,
                'total_pnl' : self.unrealized + self.realized,
                'total_rpnl': self.realized,
                })
        if self.spos > 0:
            close_price = ap1 + self.slippage * self.ticksize
            qty = abs(self.spos)
            if self.yst_pos == 0: # That means no pos yst, close today. And do not reduce yst_pos
                ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                total_fee = ex_fee + br_fee - rebate
                action = '清今'
            elif self.yst_pos > 0:
                if self.yst_pos < qty:
                    print('case2')
                    ex_fee1, br_fee1, rebate1 = self.GetFees(close_price, self.yst_pos, action='closeT')
                    ex_fee2, br_fee2, rebate2 = self.GetFees(close_price, qty - self.yst_pos, action='closeN')
                    ex_fee = ex_fee1 + ex_fee2
                    total_fee = (ex_fee1 + br_fee2 - rebate1) + (ex_fee1 + br_fee2 - rebate2)
                    action = '清昨今'
                    self.yst_pos -= self.yst_pos
                else:
                    ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                    total_fee = ex_fee + br_fee - rebate
                    action = '清昨'
                    self.yst_pos -= qty
            else:
                raise TypeError('Case not addressed')

            self.spos -= qty
            realized = self.GetRealize(self.short_avg_price, close_price, qty, 'short')
            if self.spos == 0:
                self.short_avg_price = []
                assert len(self.short_avg_price) == self.spos, 'Queue and Pos length not match. Deque {}, spos {}'.format(len(self.short_avg_price), self.spos)
            else:
                self.short_avg_price = self.short_avg_price[qty:]

            lavg_price = self.GetAvgPrice(self.long_avg_price)
            savg_price = self.GetAvgPrice(self.short_avg_price)
            lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
            sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
            self.unrealized = lunrealize + sunrealize
            self.realized   += (realized - total_fee)
            self.reports.append({
                'account_id': self.acc_id,
                'order_id'  : self.order_id,
                'datetime'  : self.index[i],
                'code'      : self.contract,
                'price'     : close_price,
                'direction' : '空',
                'action'    : action,
                'volume'    : qty,
                'value'     : qty * ap1 * self.size,
                'ex_fee'    : ex_fee,
                'total_fee' : total_fee,
                'lpos'      : self.lpos,
                'spos'      : self.spos,
                'total_pos' : self.lpos + self.spos,
                'u_pnl'     : self.unrealized,
                'r_pnl'     : realized - total_fee,
                'total_pnl' : self.unrealized + self.realized,
                'total_rpnl': self.realized,
                })
        return 0

    def reverse_long(self, price, qty, i):
        """
        反手单子： 
        反手开多， 减n手空单。 加n手多单。 minus short add long
        """
        assert self.spos > 0, 'Failed to Reverse Long: spos = {} lpos = {}'.format(self.spos, self.lpos)
        abs_pos = self.spos + self.lpos
        close_price = open_price = price + self.slippage * self.ticksize
        if self.yst_pos == 0: # That means no pos yst, close today. And do not reduce yst_pos
            ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
            total_fee = ex_fee + br_fee - rebate
            action = '减今'
        elif self.yst_pos > 0: # That means haven pos yst, close yst. Reduce yst_pos
            if self.yst_pos < qty:
                ex_fee1, br_fee1, rebate1 = self.GetFees(close_price, self.yst_pos, action='closeT')
                ex_fee2, br_fee2, rebate2 = self.GetFees(close_price, qty - self.yst_pos, action='closeN')
                ex_fee = ex_fee1 + ex_fee2
                total_fee = (ex_fee1 + br_fee2 - rebate1) + (ex_fee1 + br_fee2 - rebate2)
                action = '减昨今'
                self.yst_pos -= self.yst_pos
            else:
                ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                total_fee = ex_fee + br_fee - rebate
                action = '减昨'
                self.yst_pos -= qty
        else:
            raise TypeError('Case not addressed')
        self.spos -= qty
        realized = self.GetRealize(self.short_avg_price, close_price, qty, 'short')
        if self.spos == 0:
            self.short_avg_price = []
            assert len(self.short_avg_price) == self.spos, 'Queue and Pos length not match. Deque {}, spos {}'.format(len(self.short_avg_price), self.spos)
        else:
            self.short_avg_price = self.short_avg_price[qty:]

        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.realized += (realized - total_fee)
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : close_price,
            'direction' : '空',
            'action'    : action,
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : realized - total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        # Open Long or Add Long
        ex_fee, br_fee, rebate = self.GetFees(open_price, qty, action='open')
        total_fee = ex_fee + br_fee - rebate
        self.long_avg_price = self.long_avg_price + [open_price] * qty
        self.lpos += qty
        self.realized += -total_fee
        self.open_pos += qty
        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : open_price,
            'direction' : '多',
            'action'    : '反开',
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : -1 * total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        assert abs_pos == self.lpos + self.spos, 'Position Not Equal after Reverse Long'
        return 0

    def reverse_short(self, price, qty, i):
        """
        反手单子： 
        反手开空， 减n手多单。 加n手空单。 minus short add long。
        """
        assert self.lpos > 0, 'Failed to Minus Long: lpos = {}'.format(self.lpos)
        abs_pos = self.lpos + self.spos
        close_price = open_price = price - self.slippage * self.ticksize
        if self.yst_pos == 0: # That means no pos yst, close today. And do not reduce yst_pos
            ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
            total_fee = ex_fee + br_fee - rebate
            action = '减今'
        elif self.yst_pos > 0: # That means haven pos yst, close yst. Reduce yst_pos
            if self.yst_pos < qty:
                ex_fee1, br_fee1, rebate1 = self.GetFees(close_price, self.yst_pos, action='closeT')
                ex_fee2, br_fee2, rebate2 = self.GetFees(close_price, qty - self.yst_pos, action='closeN')
                ex_fee = ex_fee1 + ex_fee2
                total_fee = (ex_fee1 + br_fee2 - rebate1) + (ex_fee1 + br_fee2 - rebate2)
                action = '减昨今'
                self.yst_pos -= self.yst_pos
            else:
                ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
                total_fee = ex_fee + br_fee - rebate
                action = '减昨'
                self.yst_pos -= qty
        else:
            raise TypeError('Case not addressed')
        
        self.lpos -= qty
        realized = self.GetRealize(self.long_avg_price, close_price, qty, 'long')
        if self.lpos == 0:
            self.long_avg_price = []
            assert len(self.long_avg_price) == self.lpos, 'Queue and Pos length not match. Deque {}, lpos {}'.format(len(self.long_avg_price), self.lpos)
        else:
            self.long_avg_price = self.long_avg_price[qty:]

        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.realized   += (realized - total_fee)
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : close_price,
            'direction' : '多',
            'action'    : action,
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : realized - total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })

        ex_fee, br_fee, rebate = self.GetFees(open_price, qty, action='open')
        total_fee = ex_fee + br_fee - rebate
        self.short_avg_price = self.short_avg_price + [open_price] * qty
        self.spos += qty
        self.realized += -total_fee
        self.open_pos += qty
        lavg_price = self.GetAvgPrice(self.long_avg_price)
        savg_price = self.GetAvgPrice(self.short_avg_price)
        lunrealize =      round((close_price - lavg_price) * np.abs(self.lpos) * self.size,2) if lavg_price != 0 else 0
        sunrealize = -1 * round((close_price - savg_price) * np.abs(self.spos) * self.size,2) if savg_price != 0 else 0
        self.unrealized = lunrealize + sunrealize
        self.reports.append({
            'account_id': self.acc_id,
            'order_id'  : self.order_id,
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'price'     : open_price,
            'direction' : '空',
            'action'    : '反开',
            'volume'    : qty,
            'value'     : qty * price * self.size,
            'ex_fee'    : ex_fee,
            'total_fee' : total_fee,
            'lpos'      : self.lpos,
            'spos'      : self.spos,
            'total_pos' : self.lpos + self.spos,
            'u_pnl'     : self.unrealized,
            'r_pnl'     : -1 * total_fee,
            'total_pnl' : self.unrealized + self.realized,
            'total_rpnl': self.realized,
            })
        assert abs_pos == self.lpos + self.spos, 'Position Not Equal after Reverse Short'
        return 0

    def do_nothing(self):
        return 0


    def run(self, df, date_str):
        """
        Input DataFrame For Training. Daily 
        """
        # 当terminate True， 交易不进行
        try: 
            assert self.terminate == False
        except AssertionError:
            print('Date {} will not run: Backtest is terminated'.format(date_str))
            return None

        self.index         = df.index
        self.contract      = df['InstrumentID'].iloc[0]
        self.yst_pos       = self.open_pos
        self.open_pos      = 0
        self.ticks         += df.shape[0]
        self.halt          = False

        self.dates.append(date_str)
        # ----- Data Array Set up for Main Logic -----
        bp1   = df['BidPrice1'].values
        bv1   = df['BidVolume1'].values
        ap1   = df['AskPrice1'].values
        av1   = df['AskVolume1'].values
        price = df['MidPrice'].values
        time  = db.GetSecond(df.index)
        sigl  = df['sigl'].values
        sigs  = df['sigs'].values 

        # ----- Value Set Up for this trading Day -----
        upl   = df['UpperLimitPrice'].iloc[0]
        lwl   = df['LowerLimitPrice'].iloc[0]
        lot   = 1
        t     = 0
        assert len(time) == len(bp1) == len(ap1), 'Length not Match'

        # Main Loop
        for i in range(len(time)):
            if t > self.halt_time and (ap1[i] > upl - self.ticksize * self.stoplosstick or bp1[i] < lwl + self.ticksize * self.stoplosstick):
            # 如果过了15分钟还是触发停盘condition， 当天交易终止
                print('{} Stop Trading. Limit Reached after 15 mins'.format(self.index[i]))
                break
            elif t < self.halt_time and self.halt:
            # 计算停盘以后的 downtime 
                t = time[i] - record_time

            elif (self.lpos > 0 or self.spos > 0) and (ap1[i] > upl - (self.ticksize * self.stoplosstick) or bp1[i] < lwl + (self.ticksize * self.stoplosstick)):
            # 接近涨跌停板， 触发交易暂停, 15分钟后恢复交易
                self.close_all(bp1[i], ap1[i], i)
                record_time = time[i]
                self.halt = True
                print('{} Stop Limit: Trading in Halt, Close All'.format(self.index[i]))
                print('AP1 {} UpTrigger {} BP1 {} DNTrigger {}'.format(ap1[i], upl - (self.ticksize * self.stoplosstick),
                                                                       bp1[i], lwl + (self.ticksize * self.stoplosstick)))
            elif (self.lpos > 0 or self.spos > 0) and (sigl[i] == 6 or sigs[i] == 6): 
            # 信号6， 不触发停止交易
                self.close_all(bp1[i], ap1[i], i)
                print('{} Signal 6: Close All'.format(self.index[i]))
            elif (self.lpos > 0 or self.spos > 0) and (self.capital + self.realized + self.unrealized < self.capital * self.freeze_rate): 
            # 总本金少于保险线， 出发停止交易，交易永远终止
                self.close_all(bp1[i], ap1[i], i)
                self.terminate = True 
                print('{} Under Margin: Close all, End Trading'.format(self.index[i]))
                break
            else:
                self.halt = False
                if (sigl[i] > 0 or sigs[i] < 0):
                    # Check Position Available
                    max_available_pos = self.GetMaxPos(price[i]) # Use MidPrice to Estimate MaxPos
                    abs_pos = abs(self.lpos) + abs(self.spos)
                    self.order_id += 1
                    # Long Position Logic
                    if self.lpos == 0 and abs_pos < max_available_pos and av1[i] > 0: # 没有多仓 + 绝对仓位少于最大开仓数
                        if sigl[i] == 1: # 开多仓
                            self.open_long(ap1[i], self.lot, i)

                    elif self.lpos > 0 and abs_pos < max_available_pos and av1[i] > 0: # 已有多仓位 + 绝对仓位少于最大开仓数
                        if sigl[i] == 1: # 开多仓/加多仓
                            self.open_long(ap1[i], self.lot, i)
                        elif sigl[i] == 3: # 减多仓
                            self.minus_long(bp1[i], self.lot, i)
                        elif sigl[i] == 4: # 平多仓
                            self.close_long(bp1[i], i)
                        elif sigl[i] == 5: # 反手开空
                            self.reverse_short(ap1[i], self.lot, i)
                        else:
                            self.do_nothing()

                    elif self.lpos > 0 and abs_pos >= max_available_pos and av1[i] > 0: # 已有多仓为 + 绝对仓位 >= 最大开仓数
                        if sigl[i] == 3: # 减多仓
                            self.minus_long(bp1[i], self.lot, i)
                        elif sigl[i] == 4: # 平多仓
                            self.close_long(bp1[i], i)
                        elif sigl[i] == 5: # 反手开空
                            self.reverse_short(ap1[i], self.lot, i)
                        else:
                            self.do_nothing()
                    else:
                        self.do_nothing()

                    # Short Position Logic
                    if self.spos == 0 and abs_pos < max_available_pos and bv1[i] > 0: # 没有空仓 + 绝对仓位少于最大开仓数
                        if sigs[i] == -1: # 开多仓
                            self.open_short(ap1[i], self.lot, i)

                    elif self.spos > 0 and abs_pos < max_available_pos and bv1[i] > 0: # 已有空仓位 + 绝对仓位少于最大开仓数
                        if sigs[i] == -1: # 加空仓
                            self.open_short(ap1[i], self.lot, i)    
                        elif sigs[i] == -3: # 减空仓
                            self.minus_short(ap1[i], self.lot, i)
                        elif sigs[i] == -4: # 平空仓
                            self.close_short(ap1[i], i)
                        elif sigs[i] == -5: # 反手开多
                            self.reverse_long(ap1[i], self.lot, i)
                        else:
                            self.do_nothing()

                    elif self.spos > 0 and abs_pos >= max_available_pos and bv1[i] > 0: # 已有空仓为 + 绝对仓位 >= 最大开仓数
                        if sigs[i] == -3: # 减空仓
                            self.minus_short(ap1[i], self.lot, i)
                        elif sigs[i] == -4: # 平空仓
                            self.close_short(ap1[i], i)
                        elif sigs[i] == -5: # 反手开多
                            self.reverse_long(ap1[i], self.lot, i)
                        else:
                            self.do_nothing()
                    else:
                        self.do_nothing()
                #print(self.index[i], sigl[i], sigs[i], self.long_avg_price, self.short_avg_price)          
                else:
                    self.do_nothing()

        
        return None

    
    def result(self):
        """
        ----- 结算表 -----
        """
        res = pd.DataFrame(self.reports)
        res['total_pnl'] = res['total_pnl'] + self.capital
        res['total_rpnl'] = res['total_rpnl'] + self.capital
        return res
    
    def account(self):
        """
        ----- 账号设定 -----
        """

        par = pd.DataFrame({
            'Account ID': self.acc_id,
            'Instrument': self.instrument,
            'Period': '{} - {}'.format(self.dates[0], self.dates[-1]),
            'Total Days': len(self.dates),
            'Freq': self.freq,
            'Exchange Rebate': self.ex_rebate,
            'Broker Rebate': self.br_rebate,
            'slippage': '{} ticks'.format(self.slippage)
        }, index=['Value'])
        return par

    def stats(self):
        """
        ----- 交易统计 -----
        交易次数。
        开仓次数。 多仓，空仓。
        减仓次数。 多仓，空仓。
        平仓次数。 多仓，空仓。
        清仓次数。 多仓，空仓。
        `
        """
        res = pd.DataFrame(self.reports)
        res['total_pnl'] = res['total_pnl'] + self.capital
        res['total_rpnl'] = res['total_rpnl'] + self.capital
        stats = pd.DataFrame({
            '开多': len(res[(res['direction']== '多') & (res['action'].str.contains('开'))]),
            '开空': len(res[(res['direction']== '空') & (res['action'].str.contains('开'))]),
            '减多': len(res[(res['direction']== '多') & (res['action'].str.contains('减'))]),
            '减空': len(res[(res['direction']== '空') & (res['action'].str.contains('减'))]),
            '反开': len(res[(res['direction']== '多') & (res['action'].str.contains('反'))]),
            '反空': len(res[(res['direction']== '空') & (res['action'].str.contains('反'))]),
            '平开': len(res[(res['direction']== '多') & (res['action'].str.contains('平'))]),
            '平空': len(res[(res['direction']== '空') & (res['action'].str.contains('平'))]),
            '全平(双边)': len(res[(res['action'].str.contains('清'))]),
        }, index=['Value'])
        return stats

    

    def metric(self):
        """
        Stats to Record
        ----- 账户明细 -----
        Initial Capital: Unrealize PnL, Realized PnL. (Plot)
        Tick Modelled. Bar Modelled.
        """

        res = pd.DataFrame(self.reports)
        res['total_pnl'] = res['total_pnl'] + self.capital
        res['total_rpnl'] = res['total_rpnl'] + self.capital
        metric = pd.DataFrame({
                'Ticks Modelled': int(self.ticks),
                'Initial Capital': self.capital,
                'Final Capital': res['total_rpnl'].iloc[-1],
                'Realized PnL': res['r_pnl'].sum(),
                'Return': round((res['total_rpnl'].iloc[-1] / self.capital  - 1) * 100,1) ,
                'MaxDrawdown': mt.GetDrawdown(res, ratio=False),
                'MaxDrawdown Ratio': mt.GetDrawdown(res, ratio=True),
                'Win Rate': mt.GetWinRate(res),
                'Win Rate (Long)': mt.GetWinRate(res, side='long'),
                'Win Rate (Short)': mt.GetWinRate(res, side='short'),
                'PnL Ratio': mt.GetPnLRatio(res),
                'PnL Ratio (Long)': mt.GetPnLRatio(res, side='long'),
                'PnL Ratio (Short)': mt.GetPnLRatio(res, side='short'),
                'EPO': mt.GetEPO(res),
                'EPO (Long)': mt.GetEPO(res, 'long'),
                'EPO (Short)': mt.GetEPO(res, 'short'),
            }, index=['Value'])
        return metric

    def plot(self):
        res = pd.DataFrame(self.reports)
        res['total_pnl'] = res['total_pnl'] + self.capital
        res['total_rpnl'] = res['total_rpnl'] + self.capital
        res.set_index('datetime', inplace=True)
        fig = plt.figure(figsize=(10, 4))
        plt.plot(res['total_pnl'], '-', color='blue', label='Unrealize PnL')
        plt.plot(res['total_rpnl'], '-', color='red', label='Realize PnL')
        plt.axhline(y=self.capital, color='black', linestyle='-')
        plt.xticks(rotation=30)
        plt.title('CTP Based Backtest Report')
        plt.legend()
        plt.show()
        return 0
