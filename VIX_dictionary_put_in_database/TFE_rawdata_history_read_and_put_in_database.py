'''
此程式讀取D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata資料夾內的資料
並將其放入資料庫中
'''

#匯入相關套件
import sqlite3
import json

#嘗試讀取D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata資料夾內的資料
#指定一個範例檔
example_file = r'D:\Business_Cycle_stratgy\VIX_dictionary_put_in_database\TFE_rawdata\tvix_20251001'
#讀取範例檔的內容
with open(example_file, "rb") as f:
    raw = f.read()
print("bytes_len =", len(raw))
print("head_bytes =", raw[:80])

text = raw.decode("utf-8-sig", errors="replace")
print("head_text =", repr(text[:200]))
