import pandas as pd
import numpy as np
import cufflinks as cf
#import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.offline import init_notebook_mode
init_notebook_mode(connected=True)
cf.go_offline()

def GetBreaks(df, freq):
    dt_all = pd.date_range(start=df.index[0], end=df.index[-1], freq=freq)
    dt_obs = [d.strftime('%Y-%m-%d %H:%M:%S') for d in pd.to_datetime(df.index)]
    dt_breaks = [d for d in dt_all.strftime('%Y-%m-%d %H:%M:%S').tolist() if not d in dt_obs]
    return dt_breaks


def GetVisual(df, freq):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.01, row_heights=[0.2,0.6,0.2])
    
    # PnL Plot
    df[['total_pnl', 'total_rpnl']] = df[['total_pnl', 'total_rpnl']].fillna(method='ffill')
    fig.add_trace(go.Scatter(
        x=df.index, y=df['total_pnl'], line=dict(color='Purple', width=2), name='Unrealized PnL', hoverinfo='none'), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['total_rpnl'], line=dict(color='Pink', width=2), name='Realized PnL', hoverinfo='none'), row=1, col=1)
    fig.add_hline(y=df['total_pnl'].iloc[0], row=1, col=1)
    fig.update_yaxes(title_text="PnL", row=1, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    
    # Main Plot
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], showlegend=False,
        increasing=dict(fillcolor='#ff0000', line=dict(color='#000000', width=0.3)),
        decreasing=dict(fillcolor='#00ff44', line=dict(color='#000000', width=0.3)),
        #hoverinfo='none',
        opacity=0.7,
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['BBL_14_2.0'], opacity=0.3, line=dict(color='blue', width=2), name='BBL_14'), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['BBM_14_2.0'], opacity=0.3, line=dict(color='grey', width=2), name='BBM_14'), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['BBU_14_2.0'], opacity=0.3, line=dict(color='red', width=2), name='BBU_14'), row=2, col=1)
    open_long = np.where((df['direction'] == '多') & (df['action'] == '开'), df['close'], np.nan)
    fig.add_trace(go.Scatter(
        x=df.index, y=open_long, opacity=1, mode='markers', marker=dict(
        color='#cf1717', size=25, line=dict(color='grey', width=2), symbol='triangle-up',
        ),name='开多'), row=2, col=1)
    open_short = np.where((df['direction'] == '空') & (df['action'] == '开'), df['close'], np.nan)
    fig.add_trace(go.Scatter(
        x=df.index, y=open_short, opacity=1, mode='markers', marker=dict(
        color='#21b521', size=25, line=dict(color='grey', width=2), symbol='triangle-down',
        ),name='开空'), row=2, col=1)
    minus_long = np.where((df['direction'] == '多') & (df['action'].str.contains('减')), df['close']-8, np.nan)
    fig.add_trace(go.Scatter(
        x=df.index, y=minus_long, opacity=1, mode='markers', marker=dict(
        color='#cf1717', size=20, line=dict(color='grey', width=2), symbol='x',
        ),name='减多'), row=2, col=1)
    minus_short = np.where((df['direction'] == '空') & (df['action'].str.contains('减')), df['close']-8, np.nan)
    fig.add_trace(go.Scatter(
        x=df.index, y=minus_short , opacity=1, mode='markers', marker=dict(
        color='#21b521', size=20, line=dict(color='grey', width=2), symbol='x',
        ),name='减空'), row=2, col=1)
    reverse_long = np.where((df['direction'] == '多') & (df['action'].str.contains('反')), df['close'], np.nan)
    fig.add_trace(go.Scatter(
        x=df.index, y=reverse_long, opacity=1, mode='markers', marker=dict(
        color='orange', size=20, line=dict(color='grey', width=2), symbol='diamond',
        ),name='反开'), row=2, col=1)
    reverse_short = np.where((df['direction'] == '空') & (df['action'].str.contains('反')), df['close'], np.nan)
    fig.add_trace(go.Scatter(
        x=df.index, y=reverse_short , opacity=1, mode='markers', marker=dict(
        color='lime', size=20, line=dict(color='grey', width=2), symbol='diamond',
        ),name='反空'), row=2, col=1)
    fig.update_yaxes(title_text="Price / BBANDS", type='log', row=2, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=2, col=1)
    
    # Volume Plot
# colors = ['red' if row['open'] - row['close'] >= 0 else 'green' for index, row in df.iterrows()]
# fig.add_trace(go.Bar(
#     x=df.index, y=df['volume'], marker_color=colors, name='Volume'), row=3, col=1)
# fig.update_yaxes(title_text="Volume", row=3, col=1)
# fig.update_xaxes(rangeslider_visible=False, row=3, col=1)
    
    # RSI Plot
    fig.add_trace(go.Scatter(
        x=df.index, y=df['RSI_6'], opacity=0.5, line=dict(color='#2f2ff5', width=2), name='RSI_6'), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['RSI_14'], opacity=0.9, line=dict(color='#2fb3f5', width=2), name='RSI_14'), row=3, col=1)
    fig.add_hline(y=80, row=3, col=1)
    fig.add_hline(y=20, row=3, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1)
    fig.update_xaxes(
        title_text='Date', 
        rangeslider_visible=False,
        #xaxis=dict(type='category', linewidth=2),
        rangebreaks=[dict(values=GetBreaks(df, freq), dvalue=900000)],
        row=3,col=1
    )
    fig.update_layout(
        title='CTP Based Backtest Report',
        #xaxis=dict(type='category', linewidth=2), 
        autosize=False, width=1000, height=1000,
        yaxis=dict(autorange=True, fixedrange=False),
        showlegend=True,
    )
    #to_hide = []
    #fig.for_each_trace(lambda trace: trace.update(visible='legendonly') if trace.name in to_hide else ())
    return fig










'''
%matplotlib notebook
import pandas as pd
import numpy as np
import mplfinance as mpf
print(mpf.__version__)

start_date = '20210109'
end_date = '20210201'
instrument = 'EG'
freq = '15min'

f = pd.read_csv(f'./feature/{instrument}_feature_{freq}.csv', index_col=0, parse_dates=True)
f = f[(f.TradeDate >= int(start_date)) & (f.TradeDate <= int(end_date))]
f[['lower', 'mid', 'upper', 'rsi']] = f[['BBL_14_2.0', 'BBM_14_2.0', 'BBU_14_2.0', 'RSI_6']]
f['sig'] = np.where((f.close <= f.lower) & (f.rsi >= 20) & (f.rsi <= 50), -1,
           np.where((f.close >= f.upper) & (f.rsi >= 50) & (f.rsi <= 80),  1, 
           np.where((f.close >  f.upper) & (f.rsi >  80)                , -5,
           np.where((f.close <  f.lower) & (f.rsi <  20)                ,  5,
           np.where((f.close <  f.mid  ) & (f.last_close >  f.mid)      ,  3,
           np.where((f.close >  f.mid  ) & (f.last_close <  f.mid)      ,  -3,
           0))))))

buy  = np.where(f['sig'] == 1 , f['close'], np.nan)
sell = np.where(f['sig'] == -1 , f['close'], np.nan)
sell2buy = np.where(f['sig'] == 5, f['close'], np.nan)
buy2sell = np.where(f['sig'] == -5, f['close'], np.nan)


apds = [
    mpf.make_addplot(f[['lower', 'mid', 'upper']]),
    mpf.make_addplot(f[['rsi']], panel=2, ylabel='RSI 6', ylim=[0,100]),
    mpf.make_addplot(buy , type='scatter', markersize=200, marker='^', color='#fc3d03'),
    mpf.make_addplot(sell, type='scatter', markersize=200, marker='v', color='#52b35c'),
    mpf.make_addplot(sell2buy , type='scatter', markersize=200, marker='^', color='#f803fc'),
    mpf.make_addplot(buy2sell, type='scatter', markersize=200, marker='v', color='#03fc73'),
]
mc = mpf.make_marketcolors(up='red',down='green', volume='in')
s  = mpf.make_mpf_style(marketcolors=mc, base_mpl_style='seaborn',)

mpf.plot(f, warn_too_much_data=100000, addplot=apds, figscale=1.2, type='candle', style=s, volume=True, title=f'Date: {start_date} - {end_date} Contract: {instrument} Freq: {freq}')
'''