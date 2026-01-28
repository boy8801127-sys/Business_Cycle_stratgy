'''
此程式將D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata\json內的資料放入資料庫中
細項依照每個大括號內的資料填寫
date為日期
time為時間
vix為VIX指數
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

#連接資料庫，並建立資料表，如果資料表不存在，則建立資料表
# 直接使用正確的絕對路徑，並確保目錄存在
db_path = r"D:\all_data\taiwan_stock_all_data.db"
os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
#建立一個新的資料表，命名為TFE_VIX_data，並建立date, time, vix的欄位
cursor.execute(f"CREATE TABLE IF NOT EXISTS TFE_VIX_data (date TEXT, time TEXT, vix REAL)")
#建立資料表索引
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_TFE_VIX_data_date ON TFE_VIX_data (date)")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_TFE_VIX_data_time ON TFE_VIX_data (time)")
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_TFE_VIX_data_vix ON TFE_VIX_data (vix)")
#建立資料表索引
cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_VIX_data_time ON VIX_data (time)")


#將D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata\json內的資料全部放入資料庫中
json_folder = Path(r'D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata\json')

if not json_folder.exists():
    raise FileNotFoundError(f"資料夾不存在: {json_folder}")

# 統計資訊
total_files = 0
total_inserted = 0
total_skipped = 0

# 批次處理所有 JSON 檔案
json_files = sorted(json_folder.glob('*.json'))
print(f"[Info] 找到 {len(json_files)} 個 JSON 檔案")

for json_file in json_files:
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        file_inserted = 0
        file_skipped = 0
        
        for item in data:
            date = item.get('date')
            time = item.get('time')
            vix = item.get('vix')
            
            if not date or not time:
                file_skipped += 1
                continue
            
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO TFE_VIX_data (date, time, vix) VALUES (?, ?, ?)",
                    (date, time, vix)
                )
                if cursor.rowcount > 0:
                    file_inserted += 1
                else:
                    file_skipped += 1
            except sqlite3.Error as e:
                print(f"[Warning] 插入失敗: {json_file.name} date={date}, time={time}, error={e}")
                file_skipped += 1
        
        total_files += 1
        total_inserted += file_inserted
        total_skipped += file_skipped
        
        if total_files % 10 == 0:  # 每處理 10 個檔案就提交一次
            conn.commit()
            print(f"[Info] 已處理 {total_files} 個檔案，新增 {total_inserted} 筆，跳過 {total_skipped} 筆")
    
    except json.JSONDecodeError as e:
        print(f"[Error] JSON 解析失敗: {json_file.name}, error={e}")
    except Exception as e:
        print(f"[Error] 處理檔案失敗: {json_file.name}, error={e}")

print(f"[Info] 批次處理完成：共處理 {total_files} 個檔案，新增 {total_inserted} 筆，跳過 {total_skipped} 筆")

#提交交易
conn.commit()
#印出前三筆資料
cursor.execute(f"SELECT * FROM TFE_VIX_data LIMIT 3")
data = cursor.fetchall()
print(data)

#如果成功放入資料，關閉資料庫連線，並印出成功訊息
if cursor.rowcount > 0:
    print("TFE_VIX_data資料表放入資料庫成功")
    conn.close()
    print("資料庫連線已關閉")
else:
    print("TFE_VIX_data資料表放入資料庫失敗")
    conn.close()
    print("資料庫連線已關閉")
