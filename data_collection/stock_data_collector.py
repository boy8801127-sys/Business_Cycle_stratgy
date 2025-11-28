"""
股票和ETF資料蒐集模組
從證交所 API 取得所有股票和ETF資料（完全參考原設計，但包含ETF）
"""

import requests
import pandas as pd
import sqlite3
import time
import pandas_market_calendars as pmc
from datetime import datetime, timedelta
from .database_manager import DatabaseManager
import re


class StockDataCollector:
    """股票和ETF資料蒐集器"""
    
    def __init__(self, db_manager):
        """
        初始化資料蒐集器
        
        參數:
        - db_manager: DatabaseManager 實例
        """
        self.db_manager = db_manager
        self.db_path = db_manager.db_path
        
        # 確保價格指數表存在
        self.db_manager.init_price_indices_table()
    
    def fetch_all_stocks_and_etf_daily_data(self, date):
        """
        從證交所 MI_INDEX API 取得指定日期的所有個股和ETF收盤行情
        完全參考原設計，但移除 ETF 過濾條件，並加入 stock_name 欄位
        
        參數:
        - date: 日期（YYYYMMDD，例如 '20251114'）
        
        回傳:
        - df_stocks: DataFrame 包含該日期所有個股和ETF的完整成交資訊
          欄位: date, stock_name, ticker, open, high, low, close, volume, turnover, change
        """
        url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
        
        try:
            response = requests.get(
                url,
                params={
                    'date': date,
                    'type': 'ALLBUT0999',  # 全部(不含權證、牛熊證)
                    'response': 'json'
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('stat') != 'OK':
                print(f"[Error] API 回傳錯誤: {data.get('stat')}")
                return pd.DataFrame()
            
            # 找到個股資料表格（title 包含 "每日收盤行情(全部(不含權證、牛熊證))"）
            stock_table = None
            for table in data.get('tables', []):
                title = table.get('title', '')
                if '每日收盤行情' in title and '全部(不含權證、牛熊證)' in title:
                    stock_table = table
                    break
            
            if stock_table is None:
                print(f"[Error] 找不到個股資料表格")
                return pd.DataFrame()
            
            # 取得欄位定義
            fields = stock_table.get('fields', [])
            # fields: ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌(+/-)", "漲跌價差", ...]
            
            # 定義欄位索引
            field_map = {
                'ticker': None,      # 證券代號
                'stock_name': None,   # 證券名稱
                'volume': None,       # 成交股數
                'turnover': None,     # 成交金額
                'open': None,         # 開盤價
                'high': None,         # 最高價
                'low': None,          # 最低價
                'close': None,        # 收盤價
                'change': None        # 漲跌價差
            }
            
            # 對應欄位索引
            for i, field in enumerate(fields):
                if field == '證券代號':
                    field_map['ticker'] = i
                elif field == '證券名稱':
                    field_map['stock_name'] = i
                elif field == '成交股數':
                    field_map['volume'] = i
                elif field == '成交金額':
                    field_map['turnover'] = i
                elif field == '開盤價':
                    field_map['open'] = i
                elif field == '最高價':
                    field_map['high'] = i
                elif field == '最低價':
                    field_map['low'] = i
                elif field == '收盤價':
                    field_map['close'] = i
                elif field == '漲跌價差':
                    field_map['change'] = i
            
            # 檢查必要欄位是否存在
            if field_map['ticker'] is None or field_map['close'] is None:
                print(f"[Error] 找不到必要欄位")
                return pd.DataFrame()
            
            # 解析資料
            records = []
            
            for row in stock_table.get('data', []):
                if len(row) <= max([v for v in field_map.values() if v is not None]):
                    continue
                
                ticker = str(row[field_map['ticker']]).strip()
                
                # 取得證券名稱（如果有）
                stock_name = None
                if field_map['stock_name'] is not None:
                    stock_name = str(row[field_map['stock_name']]).strip() if len(row) > field_map['stock_name'] else None
                
                # 過濾：只保留股票和ETF（排除價格指數，它們在獨立的表格中）
                # 保留：
                # - 4 位純數字（個股）
                # - 4-6 位以 00 開頭的（ETF）
                # - 其他合理的股票代號格式
                if len(ticker) < 4 or len(ticker) > 6:
                    continue
                
                if not (ticker.isdigit() or ticker.startswith('00')):
                    # 如果不是純數字且不是以00開頭，檢查是否為有效的股票代號格式
                    if not re.match(r'^[0-9A-Z]{4,6}$', ticker):
                        continue
                
                # 注意：指數資料在獨立的表格中，不會出現在這裡
                
                try:
                    # 轉換數值（移除逗號和特殊符號）
                    def safe_float(s):
                        if s is None or s == '':
                            return None
                        s_clean = str(s).replace(',', '').replace('--', '0').replace('+', '').strip()
                        # 處理 HTML 標籤（如 <p style= color:green>-</p>）
                        if '<' in s_clean:
                            # 提取數字部分
                            numbers = re.findall(r'-?\d+\.?\d*', s_clean)
                            if numbers:
                                s_clean = numbers[0]
                            else:
                                return None
                        if s_clean == '' or s_clean == '-':
                            return None
                        return float(s_clean)
                    
                    def safe_int(s):
                        if s is None or s == '':
                            return None
                        s_clean = str(s).replace(',', '').replace('--', '0').strip()
                        if '<' in s_clean:
                            numbers = re.findall(r'-?\d+', s_clean)
                            if numbers:
                                s_clean = numbers[0]
                            else:
                                return None
                        if s_clean == '':
                            return None
                        return int(float(s_clean))
                    
                    record = {
                        'date': date,
                        'stock_name': stock_name,
                        'ticker': ticker,
                        'open': safe_float(row[field_map['open']]) if field_map['open'] is not None else None,
                        'high': safe_float(row[field_map['high']]) if field_map['high'] is not None else None,
                        'low': safe_float(row[field_map['low']]) if field_map['low'] is not None else None,
                        'close': safe_float(row[field_map['close']]) if field_map['close'] is not None else None,
                        'volume': safe_int(row[field_map['volume']]) if field_map['volume'] is not None else None,
                        'turnover': safe_float(row[field_map['turnover']]) if field_map['turnover'] is not None else None,
                        'change': safe_float(row[field_map['change']]) if field_map['change'] is not None else None
                    }
                    
                    # 只保留有收盤價的資料
                    if record['close'] is not None:
                        records.append(record)
                        
                except (ValueError, TypeError, IndexError) as e:
                    continue
            
            # 返回個股/ETF DataFrame
            df_stocks = pd.DataFrame(records)
            
            return df_stocks
            
        except Exception as e:
            print(f"[Error] 取得 {date} 的股票和ETF資料失敗: {e}")
            return pd.DataFrame()
    
    def fetch_price_indices_data(self, date):
        """
        從證交所 MI_INDEX API 取得指定日期的價格指數資料
        
        參數:
        - date: 日期（YYYYMMDD，例如 '20251114'）
        
        回傳:
        - df: DataFrame 包含該日期所有價格指數的完整資訊
          欄位: date, ticker, close_index, change_sign, change_points, change_pct, special_note
        """
        url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
        
        try:
            response = requests.get(
                url,
                params={
                    'date': date,
                    'type': 'ALLBUT0999',
                    'response': 'json'
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('stat') != 'OK':
                print(f"[Error] API 回傳錯誤: {data.get('stat')}")
                return pd.DataFrame()
            
            # 找到價格指數表格（title 包含 "價格指數(臺灣證券交易所)"）
            price_index_table = None
            for table in data.get('tables', []):
                title = table.get('title', '')
                if '價格指數' in title and '臺灣證券交易所' in title:
                    price_index_table = table
                    break
            
            if price_index_table is None:
                print(f"[Warning] 找不到價格指數表格")
                return pd.DataFrame()
            
            # 取得欄位定義
            fields = price_index_table.get('fields', [])
            # fields: ["指數", "收盤指數", "漲跌(+/-)", "漲跌點數", "漲跌百分比(%)", "特殊處理註記"]
            
            # 定義欄位索引
            field_map = {
                'index_name': None,    # 指數
                'close_index': None,   # 收盤指數
                'change_sign': None,   # 漲跌(+/-)
                'change_points': None, # 漲跌點數
                'change_pct': None,    # 漲跌百分比(%)
                'special_note': None   # 特殊處理註記
            }
            
            # 對應欄位索引
            for i, field in enumerate(fields):
                if field == '指數':
                    field_map['index_name'] = i
                elif field == '收盤指數':
                    field_map['close_index'] = i
                elif field == '漲跌(+/-)':
                    field_map['change_sign'] = i
                elif field == '漲跌點數':
                    field_map['change_points'] = i
                elif field == '漲跌百分比(%)':
                    field_map['change_pct'] = i
                elif field == '特殊處理註記':
                    field_map['special_note'] = i
            
            # 檢查必要欄位
            if field_map['index_name'] is None or field_map['close_index'] is None:
                print(f"[Error] 找不到價格指數必要欄位")
                return pd.DataFrame()
            
            # 解析資料
            records = []
            
            def safe_float(s):
                """安全轉換為浮點數，處理逗號分隔符"""
                if s is None or s == '':
                    return None
                s_clean = str(s).replace(',', '').replace('--', '0').strip()
                if s_clean == '' or s_clean == '-':
                    return None
                try:
                    return float(s_clean)
                except (ValueError, TypeError):
                    return None
            
            def extract_change_sign(s):
                """從 HTML 標籤中提取漲跌符號"""
                if s is None or s == '':
                    return None
                s_str = str(s)
                # 提取 + 或 -
                if '+' in s_str:
                    return '+'
                elif '-' in s_str:
                    return '-'
                # 如果提取不到，嘗試從數字判斷
                numbers = re.findall(r'-?\d+\.?\d*', s_str)
                if numbers:
                    num = float(numbers[0])
                    return '+' if num >= 0 else '-'
                return None
            
            for row in price_index_table.get('data', []):
                if len(row) <= max([v for v in field_map.values() if v is not None]):
                    continue
                
                try:
                    index_name = str(row[field_map['index_name']]).strip() if len(row) > field_map['index_name'] else None
                    
                    if not index_name:
                        continue
                    
                    # 取得漲跌符號（處理 HTML 標籤）
                    change_sign_raw = row[field_map['change_sign']] if field_map['change_sign'] is not None and len(row) > field_map['change_sign'] else None
                    change_sign = extract_change_sign(change_sign_raw)
                    
                    # 取得收盤指數
                    close_index = safe_float(row[field_map['close_index']]) if field_map['close_index'] is not None and len(row) > field_map['close_index'] else None
                    
                    # 如果沒有收盤指數，跳過
                    if close_index is None:
                        continue
                    
                    record = {
                        'date': date,
                        'ticker': index_name,  # 使用指數名稱作為 ticker
                        'close_index': close_index,
                        'change_sign': change_sign,
                        'change_points': safe_float(row[field_map['change_points']]) if field_map['change_points'] is not None and len(row) > field_map['change_points'] else None,
                        'change_pct': safe_float(row[field_map['change_pct']]) if field_map['change_pct'] is not None and len(row) > field_map['change_pct'] else None,
                        'special_note': str(row[field_map['special_note']]).strip() if field_map['special_note'] is not None and len(row) > field_map['special_note'] else None
                    }
                    
                    records.append(record)
                    
                except (ValueError, TypeError, IndexError) as e:
                    continue
            
            df = pd.DataFrame(records)
            return df
            
        except Exception as e:
            print(f"[Error] 取得 {date} 的價格指數資料失敗: {e}")
            return pd.DataFrame()
    
    def fetch_return_indices_data(self, date):
        """
        從證交所 MI_INDEX API 取得指定日期的報酬指數資料
        
        參數:
        - date: 日期（YYYYMMDD，例如 '20251114'）
        
        回傳:
        - df: DataFrame 包含該日期所有報酬指數的完整資訊
          欄位: date, ticker, close_index, change_sign, change_points, change_pct, special_note
        """
        url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
        
        try:
            response = requests.get(
                url,
                params={
                    'date': date,
                    'type': 'ALLBUT0999',
                    'response': 'json'
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('stat') != 'OK':
                print(f"[Error] API 回傳錯誤: {data.get('stat')}")
                return pd.DataFrame()
            
            # 找到報酬指數表格（title 包含 "報酬指數(臺灣證券交易所)"）
            return_index_table = None
            for table in data.get('tables', []):
                title = table.get('title', '')
                if '報酬指數' in title and '臺灣證券交易所' in title:
                    return_index_table = table
                    break
            
            if return_index_table is None:
                print(f"[Warning] 找不到報酬指數表格")
                return pd.DataFrame()
            
            # 取得欄位定義
            fields = return_index_table.get('fields', [])
            # fields: ["報酬指數", "收盤指數", "漲跌(+/-)", "漲跌點數", "漲跌百分比(%)", "特殊處理註記"]
            
            # 定義欄位索引
            field_map = {
                'index_name': None,    # 報酬指數
                'close_index': None,   # 收盤指數
                'change_sign': None,   # 漲跌(+/-)
                'change_points': None, # 漲跌點數
                'change_pct': None,    # 漲跌百分比(%)
                'special_note': None   # 特殊處理註記
            }
            
            # 對應欄位索引
            for i, field in enumerate(fields):
                if field == '報酬指數':
                    field_map['index_name'] = i
                elif field == '收盤指數':
                    field_map['close_index'] = i
                elif field == '漲跌(+/-)':
                    field_map['change_sign'] = i
                elif field == '漲跌點數':
                    field_map['change_points'] = i
                elif field == '漲跌百分比(%)':
                    field_map['change_pct'] = i
                elif field == '特殊處理註記':
                    field_map['special_note'] = i
            
            # 檢查必要欄位
            if field_map['index_name'] is None or field_map['close_index'] is None:
                print(f"[Error] 找不到報酬指數必要欄位")
                return pd.DataFrame()
            
            # 解析資料
            records = []
            
            def safe_float(s):
                """安全轉換為浮點數，處理逗號分隔符"""
                if s is None or s == '':
                    return None
                s_clean = str(s).replace(',', '').replace('--', '0').strip()
                if s_clean == '' or s_clean == '-':
                    return None
                try:
                    return float(s_clean)
                except (ValueError, TypeError):
                    return None
            
            def extract_change_sign(s):
                """從 HTML 標籤中提取漲跌符號"""
                if s is None or s == '':
                    return None
                s_str = str(s)
                # 提取 + 或 -
                if '+' in s_str:
                    return '+'
                elif '-' in s_str:
                    return '-'
                # 如果提取不到，嘗試從數字判斷
                numbers = re.findall(r'-?\d+\.?\d*', s_str)
                if numbers:
                    num = float(numbers[0])
                    return '+' if num >= 0 else '-'
                return None
            
            for row in return_index_table.get('data', []):
                if len(row) <= max([v for v in field_map.values() if v is not None]):
                    continue
                
                try:
                    index_name = str(row[field_map['index_name']]).strip() if len(row) > field_map['index_name'] else None
                    
                    if not index_name:
                        continue
                    
                    # 取得漲跌符號（處理 HTML 標籤）
                    change_sign_raw = row[field_map['change_sign']] if field_map['change_sign'] is not None and len(row) > field_map['change_sign'] else None
                    change_sign = extract_change_sign(change_sign_raw)
                    
                    # 取得收盤指數
                    close_index = safe_float(row[field_map['close_index']]) if field_map['close_index'] is not None and len(row) > field_map['close_index'] else None
                    
                    # 如果沒有收盤指數，跳過
                    if close_index is None:
                        continue
                    
                    record = {
                        'date': date,
                        'ticker': index_name,  # 使用報酬指數名稱作為 ticker
                        'close_index': close_index,
                        'change_sign': change_sign,
                        'change_points': safe_float(row[field_map['change_points']]) if field_map['change_points'] is not None and len(row) > field_map['change_points'] else None,
                        'change_pct': safe_float(row[field_map['change_pct']]) if field_map['change_pct'] is not None and len(row) > field_map['change_pct'] else None,
                        'special_note': str(row[field_map['special_note']]).strip() if field_map['special_note'] is not None and len(row) > field_map['special_note'] else None
                    }
                    
                    records.append(record)
                    
                except (ValueError, TypeError, IndexError) as e:
                    continue
            
            df = pd.DataFrame(records)
            return df
            
        except Exception as e:
            print(f"[Error] 取得 {date} 的報酬指數資料失敗: {e}")
            return pd.DataFrame()
    
    def fetch_return_indices_data(self, date):
        """
        從證交所 MI_INDEX API 取得指定日期的報酬指數資料
        
        參數:
        - date: 日期（YYYYMMDD，例如 '20251114'）
        
        回傳:
        - df: DataFrame 包含該日期所有報酬指數的完整資訊
          欄位: date, ticker, close_index, change_sign, change_points, change_pct, special_note
        """
        url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
        
        try:
            response = requests.get(
                url,
                params={
                    'date': date,
                    'type': 'ALLBUT0999',
                    'response': 'json'
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('stat') != 'OK':
                print(f"[Error] API 回傳錯誤: {data.get('stat')}")
                return pd.DataFrame()
            
            # 找到報酬指數表格（title 包含 "報酬指數(臺灣證券交易所)"）
            return_index_table = None
            for table in data.get('tables', []):
                title = table.get('title', '')
                if '報酬指數' in title and '臺灣證券交易所' in title:
                    return_index_table = table
                    break
            
            if return_index_table is None:
                print(f"[Warning] 找不到報酬指數表格")
                return pd.DataFrame()
            
            # 取得欄位定義
            fields = return_index_table.get('fields', [])
            # fields: ["報酬指數", "收盤指數", "漲跌(+/-)", "漲跌點數", "漲跌百分比(%)", "特殊處理註記"]
            
            # 定義欄位索引
            field_map = {
                'index_name': None,    # 報酬指數
                'close_index': None,   # 收盤指數
                'change_sign': None,   # 漲跌(+/-)
                'change_points': None, # 漲跌點數
                'change_pct': None,    # 漲跌百分比(%)
                'special_note': None   # 特殊處理註記
            }
            
            # 對應欄位索引
            for i, field in enumerate(fields):
                if field == '報酬指數':
                    field_map['index_name'] = i
                elif field == '收盤指數':
                    field_map['close_index'] = i
                elif field == '漲跌(+/-)':
                    field_map['change_sign'] = i
                elif field == '漲跌點數':
                    field_map['change_points'] = i
                elif field == '漲跌百分比(%)':
                    field_map['change_pct'] = i
                elif field == '特殊處理註記':
                    field_map['special_note'] = i
            
            # 檢查必要欄位
            if field_map['index_name'] is None or field_map['close_index'] is None:
                print(f"[Error] 找不到報酬指數必要欄位")
                return pd.DataFrame()
            
            # 解析資料（邏輯與價格指數相同）
            records = []
            
            def safe_float(s):
                """安全轉換為浮點數，處理逗號分隔符"""
                if s is None or s == '':
                    return None
                s_clean = str(s).replace(',', '').replace('--', '0').strip()
                if s_clean == '' or s_clean == '-':
                    return None
                try:
                    return float(s_clean)
                except (ValueError, TypeError):
                    return None
            
            def extract_change_sign(s):
                """從 HTML 標籤中提取漲跌符號"""
                if s is None or s == '':
                    return None
                s_str = str(s)
                # 提取 + 或 -
                if '+' in s_str:
                    return '+'
                elif '-' in s_str:
                    return '-'
                # 如果提取不到，嘗試從數字判斷
                numbers = re.findall(r'-?\d+\.?\d*', s_str)
                if numbers:
                    num = float(numbers[0])
                    return '+' if num >= 0 else '-'
                return None
            
            for row in return_index_table.get('data', []):
                if len(row) <= max([v for v in field_map.values() if v is not None]):
                    continue
                
                try:
                    index_name = str(row[field_map['index_name']]).strip() if len(row) > field_map['index_name'] else None
                    
                    if not index_name:
                        continue
                    
                    # 取得漲跌符號（處理 HTML 標籤）
                    change_sign_raw = row[field_map['change_sign']] if field_map['change_sign'] is not None and len(row) > field_map['change_sign'] else None
                    change_sign = extract_change_sign(change_sign_raw)
                    
                    # 取得收盤指數
                    close_index = safe_float(row[field_map['close_index']]) if field_map['close_index'] is not None and len(row) > field_map['close_index'] else None
                    
                    # 如果沒有收盤指數，跳過
                    if close_index is None:
                        continue
                    
                    record = {
                        'date': date,
                        'ticker': index_name,  # 使用指數名稱作為 ticker
                        'close_index': close_index,
                        'change_sign': change_sign,
                        'change_points': safe_float(row[field_map['change_points']]) if field_map['change_points'] is not None and len(row) > field_map['change_points'] else None,
                        'change_pct': safe_float(row[field_map['change_pct']]) if field_map['change_pct'] is not None and len(row) > field_map['change_pct'] else None,
                        'special_note': str(row[field_map['special_note']]).strip() if field_map['special_note'] is not None and len(row) > field_map['special_note'] else None
                    }
                    
                    records.append(record)
                    
                except (ValueError, TypeError, IndexError) as e:
                    continue
            
            df = pd.DataFrame(records)
            return df
            
        except Exception as e:
            print(f"[Error] 取得 {date} 的報酬指數資料失敗: {e}")
            return pd.DataFrame()
    
    def save_tw_price_indices_data(self, df, date):
        """
        儲存價格指數資料到資料庫（符合 API 格式的新結構）
        
        參數:
        - df: DataFrame 包含價格指數資料（包含 date, ticker, close_index, change_sign, change_points, change_pct, special_note）
        - date: 日期（YYYYMMDD），如果 df 中已有 date 欄位則可忽略
        """
        if df is None or df.empty:
            return
        
        # 準備資料
        records = []
        for _, row in df.iterrows():
            record_date = row.get('date', date) if 'date' in row else date
            records.append({
                'date': record_date,
                'ticker': row.get('ticker'),
                'close_index': row.get('close_index'),
                'change_sign': row.get('change_sign'),
                'change_points': row.get('change_points'),
                'change_pct': row.get('change_pct'),
                'special_note': row.get('special_note')
            })
        
        save_df = pd.DataFrame(records)
        
        # 儲存到 SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            for _, row in save_df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO tw_price_indices_data 
                    (date, ticker, close_index, change_sign, change_points, change_pct, special_note)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['date'],
                    row['ticker'],
                    row['close_index'],
                    row['change_sign'],
                    row['change_points'],
                    row['change_pct'],
                    row['special_note']
                ))
            conn.commit()
            print(f"[Info] 已儲存 {len(save_df)} 筆價格指數資料到 SQLite")
        except Exception as e:
            conn.rollback()
            print(f"[Error] SQLite 儲存價格指數失敗: {e}")
            raise
        finally:
            conn.close()
    
    def save_tw_return_indices_data(self, df, date):
        """
        儲存報酬指數資料到資料庫（符合 API 格式的新結構）
        
        參數:
        - df: DataFrame 包含報酬指數資料（包含 date, ticker, close_index, change_sign, change_points, change_pct, special_note）
        - date: 日期（YYYYMMDD），如果 df 中已有 date 欄位則可忽略
        """
        if df is None or df.empty:
            return
        
        # 準備資料
        records = []
        for _, row in df.iterrows():
            record_date = row.get('date', date) if 'date' in row else date
            records.append({
                'date': record_date,
                'ticker': row.get('ticker'),
                'close_index': row.get('close_index'),
                'change_sign': row.get('change_sign'),
                'change_points': row.get('change_points'),
                'change_pct': row.get('change_pct'),
                'special_note': row.get('special_note')
            })
        
        save_df = pd.DataFrame(records)
        
        # 儲存到 SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            for _, row in save_df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO tw_return_indices_data 
                    (date, ticker, close_index, change_sign, change_points, change_pct, special_note)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['date'],
                    row['ticker'],
                    row['close_index'],
                    row['change_sign'],
                    row['change_points'],
                    row['change_pct'],
                    row['special_note']
                ))
            conn.commit()
            print(f"[Info] 已儲存 {len(save_df)} 筆報酬指數資料到 SQLite")
        except Exception as e:
            conn.rollback()
            print(f"[Error] SQLite 儲存報酬指數失敗: {e}")
            raise
        finally:
            conn.close()
    
    def save_tw_return_indices_data(self, df, date):
        """
        儲存報酬指數資料到資料庫（符合 API 格式的新結構）
        
        參數:
        - df: DataFrame 包含報酬指數資料（包含 date, ticker, close_index, change_sign, change_points, change_pct, special_note）
        - date: 日期（YYYYMMDD），如果 df 中已有 date 欄位則可忽略
        """
        if df is None or df.empty:
            return
        
        # 準備資料
        records = []
        for _, row in df.iterrows():
            record_date = row.get('date', date) if 'date' in row else date
            records.append({
                'date': record_date,
                'ticker': row.get('ticker'),
                'close_index': row.get('close_index'),
                'change_sign': row.get('change_sign'),
                'change_points': row.get('change_points'),
                'change_pct': row.get('change_pct'),
                'special_note': row.get('special_note')
            })
        
        save_df = pd.DataFrame(records)
        
        # 儲存到 SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            for _, row in save_df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO tw_return_indices_data 
                    (date, ticker, close_index, change_sign, change_points, change_pct, special_note)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['date'],
                    row['ticker'],
                    row['close_index'],
                    row['change_sign'],
                    row['change_points'],
                    row['change_pct'],
                    row['special_note']
                ))
            conn.commit()
            print(f"[Info] 已儲存 {len(save_df)} 筆報酬指數資料到 SQLite")
        except Exception as e:
            conn.rollback()
            print(f"[Error] SQLite 儲存報酬指數失敗: {e}")
            raise
        finally:
            conn.close()
    
    def save_tw_stock_price_data(self, df, date):
        """
        儲存證交所股價資料到資料庫
        
        參數:
        - df: DataFrame 包含證交所股價資料（包含 date, stock_name, ticker, open, high, low, close, volume, turnover, change）
        - date: 日期（YYYYMMDD），如果 df 中已有 date 欄位則可忽略
        """
        if df is None or df.empty:
            return
        
        # 定義安全轉換函式
        def safe_float(val):
            if pd.isna(val) or val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        
        def safe_int(val):
            if pd.isna(val) or val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None
        
        # 準備資料
        records = []
        for _, row in df.iterrows():
            record_date = row.get('date', date) if 'date' in row else date
            records.append({
                'date': record_date,
                'stock_name': row.get('stock_name'),  # 加入 stock_name
                'ticker': row['ticker'],
                'open': safe_float(row.get('open')),
                'high': safe_float(row.get('high')),
                'low': safe_float(row.get('low')),
                'close': safe_float(row.get('close')),
                'volume': safe_int(row.get('volume')),
                'turnover': safe_float(row.get('turnover')),
                'change': safe_float(row.get('change')),
                'odd_lot_filled': safe_int(row.get('odd_lot_filled')) or 0
            })
        
        save_df = pd.DataFrame(records)
        
        # 儲存到 SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            for _, row in save_df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO tw_stock_price_data 
                    (date, stock_name, ticker, open, high, low, close, volume, turnover, change, odd_lot_filled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['date'],
                    row['stock_name'],
                    row['ticker'],
                    row['open'],
                    row['high'],
                    row['low'],
                    row['close'],
                    row['volume'],
                    row['turnover'],
                    row['change'],
                    row['odd_lot_filled']
                ))
            conn.commit()
            print(f"[Info] 已儲存 {len(save_df)} 筆股票和ETF資料到 SQLite")
        except Exception as e:
            conn.rollback()
            print(f"[Error] SQLite 儲存失敗: {e}")
        finally:
            conn.close()
    
    def fetch_specific_date_data(self, date, retry_times=3, retry_delay=5):
        """
        取得指定日期的資料（完全參考原設計）
        
        參數:
        - date: 日期（YYYYMMDD）
        - retry_times: 每個步驟失敗時的重試次數（預設 3 次）
        - retry_delay: 重試前的等待時間（秒，預設 5 秒）
        
        回傳:
        - 是否成功
        """
        print(f"\n{'='*60}")
        print(f"取得指定日期的股票和ETF資料: {date}")
        print(f"{'='*60}\n")
        
        # 取得股價資料
        print(f"[步驟] 取得 {date} 的股票和ETF資料...")
        success_price = False
        for attempt in range(1, retry_times + 1):
            try:
                df_all_stocks, df_indices = self.fetch_all_stocks_and_etf_daily_data(date)
                
                if not df_all_stocks.empty or not df_indices.empty:
                    # 儲存個股和ETF資料到資料庫
                    if not df_all_stocks.empty:
                        self.save_tw_stock_price_data(df_all_stocks, date)
                    
                    # 儲存價格指數資料到資料庫
                    if not df_indices.empty:
                        self.save_tw_price_indices_data(df_indices, date)
                    
                    success_price = True
                    stock_count = len(df_all_stocks) if not df_all_stocks.empty else 0
                    index_count = len(df_indices) if not df_indices.empty else 0
                    print(f"[Info] {date} 資料取得並儲存成功（股票/ETF: {stock_count} 檔，價格指數: {index_count} 檔）")
                    break
                else:
                    if attempt < retry_times:
                        print(f"[Warning] {date} 無法取得資料，{retry_delay} 秒後重試（第 {attempt}/{retry_times} 次）...")
                        time.sleep(retry_delay)
                    else:
                        print(f"[Error] {date} 無法取得資料，已重試 {retry_times} 次")
                        
            except Exception as e:
                if attempt < retry_times:
                    print(f"[Error] {date} 取得資料時發生錯誤: {e}")
                    print(f"[Info] {retry_delay} 秒後重試（第 {attempt}/{retry_times} 次）...")
                    time.sleep(retry_delay)
                else:
                    print(f"[Error] {date} 取得資料時發生錯誤: {e}")
                    print(f"[Error] 已重試 {retry_times} 次")
        
        if not success_price:
            print(f"[Error] {date} 股票和ETF資料取得失敗，中止")
            return False
        
        print(f"\n{'='*60}")
        print(f"{date} 股票和ETF資料取得完成")
        print(f"{'='*60}")
        
        return True
    
    def batch_fetch_stock_prices_only(self, days=15, start_date=None, retry_times=3, retry_delay=5):
        """
        批次取得證交所的股價資料並更新資料庫（完全參考原設計，含禮貌休息機制）
        
        參數:
        - days: 要更新的天數（預設 15 天）
        - start_date: 起始日期（YYYYMMDD），如果為 None，則從 2015-01-01 開始
        - retry_times: 每個日期失敗時的重試次數（預設 3 次）
        - retry_delay: 重試前的等待時間（秒，預設 5 秒）
        
        回傳:
        - 更新結果統計
        """
        print(f"\n{'='*60}")
        print(f"批次取得股票和ETF資料（目標：{days} 個交易日）")
        print(f"{'='*60}\n")
        
        # 取得台灣交易日曆
        cal = pmc.get_calendar('XTAI')
        
        # 確定日期範圍
        if start_date is None:
            # 從 2015-01-01 開始
            start_date_range = pd.Timestamp('2015-01-01')
        else:
            if isinstance(start_date, str):
                # 處理 YYYYMMDD 格式
                if len(start_date) == 8:
                    start_date_range = pd.Timestamp(f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}")
                else:
                    start_date_range = pd.Timestamp(start_date)
            else:
                start_date_range = start_date
        
        today = pd.Timestamp.now()
        
        # 取得交易日列表
        trading_days = cal.valid_days(start_date=start_date_range, end_date=today)
        trading_days_str = [day.strftime('%Y%m%d') for day in trading_days]
        
        # 檢查哪些日期已經有資料
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM tw_stock_price_data")
        existing_price_dates = set([row[0] for row in cursor.fetchall()])
        conn.close()
        
        print(f"[Info] 資料庫中已有 {len(existing_price_dates)} 個交易日的資料")
        
        # 只處理需要更新的日期
        # 如果 days 很大（如 9999），則處理所有交易日；否則限制在最近 N 個交易日
        if days >= len(trading_days_str):
            # 處理所有交易日
            dates_to_update = [
                d for d in trading_days_str 
                if d not in existing_price_dates
            ]
        else:
            # 只處理最近 N 個交易日
            dates_to_update = [
                d for d in trading_days_str[-days:] 
                if d not in existing_price_dates
            ]
        
        if not dates_to_update:
            print(f"[Info] 沒有需要更新股價資料的日期")
            return {'success': 0, 'failed': 0, 'skipped': days, 'total': days}
        
        print(f"[Info] 需要更新 {len(dates_to_update)} 個交易日的股票和ETF資料")
        print(f"[Info] 日期列表: {', '.join(dates_to_update[:5])}{'...' if len(dates_to_update) > 5 else ''}\n")
        
        # 按日期批次取得股價資料
        success_count = 0
        failed_dates = []
        
        for i, date in enumerate(dates_to_update, 1):
            print(f"[{i}/{len(dates_to_update)}] 正在取得 {date} 的所有股票和ETF資料...")
            
            # 重試邏輯
            success = False
            for attempt in range(1, retry_times + 1):
                try:
                    # 取得個股和ETF資料
                    df_all_stocks = self.fetch_all_stocks_and_etf_daily_data(date)
                    
                    # 取得價格指數資料
                    df_price_indices = self.fetch_price_indices_data(date)
                    
                    # 取得報酬指數資料
                    df_return_indices = self.fetch_return_indices_data(date)
                    
                    # 如果至少有一個資料集不為空，則視為成功
                    if not df_all_stocks.empty or not df_price_indices.empty or not df_return_indices.empty:
                        # 儲存個股和ETF資料到資料庫
                        if not df_all_stocks.empty:
                            self.save_tw_stock_price_data(df_all_stocks, date)
                        
                        # 儲存價格指數資料到資料庫
                        if not df_price_indices.empty:
                            self.save_tw_price_indices_data(df_price_indices, date)
                        
                        # 儲存報酬指數資料到資料庫
                        if not df_return_indices.empty:
                            self.save_tw_return_indices_data(df_return_indices, date)
                        
                        success = True
                        success_count += 1
                        stock_count = len(df_all_stocks) if not df_all_stocks.empty else 0
                        price_index_count = len(df_price_indices) if not df_price_indices.empty else 0
                        return_index_count = len(df_return_indices) if not df_return_indices.empty else 0
                        print(f"[Info] {date} 成功取得資料（股票/ETF: {stock_count} 檔，價格指數: {price_index_count} 檔，報酬指數: {return_index_count} 檔）")
                        break
                    else:
                        if attempt < retry_times:
                            print(f"[Warning] {date} 無法取得資料，{retry_delay} 秒後重試（第 {attempt}/{retry_times} 次）...")
                            time.sleep(retry_delay)
                        else:
                            print(f"[Error] {date} 無法取得資料，已重試 {retry_times} 次，跳過此日期")
                            
                except Exception as e:
                    if attempt < retry_times:
                        print(f"[Error] {date} 取得資料時發生錯誤: {e}")
                        print(f"[Info] {retry_delay} 秒後重試（第 {attempt}/{retry_times} 次）...")
                        time.sleep(retry_delay)
                    else:
                        print(f"[Error] {date} 取得資料時發生錯誤: {e}")
                        print(f"[Error] 已重試 {retry_times} 次，跳過此日期")
            
            if not success:
                failed_dates.append(date)
            
            # 禮貌休息：每個日期請求後休息 5 秒
            if i < len(dates_to_update):
                time.sleep(5)
        
        print(f"\n{'='*60}")
        print("批次取得股票和ETF資料完成")
        print(f"{'='*60}")
        print(f"成功: {success_count} 天")
        print(f"失敗: {len(failed_dates)} 天")
        if failed_dates:
            print(f"失敗日期: {', '.join(failed_dates)}")
        
        return {
            'success': success_count,
            'failed': len(failed_dates),
            'skipped': days - len(dates_to_update),
            'total': days
        }

