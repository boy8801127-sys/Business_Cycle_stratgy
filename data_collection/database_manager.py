"""
資料庫管理模組
連接資料庫，提供資料查詢和寫入功能
"""

import sqlite3
import pandas as pd
from datetime import datetime
import os


class DatabaseManager:
    """資料庫管理類別"""
    
    def __init__(self, db_path='D:\\all_data\\taiwan_stock_all_data.db'):
        """
        初始化資料庫管理器
        
        參數:
        - db_path: SQLite 資料庫路徑
        """
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """確保資料庫檔案存在"""
        if not os.path.exists(self.db_path):
            # 如果資料庫不存在，建立一個空資料庫
            conn = sqlite3.connect(self.db_path)
            conn.close()
            print(f"[Info] 建立新資料庫: {self.db_path}")
        
        # 確保所需資料表存在
        self.init_price_indices_table()
        self.init_return_indices_table()
        self.init_otc_stock_price_table()
        # 確保上市/上櫃股票資料表含必要欄位
        self.ensure_table_column('tw_stock_price_data', 'odd_lot_filled', 'INTEGER DEFAULT 0')
        self.ensure_table_column('tw_otc_stock_price_data', 'odd_lot_filled', 'INTEGER DEFAULT 0')
    
    def get_connection(self):
        """取得資料庫連接"""
        return sqlite3.connect(self.db_path)
    
    def execute_query(self, query, params=None):
        """
        執行查詢並回傳結果
        
        參數:
        - query: SQL 查詢語句
        - params: 查詢參數（可選）
        
        回傳:
        - 查詢結果列表
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            return results
        finally:
            conn.close()
    
    def execute_query_dataframe(self, query, params=None):
        """
        執行查詢並回傳 DataFrame
        
        參數:
        - query: SQL 查詢語句
        - params: 查詢參數（可選）
        
        回傳:
        - DataFrame
        """
        conn = self.get_connection()
        try:
            if params:
                df = pd.read_sql_query(query, conn, params=params)
            else:
                df = pd.read_sql_query(query, conn)
            return df
        finally:
            conn.close()
    
    def save_dataframe(self, df, table_name, if_exists='replace'):
        """
        儲存 DataFrame 到資料庫
        
        參數:
        - df: 要儲存的 DataFrame
        - table_name: 資料表名稱
        - if_exists: 如果表存在時的處理方式（'replace', 'append', 'fail'）
        """
        if df.empty:
            print(f"[Warning] DataFrame 為空，跳過儲存到 {table_name}")
            return
        
        conn = self.get_connection()
        try:
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            print(f"[Info] 成功儲存 {len(df)} 筆資料到 {table_name}")
        except Exception as e:
            print(f"[Error] 儲存資料到 {table_name} 失敗: {e}")
            raise
        finally:
            conn.close()
    
    def get_stock_price(self, ticker=None, start_date=None, end_date=None):
        """
        取得股價資料
        
        參數:
        - ticker: 股票代號（None 表示所有股票）
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        
        回傳:
        - DataFrame
        """
        query = "SELECT * FROM tw_stock_price_data WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(str(ticker))
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date, ticker"
        
        return self.execute_query_dataframe(query, params if params else None)
    
    def get_otc_stock_price(self, ticker=None, start_date=None, end_date=None):
        """
        取得上櫃股價資料
        """
        query = "SELECT * FROM tw_otc_stock_price_data WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(str(ticker))
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date, ticker"
        
        return self.execute_query_dataframe(query, params if params else None)
    
    def get_trading_dates(self, start_date=None, end_date=None):
        """
        取得交易日列表
        
        參數:
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        
        回傳:
        - 交易日列表（字串格式 YYYYMMDD）
        """
        query = "SELECT DISTINCT date FROM tw_stock_price_data WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date"
        
        results = self.execute_query(query, params if params else None)
        return [row[0] for row in results]
    
    def check_table_exists(self, table_name):
        """
        檢查資料表是否存在
        
        參數:
        - table_name: 資料表名稱
        
        回傳:
        - True 或 False
        """
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        results = self.execute_query(query, (table_name,))
        return len(results) > 0
    
    def get_table_schema(self, table_name):
        """
        取得資料表結構
        
        參數:
        - table_name: 資料表名稱
        
        回傳:
        - 資料表結構資訊
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            return cursor.fetchall()
        finally:
            conn.close()
    
    def ensure_table_column(self, table_name, column_name, column_definition):
        """
        確保指定資料表包含特定欄位，若不存在則新增
        """
        if not self.check_table_exists(table_name):
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            if column_name in column_names:
                return
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )
            conn.commit()
            print(f"[Info] {table_name} 已新增欄位 {column_name}")
        except Exception as e:
            conn.rollback()
            print(f"[Warning] 無法為 {table_name} 新增欄位 {column_name}: {e}")
        finally:
            conn.close()
    
    def init_price_indices_table(self):
        """
        初始化價格指數資料表（tw_price_indices_data）
        根據 API 回應格式設計：指數名稱、收盤指數、漲跌符號、漲跌點數、漲跌百分比、特殊處理註記
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tw_price_indices_data'")
            table_exists = cursor.fetchone()
            
            if table_exists:
                # 檢查表結構是否正確（檢查是否有 close_index 欄位）
                cursor.execute("PRAGMA table_info(tw_price_indices_data)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # 如果表存在但結構不正確（沒有 close_index 欄位），需要重建表
                if 'close_index' not in column_names:
                    print("[Info] 偵測到舊版價格指數表結構，正在重建...")
                    # 刪除舊表
                    cursor.execute("DROP TABLE tw_price_indices_data")
                    conn.commit()
            
            # 建立價格指數資料表（符合 API 格式）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tw_price_indices_data (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    close_index REAL,
                    change_sign TEXT,
                    change_points REAL,
                    change_pct REAL,
                    special_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            
            conn.commit()
            print(f"[Info] 價格指數資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化價格指數資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_return_indices_table(self):
        """
        初始化報酬指數資料表（tw_return_indices_data）
        結構與價格指數表相同
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tw_return_indices_data'")
            table_exists = cursor.fetchone()
            
            if table_exists:
                # 檢查表結構是否正確（檢查是否有 close_index 欄位）
                cursor.execute("PRAGMA table_info(tw_return_indices_data)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # 如果表存在但結構不正確（沒有 close_index 欄位），需要重建表
                if 'close_index' not in column_names:
                    print("[Info] 偵測到舊版報酬指數表結構，正在重建...")
                    # 刪除舊表
                    cursor.execute("DROP TABLE tw_return_indices_data")
                    conn.commit()
            
            # 建立報酬指數資料表（符合 API 格式）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tw_return_indices_data (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    close_index REAL,
                    change_sign TEXT,
                    change_points REAL,
                    change_pct REAL,
                    special_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            
            conn.commit()
            print(f"[Info] 報酬指數資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化報酬指數資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def init_otc_stock_price_table(self):
        """
        初始化上櫃股票資料表（tw_otc_stock_price_data）
        結構與上市股票資料表相同，獨立儲存櫃買中心資料
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tw_otc_stock_price_data (
                    date TEXT NOT NULL,
                    stock_name TEXT,
                    ticker TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    turnover REAL,
                    change REAL,
                    odd_lot_filled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            conn.commit()
            print("[Info] 上櫃股票資料表初始化完成")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 初始化上櫃股票資料表失敗: {e}")
            raise
        finally:
            conn.close()
    
    def get_price_indices(self, ticker=None, start_date=None, end_date=None):
        """
        取得價格指數資料
        
        參數:
        - ticker: 指數名稱（None 表示所有指數）
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        
        回傳:
        - DataFrame
        """
        query = "SELECT * FROM tw_price_indices_data WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(str(ticker))
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date, ticker"
        
        return self.execute_query_dataframe(query, params if params else None)
    
    def clear_table_data(self, table_name):
        """
        清除指定表的資料
        
        參數:
        - table_name: 要清除的資料表名稱
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"DELETE FROM {table_name}")
            conn.commit()
            print(f"[Info] 已清除 {table_name} 表的所有資料")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 清除 {table_name} 表資料失敗: {e}")
            raise
        finally:
            conn.close()
    
    def modify_stock_price_table_add_stock_name(self):
        """
        修改 tw_stock_price_data 表，在 date 和 ticker 之間新增 stock_name 欄位
        由於 SQLite 不支援 ALTER TABLE ADD COLUMN AFTER，需要重建表結構
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tw_stock_price_data'")
            if not cursor.fetchone():
                print("[Info] tw_stock_price_data 表不存在，將建立新表")
                cursor.execute('''
                    CREATE TABLE tw_stock_price_data (
                        date TEXT NOT NULL,
                        stock_name TEXT,
                        ticker TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume INTEGER,
                        turnover REAL,
                        change REAL,
                        odd_lot_filled INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (date, ticker)
                    )
                ''')
                conn.commit()
                print("[Info] 已建立新的 tw_stock_price_data 表（包含 stock_name 欄位）")
                return
            
            # 檢查是否已有 stock_name 欄位
            cursor.execute("PRAGMA table_info(tw_stock_price_data)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'stock_name' in column_names:
                print("[Info] tw_stock_price_data 表已包含 stock_name 欄位，無需修改")
                return
            
            # 如果表存在但沒有 stock_name 欄位，需要重建表
            print("[Info] 開始重建 tw_stock_price_data 表結構...")
            
            # 建立新表（包含 stock_name 欄位）
            cursor.execute('''
                CREATE TABLE tw_stock_price_data_new (
                    date TEXT NOT NULL,
                    stock_name TEXT,
                    ticker TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    turnover REAL,
                    change REAL,
                    odd_lot_filled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            
            # 複製舊資料到新表（stock_name 設為 NULL）
            cursor.execute('''
                INSERT INTO tw_stock_price_data_new 
                (date, stock_name, ticker, open, high, low, close, volume, turnover, change, odd_lot_filled, created_at)
                SELECT date, NULL as stock_name, ticker, open, high, low, close, volume, turnover, change, 0 as odd_lot_filled, created_at
                FROM tw_stock_price_data
            ''')
            
            # 刪除舊表
            cursor.execute("DROP TABLE tw_stock_price_data")
            
            # 重新命名新表
            cursor.execute("ALTER TABLE tw_stock_price_data_new RENAME TO tw_stock_price_data")
            
            conn.commit()
            print("[Info] tw_stock_price_data 表結構重建完成（已加入 stock_name 欄位）")
            
        except Exception as e:
            conn.rollback()
            print(f"[Error] 修改 tw_stock_price_data 表結構失敗: {e}")
            raise
        finally:
            conn.close()
    
    def get_return_indices(self, ticker=None, start_date=None, end_date=None):
        """
        取得報酬指數資料
        
        參數:
        - ticker: 指數代號（None 表示所有指數）
        - start_date: 起始日期（YYYYMMDD）
        - end_date: 結束日期（YYYYMMDD）
        
        回傳:
        - DataFrame
        """
        query = "SELECT * FROM tw_return_indices_data WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(str(ticker))
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date, ticker"
        
        return self.execute_query_dataframe(query, params if params else None)
    
    def clear_table_data(self, table_name):
        """
        清除資料表的所有資料
        
        參數:
        - table_name: 資料表名稱
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"DELETE FROM {table_name}")
            conn.commit()
            print(f"[Info] 已清除 {table_name} 表的所有資料")
        except Exception as e:
            conn.rollback()
            print(f"[Error] 清除 {table_name} 表資料失敗: {e}")
            raise
        finally:
            conn.close()
    
    def modify_stock_price_table_add_stock_name(self):
        """
        修改 tw_stock_price_data 表結構，在 date 和 ticker 之間加入 stock_name 欄位
        由於 SQLite 不支援 ALTER TABLE ADD COLUMN AFTER，需要重建表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 檢查表是否存在
            if not self.check_table_exists('tw_stock_price_data'):
                print("[Info] tw_stock_price_data 表不存在，直接建立新表")
                cursor.execute('''
                    CREATE TABLE tw_stock_price_data (
                        date TEXT NOT NULL,
                        stock_name TEXT,
                        ticker TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume INTEGER,
                        turnover REAL,
                        change REAL,
                        odd_lot_filled INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (date, ticker)
                    )
                ''')
                conn.commit()
                print("[Info] 已建立包含 stock_name 欄位的 tw_stock_price_data 表")
                return
            
            # 檢查是否已有 stock_name 欄位
            schema = self.get_table_schema('tw_stock_price_data')
            column_names = [col[1] for col in schema]
            
            if 'stock_name' in column_names:
                print("[Info] tw_stock_price_data 表已包含 stock_name 欄位，無需修改")
                return
            
            print("[Info] 開始重建 tw_stock_price_data 表結構...")
            
            # 1. 建立新表（包含 stock_name 欄位）
            cursor.execute('''
                CREATE TABLE tw_stock_price_data_new (
                    date TEXT NOT NULL,
                    stock_name TEXT,
                    ticker TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    turnover REAL,
                    change REAL,
                    odd_lot_filled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            
            # 2. 複製舊資料（stock_name 設為 NULL）
            cursor.execute('''
                INSERT INTO tw_stock_price_data_new 
                (date, ticker, open, high, low, close, volume, turnover, change, odd_lot_filled, created_at)
                SELECT date, ticker, open, high, low, close, volume, turnover, change, 0 as odd_lot_filled, created_at
                FROM tw_stock_price_data
            ''')
            
            # 3. 刪除舊表
            cursor.execute('DROP TABLE tw_stock_price_data')
            
            # 4. 重新命名新表
            cursor.execute('ALTER TABLE tw_stock_price_data_new RENAME TO tw_stock_price_data')
            
            conn.commit()
            print("[Info] 已成功重建 tw_stock_price_data 表結構，加入 stock_name 欄位")
            
        except Exception as e:
            conn.rollback()
            print(f"[Error] 修改 tw_stock_price_data 表結構失敗: {e}")
            raise
        finally:
            conn.close()

