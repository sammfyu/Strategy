import pandas as pd
import numpy as np
from numba import njit


def tupling(label, sign):
    res = []
    start = None
    end = None
    for i in range(len(label) + 1):
        try:
            if start == None:
                if label[i] == sign:
                    start = i
            elif start != None:
                if label[i] == sign:
                    continue
                elif label[i] != sign:
                    end = i - 1
                    res.append((start, end))
                    start = None
                    end = None
        except IndexError:
            if label[i-1] == sign:
                end = i
                res.append((start, end))
    return res





def GetOHLC(df, second):
    df['volume'] = df['Volume'].diff().fillna(df['Volume'].iloc[0])
    # Day
    d = df[(df.index.hour < 16) & (df.index.hour > 8)]
    od = d['MidPrice'].resample(second).ohlc()
    od['volume'] = d['volume'].resample(second).sum()
    od.index = od.index.shift(1)
    
    # Night
    n = df[(df.index.hour > 20) | (df.index.hour < 3)]
    if len(n) != 0:
        on = n['MidPrice'].resample(second).ohlc()
        on['volume'] = n['volume'].resample(second).sum()
        on.index = on.index.shift(1)
        ohlc = pd.concat([on, od], axis=0)
    else:
        ohlc = od
    ohlc.dropna(inplace=True)
    return ohlc



@njit 
def SignalFilter(array):
    """
    Assume signal has been ASOF merged: only NaN and int values left
    This function makes sure value does not repeat
    """
    res = [np.nan]
    for i in range(1, len(array)):
        if not np.isnan(array[i]) and np.isnan(array[i-1]):
            res.append(array[i])
        elif array[i] == array[i-1] and not np.isnan(array[i]):
            res.append(np.nan)
        else:
            res.append(np.nan)
    return res

