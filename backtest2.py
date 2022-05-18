import numpy as np
import pandas as pd
import database as db
from math import floor
from collections import deque


class backtest(object):
    def __init__(self,                  
                 instrument,
                 slippage=0, # In measure of ticks
                 acc_id='001',
                 capital=100000,
                 broker_rate=0,
                 ex_rebate=0, # Percentage
                 br_rebate=0,
                ):

        # Bacaktest Param
        self.open_fee       = db.GetFees(instrument, 'open')
        self.close_tdy_fee  = db.GetFees(instrument, 'closeT')
        self.close_yst_fee  = db.GetFees(instrument, 'closeN')
        self.ticksize       = db.GetTickSize(instrument)
        self.size           = db.GetContractSize(instrument)
        self.margin         = db.GetMargin(instrument)
        self.slippage       = slippage
        self.acc_id         = acc_id
        self.capital        = capital
        self.broker_rate    = broker_rate
        self.ex_rebate      = ex_rebate
        self.br_rebate      = br_rebate

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
        close_price = bp1 - self.slippage * self.ticksize
        qty = abs(self.lpos)
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

        close_price = ap1 + self.slippage * self.ticksize
        qty = abs(self.spos)
        if self.yst_pos == 0: # That means no pos yst, close today. And do not reduce yst_pos
            ex_fee, br_fee, rebate = self.GetFees(close_price, qty, action='closeN')
            total_fee = ex_fee + br_fee - rebate
            action = '平今'
        elif self.yst_pos > 0:
            if self.yst_pos < qty:
                print('case2')
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


    def run(self, df):
        """
        Input DataFrame For Training. Daily 
        """
        self.index         = df.index
        self.contract      = df['InstrumentID'].iloc[0]
        self.yst_pos       = self.open_pos
        self.open_pos      = 0
        self.ticks         += df.shape[0]
        # ----- Data Array Set up for Main Logic -----
        bp1   = df['BidPrice1'].values
        ap1   = df['AskPrice1'].values
        price = df['MidPrice'].values
        time  = db.GetSecond(df.index)
        sigl  = df['sigl'].values
        sigs  = df['sigs'].values 
        
        lot   = 1
        assert len(time) == len(bp1) == len(ap1), 'Length not Match'
        
        for i in range(len(time)):
            if (sigl[i] > 0 or sigs[i] < 0):
                # Check Position Available
                max_available_pos = self.GetMaxPos(price[i]) # Use MidPrice to Estimate MaxPos
                abs_pos = abs(self.lpos) + abs(self.spos)
                self.order_id += 1
                # Long Position Logic
                if self.lpos == 0 and abs_pos < max_available_pos: # 没有多仓 + 绝对仓位少于最大开仓数
                    if sigl[i] == 1: # 开多仓
                        self.open_long(ap1[i], lot, i)

                elif self.lpos > 0 and abs_pos < max_available_pos: # 已有多仓位 + 绝对仓位少于最大开仓数
                    if sigl[i] == 1: # 开多仓/加多仓
                        self.open_long(ap1[i], lot, i)
                    elif sigl[i] == 3: # 减多仓
                        self.minus_long(bp1[i], lot, i)
                    elif sigl[i] == 4: # 平多仓
                        self.close_long(bp1[i], i)
                    elif sigl[i] == 5: # 反手开空
                        self.reverse_short(ap1[i], lot, i)
                    else:
                        self.do_nothing()

                elif self.lpos > 0 and abs_pos >= max_available_pos: # 已有多仓为 + 绝对仓位 >= 最大开仓数
                    if sigl[i] == 3: # 减多仓
                        self.minus_long(bp1[i], lot, i)
                    elif sigl[i] == 4: # 平多仓
                        self.close_long(bp1[i], i)
                    elif sigl[i] == 5: # 反手开空
                        self.reverse_short(ap1[i], lot, i)
                    else:
                        self.do_nothing()
                else:
                    self.do_nothing()

                # Short Position Logic
                if self.spos == 0 and abs_pos < max_available_pos: # 没有空仓 + 绝对仓位少于最大开仓数
                    if sigs[i] == -1: # 开多仓
                        self.open_short(ap1[i], lot, i)

                elif self.spos > 0 and abs_pos < max_available_pos: # 已有空仓位 + 绝对仓位少于最大开仓数
                    if sigs[i] == -1: # 加空仓
                        self.open_short(ap1[i], lot, i)    
                    elif sigs[i] == -3: # 减空仓
                        self.minus_short(ap1[i], lot, i)
                    elif sigs[i] == -4: # 平空仓
                        self.close_short(ap1[i], i)
                    elif sigs[i] == -5: # 反手开多
                        self.reverse_long(ap1[i], lot, i)
                    else:
                        self.do_nothing()

                elif self.spos > 0 and abs_pos >= max_available_pos: # 已有空仓为 + 绝对仓位 >= 最大开仓数
                    if sigs[i] == -3: # 减空仓
                        self.minus_short(ap1[i], lot, i)
                    elif sigs[i] == -4: # 平空仓
                        self.close_short(ap1[i], i)
                    elif sigs[i] == -5: # 反手开多
                        self.reverse_long(ap1[i], lot, i)
                    else:
                        self.do_nothing()
                else:
                    self.do_nothing()

                # 平仓机制
                if (self.lpos > 0 or self.spos > 0) and (sigl[i] == 6 or sigs[i] == 6):
                    self.close_all(bp1[i], ap1[i], i)
                else:
                    self.do_nothing()
                
                
                #print(self.index[i], sigl[i], sigs[i], self.long_avg_price, self.short_avg_price)          
            else:
                self.do_nothing()


    def result(self):
        res = pd.DataFrame(self.reports)
        res['total_pnl'] = res['total_pnl'] + self.capital
        res['total_rpnl'] = res['total_rpnl'] + self.capital
        return res
    



    def stats(self):
        """
        Stats to Record
        ----- 账户明细 -----
        Initial Capital: Unrealize PnL, Realized PnL. (Plot)
        Tick Modelled. Bar Modelled.


        ----- 交易统计 -----
        交易次数。
        开仓次数。 多仓，空仓。
        减仓次数。 多仓，空仓。
        平仓次数。 多仓，空仓。
        清仓次数。 多仓，空仓。
        胜率， 多仓胜率，空仓胜率。
        盈亏比率， 多仓盈亏比，空仓盈亏比。
        EPO， 多仓epo， 空仓epo。
        最大回撤。 (多/空)
        
        """
        return 0
    