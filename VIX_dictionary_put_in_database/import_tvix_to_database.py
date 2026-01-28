"""
將 tvix JSON 檔案匯入資料庫
格式 A：date (YYYYMMDD TEXT), time (HH:MM:SS TEXT), vix (REAL)
使用 INSERT OR IGNORE 避免重複寫入（基於 date + time 組合）
"""

import sqlite3
import json
import os
from pathlib import Path

# 資料庫路徑（與 database_manager.py 一致）
DB_PATH = r"D:\all_data\taiwan_stock_all_data.db"
TABLE_NAME = "vix_tvix_data"

def init_table(conn):
    """建立資料表（如果不存在）"""
    cursor = conn.cursor()
    
    # 建立資料表：date (YYYYMMDD) + time (HH:MM:SS) 作為複合主鍵
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            vix REAL,
            PRIMARY KEY (date, time)
        )
    ''')
    
    # 建立索引
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_date ON {TABLE_NAME} (date)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_time ON {TABLE_NAME} (time)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_vix ON {TABLE_NAME} (vix)")
    
    conn.commit()
    print(f"[Info] 資料表 {TABLE_NAME} 初始化完成")

def import_json_to_db(json_path, db_path=DB_PATH):
    """
    將 JSON 檔案匯入資料庫
    
    參數:
    - json_path: JSON 檔案路徑
    - db_path: 資料庫路徑
    """
    json_file = Path(json_path)
    if not json_file.exists():
        raise FileNotFoundError(f"JSON 檔案不存在: {json_path}")
    
    # 確保資料庫目錄存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 連接資料庫
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 初始化資料表
        init_table(conn)
        
        # 讀取 JSON
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"[Info] 讀取到 {len(data)} 筆資料")
        
        # 統計資訊
        inserted_count = 0
        skipped_count = 0
        
        # 匯入資料（使用 INSERT OR IGNORE 避免重複）
        for item in data:
            date = item.get('date')  # YYYYMMDD
            time = item.get('time')  # HH:MM:SS
            vix = item.get('vix')   # REAL 或 None
            
            if not date or not time:
                skipped_count += 1
                continue
            
            try:
                cursor.execute(
                    f"INSERT OR IGNORE INTO {TABLE_NAME} (date, time, vix) VALUES (?, ?, ?)",
                    (date, time, vix)
                )
                if cursor.rowcount > 0:
                    inserted_count += 1
                else:
                    skipped_count += 1
            except sqlite3.Error as e:
                print(f"[Warning] 插入失敗: date={date}, time={time}, error={e}")
                skipped_count += 1
        
        # 提交交易
        conn.commit()
        
        print(f"[Info] 匯入完成：新增 {inserted_count} 筆，跳過 {skipped_count} 筆（重複或無效）")
        
        # 顯示前 3 筆資料
        cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY date DESC, time DESC LIMIT 3")
        samples = cursor.fetchall()
        print(f"\n[Info] 資料表前 3 筆（最新）:")
        for row in samples:
            print(f"  date={row[0]}, time={row[1]}, vix={row[2]}")
        
    except Exception as e:
        conn.rollback()
        print(f"[Error] 匯入失敗: {e}")
        raise
    finally:
        conn.close()
        print("[Info] 資料庫連線已關閉")

if __name__ == "__main__":
    import sys
    
    # 預設使用 tvix_20251001.json
    default_json = r"D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata\tvix_20251001.json"
    
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_path = default_json
    
    print(f"[Info] 開始匯入: {json_path}")
    import_json_to_db(json_path)
    print("[Info] 完成")
