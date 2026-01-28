'''
取出TFE_VIX_data資料表內的資料，計算每個月的K線，並存入資料庫中

首先從資料庫中取出TFE_VIX_data資料表內的資料
計算每個月的K線
存入資料庫中
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
from pathlib import Path

#連接資料庫，取得TFE_VIX_data資料表內的資料
db_path = r"D:\all_data\taiwan_stock_all_data.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
#取出TFE_VIX_data資料表內的資料
cursor.execute(f"SELECT * FROM TFE_VIX_data")
data = cursor.fetchall()
#print(data)

'''
計算每個月的K線，得出開始時間(time)、結束時間(tradeDate)、開盤價(open)、最高價(high)、最低價(low)、收盤價(close)
每個月的K線存入mouth_k_line中
mouth_k_line的格式為：
[
    [開始時間, 結束時間, 開盤價, 最高價, 最低價, 收盤價],
    [開始時間, 結束時間, 開盤價, 最高價, 最低價, 收盤價],
    ...
]
'''

#計算每個月的K線，首先透過date取得資料的紀錄日期(date)，將同一個月的資料存入同一個mouth_k_line中
#如果有多個月份就建立多個mouth_k_line

# 初始化：從第一筆資料取得年月作為起始月份
if not data:
    print("[Warning] 資料表為空，無法計算K線")
    mouth_k_line = []
else:
    # 從第一筆資料的 date (YYYYMMDD) 提取年月 (YYYYMM)
    first_date = data[0][0]  # 假設 date 是第一個欄位
    current_year_month = first_date[:6] if len(first_date) >= 6 else None  # 取前6碼 YYYYMM
    
    # 重新初始化 mouth_k_line
    mouth_k_line = []
    mouth_k_line.append([])
    mouth_k_line[0].append(data[0])
    
    # 從第二筆開始處理（第一筆已經加入）
    for row in data[1:]:
        row_date = row[0]  # 取得該筆資料的 date
        row_year_month = row_date[:6] if len(row_date) >= 6 else None  # 提取年月 YYYYMM
        
        # 如果年月改變，建立新的月份分組
        if row_year_month != current_year_month:
            current_year_month = row_year_month
            mouth_k_line.append([])
        
        # 將資料加入當前月份的分組
        mouth_k_line[len(mouth_k_line)-1].append(row)

#共有幾個月的Kline須計算，並印出資料數量
if mouth_k_line:
    print(f"共有{len(mouth_k_line)}個月的Kline須計算")
    for i, month_data in enumerate(mouth_k_line):
        print(f"  第{i+1}個月：資料數量為{len(month_data)}筆")
else:
    print("沒有資料可計算K線")

'''
#印出計算出來的mouth_k_line（可選：如果資料量很大，建議只印前幾筆或摘要）
if mouth_k_line:
    print(f"\n[Debug] 前3個月的資料筆數：")
    for i in range(min(3, len(mouth_k_line))):
        print(f"  月份 {i+1}: {len(mouth_k_line[i])} 筆")
    # 完整資料可取消註解以下行來查看
    # print(mouth_k_line)

'''

#計算每個月的K線，得出開始時間(time)、結束時間(tradeDate)、開盤價(open)、最高價(high)、最低價(low)、收盤價(close)
# 建立新的列表來儲存計算結果（每個月的K線）
monthly_k_lines = []

for month_data in mouth_k_line:
    if not month_data:  # 跳過空資料
        continue
    
    # 取得該月第一筆資料（開盤）
    first_row = month_data[0]
    first_date = first_row[0]      # 該月第一個交易日的 date (YYYYMMDD)
    time = first_date[:6] + "01"   # 開始時間：該月第一天 (YYYYMM01)
    open_price = first_row[2]      # 開盤價：該月第一筆的 vix
    
    # 取得該月最後一筆資料（收盤）
    last_row = month_data[-1]
    tradeDate = last_row[0]         # 結束時間：該月最後一個交易日的 date (YYYYMMDD)
    close_price = last_row[2]      # 收盤價：該月最後一筆的 vix
    
    # 計算該月的最高價和最低價（遍歷該月所有資料的 vix）
    vix_values = [row[2] for row in month_data if row[2] is not None]  # 過濾掉 None 值
    
    if not vix_values:  # 如果該月沒有有效的 vix 資料
        print(f"[Warning] 月份 {first_row[0][:6]} 沒有有效的 vix 資料，跳過")
        continue
    
    high_price = max(vix_values)   # 最高價：該月所有 vix 的最大值
    low_price = min(vix_values)    # 最低價：該月所有 vix 的最小值
    
    # 將計算結果加入列表：[開始時間, 結束時間, 開盤價, 最高價, 最低價, 收盤價]
    monthly_k_lines.append([time, tradeDate, open_price, high_price, low_price, close_price])

#印出計算出來的monthly_k_lines
print(f"\n[Info] 共計算出 {len(monthly_k_lines)} 個月的K線：")
print("-" * 80)
print(f"{'月份':<12} {'開始時間':<12} {'結束日期':<12} {'開盤':<10} {'最高':<10} {'最低':<10} {'收盤':<10}")
print("-" * 80)

for i, k_line in enumerate(monthly_k_lines):
    time, tradeDate, open_price, high_price, low_price, close_price = k_line
    month_label = tradeDate[:6] if len(tradeDate) >= 6 else "未知"  # 從結束日期提取年月
    print(f"{month_label:<12} {time:<12} {tradeDate:<12} {open_price:<10.2f} {high_price:<10.2f} {low_price:<10.2f} {close_price:<10.2f}")

# 如果需要看完整資料（取消註解以下行）
# print("\n[Debug] 完整 monthly_k_lines 資料：")
# for i, k_line in enumerate(monthly_k_lines):
#     print(f"  第{i+1}個月: {k_line}")

#儲存至資料庫中VIX_data資料表中
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='VIX_data'")
if not cursor.fetchone():
    print("無資料")
else:
    for k_line in monthly_k_lines:
        time, tradeDate, open_price, high_price, low_price, close_price = k_line
        cursor.execute(
            "INSERT OR IGNORE INTO VIX_data (time, tradeDate, open, high, low, close) VALUES (?, ?, ?, ?, ?, ?)",
            (time, tradeDate, open_price, high_price, low_price, close_price)
        )
    conn.commit()
    print("資料儲存完成")

#關閉資料庫連線
conn.close()
print("資料庫連線已關閉")