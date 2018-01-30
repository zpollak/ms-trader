#!/usr/bin/env python

from __future__ import print_function
from binance.client import Client
import myapi
import datetime
import numpy as np
import pandas as pd
import talib as ta
import matplotlib.pyplot as plt

# Functions (these should be in another module)
def time_test(mycode):
    """
    Quick execution time test to help select optimal code snippets.
    Args: mycode = string of code you want to time
    """
    import timeit
    start_time = timeit.default_timer()
    exec(mycode)
    
    return timeit.default_timer() - start_time


def milliseconds_to_datetime(milli_str):
    '''
    Transforms milliseconds into datetime. Should probably be UTC...
    
    Args: milli_str = milliseconds as a string
    '''
    return datetime.datetime.fromtimestamp(milli_str/1000.0)


def milliseconds_to_date(milli_str):
    '''
    Transforms milliseconds into date. No need for UTC here because the
    date will be identical.
    
    Args:
        milli_str = milliseconds as a string
        day_or_min = 'day' for kline_days, 'min' for kline_mins
    '''
    return datetime.date.fromtimestamp(milli_str/1000.0)


def kline_to_pd(kline_list):
    '''
    Transform OHLC data returned from Client.get_klines() into a pandas
    DataFrame object so we can calculate statistics and build models.
    
    Args: kline_list = nested list object returned by Client.get_klines()
    '''
    # Prepend headers to data
    header = [
                'OpenTime', 
                'Open', 
                'High',
                'Low',
                'Close',
                'Volume',
                'CloseTime',
                'QuoteAssetVolume',
                'NumTrades',
                'TakerBuyBaseVolume',
                'TakerBuyQuoteVolume',
                'IGNORE'
              ]
    data = [header] + kline_list
    # Transform to DataFrame
    df = pd.DataFrame(data[1:], columns=data[0])
    # Remove the 'IGNORE' column
    del df['IGNORE']
    
    return df


# Initialize client
client = Client(myapi.key, myapi.secret)
# Ping the server
client.ping()
# Server time
client.get_server_time()

# Set your ticker
tick = 'XLMBTC'

# Historical OHLCV data
# You can sub '30m', '1h', '1d', etc. in place of Client.KLINE_INTERVAL_
tick_15m = client.get_historical_klines(tick, Client.KLINE_INTERVAL_15MINUTE, "1 Jan, 2017")

# Initialize DataFrame
df = pd.DataFrame()

# Extract times from klines list and transform to datetime
df['dates'] = [elem[6] for elem in tick_15m]
df['dates'] = map(milliseconds_to_datetime, df['dates'])

# Extract close price from klines list
df['close'] = [elem[4] for elem in tick_15m]
df['close'] = map(float, df['close'])

# Let's plot price over time
plt.figure(0)
plt.plot(df.dates, df.close, '-', label='Close')
plt.legend()

# Calculate 15-min returns
df['simple_ret'] = df.close.pct_change()
df['log_ret'] = np.log(df.close).diff()
# Went with np.log(x).diff() because it's most efficient
#df['log_ret'] = np.log(1 + df.close.pct_change())
#df['log_ret'] = np.log(df.close) - np.log(df.close.shift(1))

# Calculate SMA(5), SMA(7), SMA(10), SMA(20), SMA(50)
df['sma5'] = ta.SMA(df.close.values, 5)
df['sma7'] = ta.SMA(df.close.values, 7)
df['sma10'] = ta.SMA(df.close.values, 10)
df['sma14'] = ta.SMA(df.close.values, 14)
df['sma20'] = ta.SMA(df.close.values, 20)
df['sma50'] = ta.SMA(df.close.values, 50)

# Calculate RSI(14)
df['rsi'] = ta.RSI(df.close.values, 14)

# Clean-up data
df = df.dropna()



'''
I THINK rules_engine() COULD SHIFT TO OOP OR AT LEAST BETTER FUNCTION.
CURRENTLY ALLOWS FOR SHORTING AND DOESN'T MONITOR ACCOUNT BALANCE. ACCOUNT
BALANCE IS NEGLIBLE AT THE MOMENT BECAUSE WE'RE THROWING THE ENTIRE STACK TOWARDS
COIN BEING TESTED.

To remove the ability to short, we just need a 'current_pos' variable.
'current_pos' needs to be equal to the last position we took. So it starts at 0,
if we buy then it moves to 1 and stays 1 until we sell. Basically, 'signal' can only
be -1 if 'current_pos' is 1. If 'current_pos' = 0 or -1, we cannot sell.
I'm having trouble figuring out how to implement this without loop...
'''
def rules_engine(df):
    """
    Just a simple rules engine to generate your signal vector.
    Args: df = pandas DataFrame of pricing data and TA indicators
    """
    
    '''STRATEGY RULES GO BELOW HERE'''
    # If SMA(5) crosses SMA(10) from below & RSI < 80, then buy
    # If SMA(5) crosses SMA(10) from above & RSI > 20, then sell
    df['signal'] = np.where((df.sma5 > df.sma10) & (df.sma5.shift(1) < df.sma10.shift(1)), 1, 
                              np.where((df.sma5 < df.sma10) & df.sma5.shift(1) > df.sma10.shift(1), -1, 0))
    '''STRATEGY RULES GO ABOVE HERE'''
    
    
    # Lag the signal 1 row because we're setting our position for the next 15m period
    df['signal'] = df.signal.shift(1)
    df = df.dropna()
    
    return df



# Generate signals
df = rules_engine(df)

# Calculate returns
df['strat_ret'] = df.signal * df.log_ret
df['cum_log_ret'] = df.strat_ret.cumsum()
df['cum_simple_ret'] = np.exp(df.cum_log_ret) - 1
# Print cum returns
print('Cumulative Log Return = ' + str(df.cum_log_ret[-1:].values * 100).strip('[]') + '%')
print('Cumulative Simple Return = ' + str(df.cum_simple_ret[-1:].values * 100).strip('[]') + '%')


'''
TRANSITION FROM matplotlib TO plotly.
'''
# Plot equity curve
plt.figure(1)
plt.plot(df.dates, df.cum_log_ret, label='Cum. Log Ret')
plt.plot(df.dates, df.cum_simple_ret, label='Cum. Simple Ret')
plt.legend()


#import plotly.plotly as pt
#import plotly.graph_objs as go
#trace0 = go.Scatter(
#        x = df.dates,
#        y = df.cum_log_ret,
#        name = 'Cum. Log Return'
#)
#trace1 = go.Scatter(
#        x = df.dates,
#        y = df.cum_simple_ret,
#        name = 'Cum. Simple Return'
#)
#pt_data = [trace0, trace1]
#pt.iplot(pt_data, filename='line-mode')
#
