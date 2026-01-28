'''
統一 VIX_data 資料表中的日期格式
將 time 和 tradeDate 欄位統一轉換為 YYYYMMDD 格式（例如：20260128）
支援格式：
- YYYYMMDD (例如: 20260128)
- YYYY-MM-DD HH:MM:SS (例如: 2025-10-31 00:00:00)
- YYYY-MM-DD (例如: 2025-10-31)
'''

import sqlite3

# 連接資料庫
db_path = r"D:\all_data\taiwan_stock_all_data.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def normalize_date(date_str):
    """
    將日期統一轉換為 YYYYMMDD 格式
    """
    if not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    # 如果已經是 YYYYMMDD 格式（8位數字）
    if len(date_str) == 8 and date_str.isdigit():
        return date_str
    
    # 如果是 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD 格式
    if '-' in date_str:
        # 提取日期部分（YYYY-MM-DD）
        date_part = date_str.split()[0] if ' ' in date_str else date_str
        # 移除連字號，轉換為 YYYYMMDD
        return date_part.replace('-', '')
    
    return date_str

# 檢查資料表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='VIX_data'")
if not cursor.fetchone():
    print("VIX_data 資料表不存在")
    conn.close()
    exit()

# 讀取所有資料
cursor.execute("SELECT * FROM VIX_data")
rows = cursor.fetchall()

if not rows:
    print("VIX_data 資料表為空")
    conn.close()
    exit()

# 取得欄位名稱
cursor.execute("PRAGMA table_info(VIX_data)")
columns = [col[1] for col in cursor.fetchall()]

# 找出 time 和 tradeDate 欄位的索引
try:
    time_idx = columns.index('time')
    tradeDate_idx = columns.index('tradeDate')
except ValueError as e:
    print(f"找不到欄位: {e}")
    conn.close()
    exit()

print(f"[Info] 找到 {len(rows)} 筆資料，開始轉換日期格式...")

# 統計資訊
updated_count = 0
skipped_count = 0

# 更新每筆資料的日期格式
for row in rows:
    row_list = list(row)
    original_time = row_list[time_idx]
    original_tradeDate = row_list[tradeDate_idx]
    
    # 轉換日期格式
    normalized_time = normalize_date(original_time)
    normalized_tradeDate = normalize_date(original_tradeDate)
    
    # 如果格式有變化，才更新
    if normalized_time != original_time or normalized_tradeDate != original_tradeDate:
        cursor.execute(
            "UPDATE VIX_data SET time = ?, tradeDate = ? WHERE time = ? AND tradeDate = ?",
            (normalized_time, normalized_tradeDate, original_time, original_tradeDate)
        )
        updated_count += 1
    else:
        skipped_count += 1

# 提交交易
conn.commit()
print(f"[Info] 轉換完成：更新 {updated_count} 筆，跳過 {skipped_count} 筆（格式已正確）")

# 驗證：查詢前3筆資料確認格式
cursor.execute("SELECT time, tradeDate FROM VIX_data LIMIT 3")
verify_data = cursor.fetchall()
print(f"\n[Info] 前3筆資料驗證：")
for i, (time, tradeDate) in enumerate(verify_data, 1):
    print(f"  第{i}筆: time={time}, tradeDate={tradeDate}")

# 關閉資料庫連線
conn.close()
print("\n資料庫連線已關閉")