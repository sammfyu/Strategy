import pandas as pd
import numpy as np

def GetWinRate(res, side=None):
    """
    Calculate Win Rate Wrapper.
    Calcualte From Settlement Report
    Side = All / Long /Short
    """
    if side == 'long':
        xt = (res[(res['action'].str.contains('减') | res['action'].str.contains('平')) & (res['direction'].str.contains('多'))]['r_pnl'] > 0).value_counts()
    elif side == 'short':
        xt = (res[(res['action'].str.contains('减') | res['action'].str.contains('平')) & (res['direction'].str.contains('空'))]['r_pnl'] > 0).value_counts()
    else:
        xt = (res[(res['action'].str.contains('减') | res['action'].str.contains('平'))]['r_pnl'] > 0).value_counts()

    if xt.shape[0] == 2:
        win_rate = round(xt.loc[True] / (xt.loc[True] + xt.loc[False]),2)
    elif xt.shape[0] == 1:
        if xt.index[0] == True:
            win_rate = 1.0
        else:
            win_rate = 0.0
    else:
        raise ValueError('Case not justify')
    return win_rate

def GetPnLRatio(res, side=None):
    if side == 'long':
        xt = res[(res['action'].str.contains('减') | res['action'].str.contains('平')) & (res['direction'].str.contains('多'))][['r_pnl']]
    elif side == 'short':
        xt = res[(res['action'].str.contains('减') | res['action'].str.contains('平')) & (res['direction'].str.contains('空'))][['r_pnl']]
    else:
        xt = res[(res['action'].str.contains('减') | res['action'].str.contains('平'))][['r_pnl']]
    xt['tag'] = np.where(xt['r_pnl'] > 0, True, False)
    xt = xt.groupby('tag').sum()
    if xt.shape[0] == 2:
        pnl_ratio = round(abs(xt.loc[True].values[0]) / abs(xt.loc[False].values[0]) ,2)
    elif xt.shape[0] == 1:
        if xt.index[0] == True:
            pnl_ratio = np.inf
        else:
            pnl_ratio = -np.inf
    else:
        raise ValueError('Case not justify')
    return pnl_ratio


def GetEPO(res, side=None):
    if side == 'long':
        x = res[(res['action'].str.contains('减') | res['action'].str.contains('平')) & (res['direction'].str.contains('多'))][['r_pnl']]
    elif side == 'short':
        x = res[(res['action'].str.contains('减') | res['action'].str.contains('平')) & (res['direction'].str.contains('空'))][['r_pnl']]
    else:
        x = res[(res['action'].str.contains('减') | res['action'].str.contains('平'))][['r_pnl']]
    if x.shape[0] > 0:
        epo = round(x.mean().values[0],2)
    elif x.shape[0] == 0:
        epo = np.nan
    else:
        ValueError('Case Not Justify')
    return epo

def GetCounts(res):
    counts = pd.DataFrame({
        '开多': len(res[(res['direction']== '多') & (res['action'].str.contains('开'))]),
        '开空': len(res[(res['direction']== '空') & (res['action'].str.contains('开'))]),
        '减多': len(res[(res['direction']== '多') & (res['action'].str.contains('减'))]),
        '减空': len(res[(res['direction']== '空') & (res['action'].str.contains('减'))]),
        '反开': len(res[(res['direction']== '多') & (res['action'].str.contains('反'))]),
        '反空': len(res[(res['direction']== '空') & (res['action'].str.contains('反'))]),
        '平开': len(res[(res['direction']== '多') & (res['action'].str.contains('平'))]),
        '平空': len(res[(res['direction']== '空') & (res['action'].str.contains('平'))]),
        '全平': len(res[(res['action'].str.contains('全'))]),
    }, index=['Actions'])
    return counts

def GetAccount(res, ticks, capital):
    acc = pd.DataFrame({
        'Ticks Modelled': int(ticks),
        'Initial Capital': capital,
        'Final Capital': res['total_rpnl'].iloc[-1],
        'Realized PnL': res['r_pnl'].sum(),
        'Return': round((res['total_rpnl'].iloc[-1] / capital  - 1) * 100,1) ,
        'MaxDrawdown': GetDrawdown(res, ratio=False),
        'MaxDrawdown Ratio': GetDrawdown(res, ratio=True),
        'Win Rate': GetWinRate(res),
        'Win Rate (Long)': GetWinRate(res, side='long'),
        'Win Rate (Short)': GetWinRate(res, side='short'),
        'PnL Ratio': GetPnLRatio(res),
        'PnL Ratio (Long)': GetPnLRatio(res, side='long'),
        'PnL Ratio (Short)': GetPnLRatio(res, side='short'),
        'EPO': GetEPO(res),
        'EPO (Long)': GetEPO(res, 'long'),
        'EPO (Short)': GetEPO(res, 'short'),
    }, index=['Stats'])
    return acc


def GetDrawdown(res, ratio=False):
    array = res['total_rpnl'].values
    max_ = np.max(array)
    idx = np.argmax(array)
    array = array[idx:]
    min_ = np.min(array)
    if ratio == False:
        res = max_ - min_
    else:
        res = (max_ - min_) / max_
    return round(res,2)