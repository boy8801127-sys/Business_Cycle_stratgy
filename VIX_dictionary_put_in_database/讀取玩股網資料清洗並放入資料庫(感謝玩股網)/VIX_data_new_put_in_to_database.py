'''
此程式將VIX_data_new.json內的資料放入資料庫中
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


#連接資料庫，並建立資料表，如果資料表不存在，則建立資料表
# 直接使用正確的絕對路徑，並確保目錄存在
db_path = r"D:\all_data\taiwan_stock_all_data.db"
os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute(f"CREATE TABLE IF NOT EXISTS VIX_data (time TEXT, tradeDate TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, millionAmount REAL)")
#建立資料表索引
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_VIX_data_time ON VIX_data (time)")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_VIX_data_tradeDate ON VIX_data (tradeDate)")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_VIX_data_open ON VIX_data (open)")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_VIX_data_high ON VIX_data (high)")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_VIX_data_low ON VIX_data (low)")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_VIX_data_close ON VIX_data (close)")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_VIX_data_volume ON VIX_data (volume)")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_VIX_data_millionAmount ON VIX_data (millionAmount)")

#印出VIX_data資料表的子欄位
cursor.execute(f"PRAGMA table_info(VIX_data)")
sub_columns = cursor.fetchall()
print(sub_columns)

#將VIX_data_new.json內的資料放入資料庫中
with open('VIX_data_new.json', 'r') as file:
    data = json.load(file)
    for item in data:
        cursor.execute(f"INSERT INTO VIX_data (time, tradeDate, open, high, low, close, volume, millionAmount) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (item['time'], item['tradeDate'], item['open'], item['high'], item['low'], item['close'], item['volume'], item['millionAmount']))

#提交交易
conn.commit()

#印出前三筆資料
cursor.execute(f"SELECT * FROM VIX_data LIMIT 3")
data = cursor.fetchall()
print(data)

#如果成功放入資料，關閉資料庫連線，並印出成功訊息
if cursor.rowcount > 0:
    print("VIX_data資料表放入資料庫成功")
    conn.close()
    print("資料庫連線已關閉")
else:
    print("VIX_data資料表放入資料庫失敗")
    conn.close()
    print("資料庫連線已關閉")