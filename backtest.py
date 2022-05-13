import numpy as np
import pandas as pd
import database as db

class backtest(object):
    def __init__(self,                  
                 instrument,
                 fees=0,
                 slippage=0, # In measure of ticks
                 max_pos=10, 
                 rebate=0, # Percentage
                ):

        # Used Param
        self.open_fee      = db.GetFees(instrument, 'open')
        self.close_fee     = db.GetFees(instrument, 'close')
        self.ticksize      = db.GetTickSize(instrument)
        self.contract_size = db.GetContractSize(instrument)
        self.slippage      = slippage
        self.max_pos       = max_pos
        self.rebate        = rebate
        self.fees          = fees
        self.reports       = []
        self.pos           = 0
        self.realized      = 0
        
        self.long_avg_price     = []
        self.short_avg_price    = []
        
        
    # ----- Buttons -----
    # Open Q Lots at Price P
    def open_long(self, price, qty, i):
        assert abs(self.pos) < self.max_pos, 'Failed Open Long: Position Exceeded Limit'
        open_price = price + self.slippage * self.ticksize 
        if self.open_fee < 1:
            cost = (1 - self.rebate) * self.fees * open_price * qty * self.contract_size * self.open_fee
        else:
            cost = (1 - self.rebate) * self.fees * self.open_fee * qty
        self.long_avg_price.append((open_price, qty))
        self.pos += qty
        self.realized += -cost
        avg_price  = np.sum([p * q for (p, q) in self.long_avg_price]) / np.sum([q for (_, q) in self.long_avg_price])
        unrealized = round((open_price - avg_price) * np.abs(self.pos) * self.contract_size,2)
        self.reports.append({
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'direction' : '多',
            'offset'    : '开',
            'price'     : open_price,
            'volume'    : qty,
            'cost'      : cost,
            'position'  : self.pos,
            'u_pnl'     : unrealized,
            'r_pnl'     : -cost,
            'total_pnl' : unrealized + self.realized,
        })
        

    # Close Q Lots at Price P
    def close_long(self, price, qty, i):
        assert self.pos > 0, 'Failed Close Long: Position is not Positive'
        close_price = price - self.slippage * self.ticksize 
        if self.close_fee < 1:
            cost = (1 - self.rebate) * self.fees * close_price * qty * self.contract_size * self.close_fee
        else:
            cost = (1 - self.rebate) * self.fees * self.close_fee * qty
        self.pos -= qty
        avg_price  = np.sum([p * q for (p, q) in self.long_avg_price]) / np.sum([q for (_, q) in self.long_avg_price])
        realized = round((close_price - avg_price) * qty * self.contract_size,2)
        self.realized   += (realized - cost)
        unrealized = round((close_price - avg_price) * np.abs(self.pos) * self.contract_size,2)
        self.reports.append({
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'direction' : '多',
            'offset'    : '平今',
            'price'     : close_price,
            'volume'    : qty,
            'cost'      : cost,
            'position'  : self.pos,
            'u_pnl'     : unrealized, 
            'r_pnl'     : realized - cost,
            'total_pnl' : unrealized + self.realized, 
        })
        if self.pos == 0:
            self.long_avg_price = []
        else:
            self.long_avg_price.append((close_price, -1 * qty))
        return 0
        
    def open_short(self, price, qty, i):
        assert abs(self.pos) < self.max_pos, 'Failed Open Short: Position Exceeded Limit'
        open_price = price - self.slippage * self.ticksize # Can only Sell in cheaper Price
        if self.open_fee < 1:
            cost = (1 - self.rebate) * self.fees * open_price * qty * self.contract_size * self.open_fee
        else:
            cost = (1 - self.rebate) * self.fees * self.open_fee * qty

        self.short_avg_price.append((open_price, qty))
        self.pos -= qty
        self.realized += -cost
        avg_price  = round(np.sum([p * q for (p, q) in self.short_avg_price]) / np.sum([q for (_, q) in self.short_avg_price]), 2)
        unrealized = round(-1 * (open_price - avg_price) * qty * self.contract_size, 2)
        self.reports.append({
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'direction' : '空',
            'offset'    : '开',
            'price'     : open_price,
            'volume'    : qty,
            'cost'      : cost,
            'position'  : self.pos,
            'u_pnl'     : unrealized, 
            'r_pnl'     : -cost,
            'total_pnl' : unrealized + self.realized, 
        })
        return 0

    def close_short(self, price, qty, i):
        assert self.pos < 0, 'Failed Close Short: Position is not Negative'
        close_price = price + self.slippage * self.ticksize # Can Only Buy in more expensive Price
        if self.close_fee < 1:
            cost = (1 - self.rebate) * self.fees * close_price * qty * self.contract_size * self.close_fee
        else:
            cost = (1 - self.rebate) * self.fees * self.close_fee * qty

        self.pos += qty
        avg_price  = np.sum([p * q for (p, q) in self.short_avg_price]) / np.sum([q for (_, q) in self.short_avg_price])
        realized = round(-1 * (close_price - avg_price) * qty * self.contract_size,2)
        self.realized   += (realized - cost)
        unrealized = round(-1 * (close_price - avg_price) * np.abs(self.pos) * self.contract_size,2)
        self.reports.append({
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'direction' : '空',
            'offset'    : '平今',
            'price'     : close_price,
            'volume'    : qty,
            'cost'      : cost,
            'position'  : self.pos,
            'u_pnl'     : unrealized, 
            'r_pnl'     : realized - cost,
            'total_pnl' : unrealized + self.realized,
        })
        if self.pos == 0:
            self.short_avg_price = []
        else:
            self.short_avg_price.append((close_price, -1 * qty))
        return 0

    def close_short_open_long(self, price, qty, i):
        # Count as 2 settlements
        assert self.pos < 0, 'Failed Close Short Open Long'
        close_price = open_price = price + self.slippage * self.ticksize
        if self.close_fee < 1:
            cost = (1 - self.rebate) * self.fees * open_price * self.contract_size * np.abs(self.pos) * self.close_fee
        else: 
            cost = (1 - self.rebate) * self.fees * self.close_fee * np.abs(self.pos)
        pos = abs(self.pos)
        self.pos += abs(self.pos)
        avg_price = np.sum([p * q for (p, q) in self.short_avg_price]) / np.sum([q for (_, q) in self.short_avg_price])
        realized = round(-1 * (close_price - avg_price) * pos * self.contract_size,2)
        self.realized   += (realized - cost)
        unrealized = round(-1 * (close_price - avg_price) * np.abs(self.pos) * self.contract_size,2)
        self.reports.append({
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'direction' : '空',
            'offset'    : '全平今',
            'price'     : close_price,
            'volume'    : pos,
            'cost'      : cost,
            'position'  : self.pos,
            'u_pnl'     : unrealized, 
            'r_pnl'     : realized - cost,
            'total_pnl' : unrealized + self.realized,
        })
        if self.pos == 0:
            self.short_avg_price = []
        else:
            self.short_avg_price.append((close_price, -1 * qty))
    
        if self.open_fee < 1:
            cost = (1 - self.rebate) * self.fees * open_price * qty * self.contract_size * self.open_fee
        else:
            cost = (1 - self.rebate) * self.fees * self.open_fee * qty
        self.long_avg_price.append((open_price, qty))
        self.pos += qty
        self.realized += -cost
        avg_price  = np.sum([p * q for (p, q) in self.long_avg_price]) / np.sum([q for (_, q) in self.long_avg_price])
        unrealized = round((open_price - avg_price) * np.abs(self.pos) * self.contract_size,2)
        self.reports.append({
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'direction' : '多',
            'offset'    : '反开',
            'price'     : open_price,
            'volume'    : qty,
            'cost'      : cost,
            'position'  : self.pos,
            'u_pnl'     : unrealized,
            'r_pnl'     : -cost,
            'total_pnl' : unrealized + self.realized,
        })
        return 0


    def close_long_open_short(self, price, qty, i):
        assert self.pos > 0, 'Failed Close Long Open Short'
        close_price = open_price = price - self.slippage * self.ticksize
        if self.close_fee < 1:
            cost = (1 - self.rebate) * self.fees * open_price * self.contract_size * np.abs(self.pos) * self.close_fee
        else: 
            cost = (1 - self.rebate) * self.fees * self.close_fee * np.abs(self.pos)
        pos = abs(self.pos)
        self.pos -= abs(self.pos)
        avg_price  = np.sum([p * q for (p, q) in self.long_avg_price]) / np.sum([q for (_, q) in self.long_avg_price])
        realized = round((close_price - avg_price) * pos * self.contract_size,2)
        self.realized   += (realized - cost)
        unrealized = round((close_price - avg_price) * np.abs(self.pos) * self.contract_size,2)
        self.reports.append({
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'direction' : '多',
            'offset'    : '全平今',
            'price'     : close_price,
            'volume'    : pos,
            'cost'      : cost,
            'position'  : self.pos,
            'u_pnl'     : unrealized, 
            'r_pnl'     : realized - cost,
            'total_pnl' : unrealized + self.realized,
        })
        if self.pos == 0:
            self.long_avg_price = []
        else:
            self.long_avg_price.append((close_price, -1 * qty))
    
        if self.open_fee < 1:
            cost = (1 - self.rebate) * self.fees * open_price * qty * self.contract_size * self.open_fee
        else:
            cost = (1 - self.rebate) * self.fees * self.open_fee * qty

        self.short_avg_price.append((open_price, qty))
        self.pos -= qty
        self.realized += -cost
        avg_price  = np.sum([p * q for (p, q) in self.short_avg_price]) / np.sum([q for (_, q) in self.short_avg_price])
        unrealized = round(-1 * (open_price - avg_price) * qty * self.contract_size, 2)
        self.reports.append({
            'datetime'  : self.index[i],
            'code'      : self.contract,
            'direction' : '空',
            'offset'    : '反开',
            'price'     : open_price,
            'volume'    : qty,
            'cost'      : cost,
            'position'  : self.pos,
            'u_pnl'     : unrealized,
            'r_pnl'     : -cost,
            'total_pnl' : unrealized + self.realized,
        })
        return 0

    def do_nothing(self):
        return 0

    def run(self, df):
        """
        Input DataFrame For Training
        """
        self.index         = df.index
        self.contract      = df['InstrumentID'].iloc[0]
        # ----- Data Array Set up for Main Logic -----
        bp1   = df['BidPrice1'].values
        ap1   = df['AskPrice1'].values
        price = df['MidPrice'].values
        time  = db.GetSecond(df.index)
        sig   = df['sig'].values
        lot   = 1
        assert len(time) == len(bp1) == len(ap1), 'Length not Match'
        
        for i in range(len(time)):
            if time[i] < time[-1]:
                if self.pos == 0:
                    if sig[i] == 2 or sig[i] == 1:
                        self.open_long(ap1[i], lot, i)
                    elif sig[i] == -2 or sig[i] == -1:
                        self.open_short(bp1[i], lot, i)
                    else:
                        self.do_nothing()
                elif self.pos > 0:
                    if (sig[i] == 1 or sig[i] == 2) and np.abs(self.pos) < self.max_pos:
                        self.open_long(ap1[i], lot, i)
                    elif sig[i] == -1:
                        self.close_long(bp1[i], lot, i)
                    elif sig[i] == -2:
                        self.close_long_open_short(bp1[i], lot, i)
                    else:
                        self.do_nothing()
                elif self.pos < 0:
                    if (sig[i] == -1 or sig[i] == -2) and np.abs(self.pos) < self.max_pos:
                        self.open_short(bp1[i], lot, i)
                    elif sig[i] == 1:
                        self.close_short(ap1[i], lot, i)
                    elif sig[i] == 2:
                        self.close_short_open_long(ap1[i], lot, i)
                    else:
                        self.do_nothing()
                else:
                    self.do_nothing()                    
            else:
                self.do_nothing()

    def result(self):
        return pd.DataFrame(self.reports)
    
    def pnl(self):
        return 