'''
此程式用於將VIX指數資料標準化
資料來源為VIX_data.txt
範例:
    {
        "time": 1343750400000,
        "tradeDate": 1346342400000,
        "open": 19.38000,
        "high": 19.38000,
        "low": 16.44000,
        "close": 18.35000,
        "volume": 0,
        "millionAmount": 0.00
    },
細項依照每個大括號內的資料填寫
time為時間戳記
tradeDate為交易日期，為時間戳記
open為開盤價
high為最高價
low為最低價
close為收盤價
volume為成交量
millionAmount為成交金額
'''

#匯入相關套件

import sqlite3
import json
import os
import time
import datetime
import pytz
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

#解析VIX_data.txt
with open('VIX_data.txt', 'r') as file:
    data = file.read()
#將data轉換為json格式
data = json.loads(data)

#印出前三項
#print(data[:3])

#換算json內的time和tradeDate為台灣時間，印出第一筆與最後一筆的資料時間
time_tz = pytz.timezone('Asia/Taipei')

# 將毫秒級時間戳轉換為秒級（除以1000）
print(f"第一筆資料 - time: {time_tz.localize(datetime.datetime.fromtimestamp(data[0]['time'] / 1000.0)).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"第一筆資料 - tradeDate: {time_tz.localize(datetime.datetime.fromtimestamp(data[0]['tradeDate'] / 1000.0)).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"最後一筆資料 - time: {time_tz.localize(datetime.datetime.fromtimestamp(data[-1]['time'] / 1000.0)).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"最後一筆資料 - tradeDate: {time_tz.localize(datetime.datetime.fromtimestamp(data[-1]['tradeDate'] / 1000.0)).strftime('%Y-%m-%d %H:%M:%S')}")

#將data內的time和tradeDate換算為台灣時間，並存成新的json格式
new_data = []
for item in data:
    new_data.append({
        'time': time_tz.localize(datetime.datetime.fromtimestamp(item['time'] / 1000.0)).strftime('%Y-%m-%d %H:%M:%S'),
        'tradeDate': time_tz.localize(datetime.datetime.fromtimestamp(item['tradeDate'] / 1000.0)).strftime('%Y-%m-%d %H:%M:%S'),
        'open': item['open'],
        'high': item['high'],
        'low': item['low'],
        'close': item['close'],
        'volume': item['volume'],
        'millionAmount': item['millionAmount']
    })

#將new_data存成新的json格式
# 修正目錄問題，並確保目錄存在，避免儲存時出錯
output_dir = 'VIX_dictionary_put_in_database'
output_path = os.path.join(output_dir, 'VIX_data_new.json')
os.makedirs(output_dir, exist_ok=True)  # 確保資料夾存在

with open(output_path, 'w', encoding='utf-8') as file:
    json.dump(new_data, file, indent=4, ensure_ascii=False)

#印出new_data的前三項
print(new_data[:3])