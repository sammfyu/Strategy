import glob
import pandas as pd
import numpy as np

def GetTickSize(instrument: str) -> float:
    ticksizes = {
        'C' : 1, 
        'CS': 1, 
        'A' : 1, 
        'B' : 1, 
        'M' : 1,
        'Y' : 2, 
        'P' : 2, 
        'FB': 0.5,
        'BB': 0.05,
        'JD': 1,
        'RR': 1, 
        'LH': 5,
        'L' : 5,
        'V' : 5,
        'PP': 1,
        'J' : 0.5,
        'JM': 0.5,
        'I' : 0.5,
        'EG': 1,
        'EB': 1,
        'PG': 1,
    }
    return ticksizes[instrument]


def GetContractSize(instrument: str) -> float:
    multipliers = {
        'C' : 10, 
        'CS': 10, 
        'A' : 10, 
        'B' : 10, 
        'M' : 10,
        'Y' : 10,
        'P' : 10, 
        'FB': 10,
        'BB': 500,
        'JD': 10,
        'RR': 10,
        'LH': 16,
        'L' : 5,
        'V' : 5,
        'PP': 5,
        'J' : 100,
        'JM': 60,
        'I' : 100,
        'EG': 10,
        'EB': 5,
        'PG': 20,
    }
    return multipliers[instrument]

def GetMargin(instrument: str) -> float:
    """
    只记录投机用的保证金率
    """
    margins = {
        'C' : 0.12,
        'CS': 0.09,
        'A' : 0.12,
        'B' : 0.09,
        'M' : 0.10,
        'Y' : 0.09,
        'P' : 0.12,
        'FB': 0.10,
        'BB': 0.40,
        'JD': 0.09,
        'RR': 0.06,
        'LH': 0.15,
        'L' : 0.11,
        'V' : 0.11,
        'PP': 0.11,
        'J' : 0.20,
        'JM': 0.20,
        'I' : 0.13,
        'EG': 0.12,
        'EB': 0.12,
        'PG': 0.13,
    }
    return margins[instrument]


def GetExchangeRebate():
    ex_rebate = 0.0
    return ex_rebate

def GetBrokerRebate():
    br_rebate = 0.0
    return br_rebate

def GetFees(instrument: str, oc='open'):
    """
    Most Contract has different open,close tdy (closeT), close normal(closeN)
    """
    # If value > 1, then it is as flat fee. Otherwise it's percentage.
    fees = {
        'C' : {'open': 1.2, 'closeT': 1.2, 'closeN': 1.2}, 
        'CS': {'open': 1.5, 'closeT': 1.5, 'closeN': 1.5}, 
        'A' : {'open': 2.0, 'closeT': 4.0, 'closeN': 2.0},
        'B' : {'open': 1.0, 'closeT': 2.0, 'closeN': 1.0}, 
        'M' : {'open': 1.5, 'closeT': 2.0, 'closeN': 1.5}, 
        'Y' : {'open': 2.5, 'closeT': 7.5, 'closeN': 2.5}, 
        'P' : {'open': 2.5, 'closeT': 10.0,'closeN': 2.5},  
        'FB': {'open': 1e-4, 'closeT': 1e-4, 'closeN': 1e-4}, 
        'BB': {'open': 1e-4, 'closeT': 1e-4, 'closeN': 1e-4}, 
        'JD': {'open': 1.5e-4, 'closeT': 1.5e-4, 'closeN': 1.5e-4}, 
        'RR': {'open': 1.0, 'closeT': 1.0, 'closeN': 1.0},
        'LH': {'open': 2e-4, 'closeT': 4e-4, 'closeN': 2e-4}, 
        'L' : {'open': 1.0, 'closeT': 1.0, 'closeN': 1.0},
        'V' : {'open': 1.0, 'closeT': 1.0, 'closeN': 1.0},
        'PP': {'open': 1.0, 'closeT': 1.0, 'closeN': 1.0},
        'J' : {'open': 1e-4, 'closeT': 4e-4, 'closeN': 1e-4}, 
        'JM': {'open': 1e-4, 'closeT': 4e-4, 'closeN': 1e-4},
        'I' : {'open': 2e-4, 'closeT': 4e-4, 'closeN': 2e-4},
        'EG': {'open': 3.0, 'closeT': 3.0, 'closeN': 3.0},
        'EB': {'open': 3.0, 'closeT': 3.0, 'closeN': 3.0},
        'PG': {'open': 6.0, 'closeT': 12.0, 'closeN': 6.0},
    }
    return fees[instrument][oc]


def GetTradeDates(instrument):
    return sorted(list(set([x.split('/')[-1][:-4] for x in glob.glob('./data/{}/*.csv'.format(instrument))])))


def GetSecond(index):
    # Fuck timestamp I did not convert to datetime when cleaning
    #ex_time = pd.to_datetime(index).astype(int).values # Fuck timestamp I did not convert to datetime when cleaning
    ex_time = index.astype(int).values
    time = (ex_time - ex_time[0]) / 1_000_000_000
    if np.max(np.diff(time) >= 208800): # Weekend Night to Day Session, total of 208800 seconds
        idx = np.argmax(np.diff(time)) + 1
        time[idx:] = time[idx:] - np.round(np.max(np.diff(time)))
    if np.max(np.diff(time) >= 21600): # Night to Day Session (Normal Day), slice, 6 hours(from 3am to 9am)
        idx = np.argmax(np.diff(time)) + 1
        time[idx:] = time[idx:] - np.round(np.max(np.diff(time)))
    if np.max(np.diff(time) >= 7200): # 2 hours break 
        idx = np.argmax(np.diff(time)) + 1
        time[idx:] = time[idx:] - np.round(np.max(np.diff(time)))
    if np.max(np.diff(time) >= 900): # 15 minutes morning break
        idx = np.argmax(np.diff(time)) + 1
        time[idx:] = time[idx:] - np.round(np.max(np.diff(time)))
    assert np.all(np.diff(time) <= 60), 'Timestamp has Over 1 minute Gap'
    return time