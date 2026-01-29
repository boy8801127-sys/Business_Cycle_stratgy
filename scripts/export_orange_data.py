"""
輸出 Orange 分析數據腳本
將股價數據（006208、2330）與領先/同時/落後指標合併，輸出為長格式 CSV
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Iterable, Optional, Sequence, List

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collection.database_manager import DatabaseManager


def get_column_chinese_mapping():
    """
    取得欄位中文映射字典
    用於將英文欄位名稱轉換為中文，方便理解
    """
    mapping = {
        # 基本欄位
        'date': '日期',
        'ticker': '股票代號',
        'close': '收盤價',
        'open': '開盤價',
        'high': '最高價',
        'low': '最低價',
        'volume': '成交量',
        'turnover': '成交金額',
        
        # 報酬率相關
        'daily_return': '日報酬率(%)',
        'cumulative_return': '累積報酬率(%)',
        
        # 時間特徵
        'year': '年份',
        'month': '月份',
        'quarter': '季度',
        'day_of_week': '星期幾(0=週一)',
        'is_month_start': '是否月初(1=是)',
        'is_month_end': '是否月末(1=是)',
        
        # 技術指標 - 日線
        'ma5': '5日移動平均線',
        'ma20': '20日移動平均線',
        'ma60': '60日移動平均線',
        'price_vs_ma5': '股價相對5日均線位置(%)',
        'price_vs_ma20': '股價相對20日均線位置(%)',
        'volatility_20': '20日波動率',
        'volatility_pct_20': '20日波動率(%)',
        'return_1d': '1日報酬率(%)',
        'return_5d': '5日報酬率(%)',
        'return_20d': '20日報酬率(%)',
        'rsi': 'RSI指標(14日)',
        'volume_ma5': '5日平均成交量',
        'volume_ratio': '成交量比率',
        
        # 技術指標 - 月線
        'ma3': '3月移動平均線',
        'ma6': '6月移動平均線',
        'ma12': '12月移動平均線',
        'price_vs_ma3': '股價相對3月均線位置(%)',
        'price_vs_ma6': '股價相對6月均線位置(%)',
        'volatility_6': '6月波動率',
        'volatility_pct_6': '6月波動率(%)',
        'return_1m': '1月報酬率(%)',
        'return_3m': '3月報酬率(%)',
        'return_12m': '12月報酬率(%)',
        'volume_ma3': '3月平均成交量',
        
        # 融資融券指標
        'short_margin_ratio': '券資比',
        'margin_balance_change_rate': '融資餘額變化率(%)',
        'margin_balance_net_change': '融資餘額淨增減(仟元)',
        'margin_buy_sell_ratio': '融資買賣比',
        'margin_buy_sell_net': '融資買賣淨額(仟元)',
        'short_balance_change_rate': '融券餘額變化率(%)',
        'short_balance_net_change': '融券餘額淨增減(交易單位)',
        'short_buy_sell_ratio': '融券買賣比',
        'short_buy_sell_net': '融券買賣淨額(交易單位)',
    }
    
    # 添加融資融券指標的滯後值和變化率
    margin_base_cols = [
        'short_margin_ratio',
        'margin_balance_change_rate',
        'margin_balance_net_change',
        'margin_buy_sell_ratio',
        'margin_buy_sell_net',
        'short_balance_change_rate',
        'short_balance_net_change',
        'short_buy_sell_ratio',
        'short_buy_sell_net'
    ]
    
    for col in margin_base_cols:
        if col in mapping:
            mapping[f'{col}_lag1'] = f'{mapping[col]}_前1期'
            mapping[f'{col}_lag2'] = f'{mapping[col]}_前2期'
            mapping[f'{col}_change'] = f'{mapping[col]}_變化量'
    
    # 添加總經指標的中文映射（leading_, coincident_, lagging_, signal_ 前綴）
    # 領先指標
    mapping.update({
        'leading_export_order_index': '領先_外銷訂單動向指數(以家數計)',
        'leading_m1b_money_supply': '領先_貨幣總計數M1B(百萬元)',
        'leading_m1b_yoy_month': '領先_M1B月對月年增率(%)',
        'leading_m1b_yoy_momentum': '領先_M1B年增率動能(%)',
        'leading_m1b_mom': '領先_M1B月對月變化率(%)',
        'leading_m1b_vs_3m_avg': '領先_M1B當月vs前三個月平均變化率(%)',
        'leading_stock_price_index': '領先_股價指數(Index1966=100)',
        'leading_employment_net_entry_rate': '領先_工業及服務業受僱員工淨進入率(%)',
        'leading_building_floor_area': '領先_建築物開工樓地板面積(千平方公尺)',
        'leading_semiconductor_import': '領先_名目半導體設備進口(新臺幣百萬元)',
    })
    
    # 同時指標
    mapping.update({
        'coincident_industrial_production_index': '同時_工業生產指數(Index2021=100)',
        'coincident_electricity_consumption': '同時_電力(企業)總用電量(十億度)',
        'coincident_manufacturing_sales_index': '同時_製造業銷售量指數(Index2021=100)',
        'coincident_wholesale_retail_revenue': '同時_批發零售及餐飲業營業額(十億元)',
        'coincident_overtime_hours': '同時_工業及服務業加班工時(小時)',
        'coincident_export_value': '同時_海關出口值(十億元)',
        'coincident_machinery_import': '同時_機械及電機設備進口值(十億元)',
    })
    
    # 落後指標
    mapping.update({
        'lagging_unemployment_rate': '落後_失業率(%)',
        'lagging_labor_cost_index': '落後_製造業單位產出勞動成本指數(2021=100)',
        'lagging_loan_interest_rate': '落後_五大銀行新承做放款平均利率(年息百分比)',
        'lagging_financial_institution_loans': '落後_全體金融機構放款與投資(10億元)',
        'lagging_manufacturing_inventory': '落後_製造業存貨價值(千元)',
    })
    
    # 信號指標
    mapping.update({
        'signal_leading_index': '信號_領先指標綜合指數',
        'signal_leading_index_no_trend': '信號_領先指標不含趨勢指數',
        'signal_coincident_index': '信號_同時指標綜合指數',
        'signal_coincident_index_no_trend': '信號_同時指標不含趨勢指數',
        'signal_lagging_index': '信號_落後指標綜合指數',
        'signal_lagging_index_no_trend': '信號_落後指標不含趨勢指數',
        'signal_business_cycle_score': '信號_景氣對策信號綜合分數',
        'signal_business_cycle_signal': '信號_景氣對策信號(燈號顏色)',
    })
    
    return mapping


def rename_columns_to_chinese(df):
    """
    將 DataFrame 的欄位名稱轉換為中文
    
    參數:
    - df: 原始 DataFrame
    
    返回:
    - 欄位名稱已轉換為中文的 DataFrame
    """
    mapping = get_column_chinese_mapping()
    
    # 只重命名存在的欄位
    rename_dict = {col: mapping[col] for col in df.columns if col in mapping}
    
    # 對於沒有映射的欄位，保持原樣（可能是動態生成的欄位）
    df_renamed = df.rename(columns=rename_dict)
    
    return df_renamed


def load_margin_data(db_manager: DatabaseManager, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    讀取融資融券數據
    
    參數:
    - db_manager: DatabaseManager 實例
    - start_date: 起始日期（YYYYMMDD）
    - end_date: 結束日期（YYYYMMDD）
    
    返回:
    - DataFrame: 包含融資融券數據和衍生指標
    """
    margin_df = db_manager.get_market_margin_data(start_date=start_date, end_date=end_date)
    
    if margin_df.empty:
        return pd.DataFrame()
    
    # 轉換日期格式
    margin_df['date'] = pd.to_datetime(margin_df['date'], format='%Y%m%d', errors='coerce')
    margin_df = margin_df[margin_df['date'].notna()]
    margin_df = margin_df.sort_values('date').reset_index(drop=True)
    
    return margin_df


def get_margin_for_date(target_date: pd.Timestamp, margin_df: pd.DataFrame):
    """
    根據目標日期，取得對應的融資維持率數據
    
    參數:
    - target_date: 目標日期（datetime）
    - margin_df: 融資維持率數據 DataFrame（包含 date 欄位）
    
    返回:
    - Series: 對應的融資維持率數據
    """
    if margin_df.empty:
        return pd.Series(dtype=float)
    
    # 找到最接近的日期（使用當日或最近的前一個交易日）
    target_date_str = target_date.strftime('%Y-%m-%d')
    margin_df['date_str'] = margin_df['date'].dt.strftime('%Y-%m-%d')
    
    # 先嘗試精確匹配
    exact_match = margin_df[margin_df['date_str'] == target_date_str]
    if not exact_match.empty:
        return exact_match.iloc[0]
    
    # 如果沒有精確匹配，找最近的前一個交易日
    before_dates = margin_df[margin_df['date'] <= target_date]
    if not before_dates.empty:
        return before_dates.iloc[-1]
    
    return pd.Series(dtype=float)


def load_indicator_data(db_manager: Optional[DatabaseManager] = None, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    讀取所有指標數據（領先、同時、落後、綜合指標）
    從 merged_economic_indicators 表讀取預先計算的合併指標
    
    參數:
    - db_manager: DatabaseManager 實例（如果為 None，則建立新的實例）
    - start_date: 起始日期（YYYYMMDD 格式，可選）
    - end_date: 結束日期（YYYYMMDD 格式，可選）
    
    返回:
    - DataFrame: 包含合併指標的數據，indicator_date 欄位為 datetime 類型
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    
    # 建立查詢語句
    query = "SELECT * FROM merged_economic_indicators WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND indicator_date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND indicator_date <= ?"
        params.append(end_date)
    
    query += " ORDER BY indicator_date"
    
    # 從資料庫讀取
    merged_indicators = db_manager.execute_query_dataframe(query, params=params if params else None)
    
    if merged_indicators.empty:
        print("[Warning] merged_economic_indicators 表為空，請先執行選項1匯入資料並計算合併指標")
        return pd.DataFrame()
    
    # 將 indicator_date 從 YYYYMMDD 字串轉換為 datetime
    merged_indicators['indicator_date'] = pd.to_datetime(merged_indicators['indicator_date'], format='%Y%m%d', errors='coerce')
    merged_indicators = merged_indicators[merged_indicators['indicator_date'].notna()]
    
    # 按日期排序
    merged_indicators = merged_indicators.sort_values('indicator_date').reset_index(drop=True)
    
    return merged_indicators


def get_indicator_for_date(target_date, indicator_df):
    """
    根據目標日期，取得往前推2個月的指標數據
    
    參數:
    - target_date: 目標日期（datetime）
    - indicator_df: 指標數據 DataFrame（包含 indicator_date 欄位）
    
    返回:
    - Series: 對應的指標數據
    """
    # 計算往前推2個月的日期（該月份的第一天）
    target_month = target_date.replace(day=1)
    
    # 使用 pandas 的 DateOffset 來往前推2個月
    indicator_month = target_month - pd.DateOffset(months=2)
    
    # 在指標數據中查找對應月份的數據
    # 找到 indicator_date 與 indicator_month 相同月份的數據
    mask = (indicator_df['indicator_date'].dt.year == indicator_month.year) & \
           (indicator_df['indicator_date'].dt.month == indicator_month.month)
    
    matching_rows = indicator_df[mask]
    
    if len(matching_rows) > 0:
        # 返回第一筆匹配的數據（應該只有一筆，因為是月數據）
        return matching_rows.iloc[0]
    else:
        # 如果找不到，返回空 Series
        return pd.Series(dtype=float)


def load_monthly_technical_indicators(
    db_manager: DatabaseManager,
    tickers: Sequence[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    從資料庫讀取月線技術指標資料
    
    參數:
    - db_manager: DatabaseManager 實例
    - tickers: 股票代號列表
    - start_date: 起始日期（YYYYMMDD）
    - end_date: 結束日期（YYYYMMDD）
    
    返回:
    - DataFrame: 包含月線技術指標的資料
    """
    print("\n正在讀取月線技術指標數據...")
    
    if not tickers:
        print("  [Warning] 沒有指定股票代號")
        return pd.DataFrame()
    
    # 使用參數化查詢避免 SQL 注入
    placeholders = ','.join(['?'] * len(tickers))
    query = f"SELECT * FROM stock_technical_indicators_monthly WHERE ticker IN ({placeholders})"
    params = [str(t) for t in tickers]
    
    if start_date:
        query += " AND date >= ?"
        params.append(str(start_date))
    if end_date:
        query += " AND date <= ?"
        params.append(str(end_date))
    
    query += " ORDER BY date, ticker"
    
    df = db_manager.execute_query_dataframe(query, params)
    
    if df.empty:
        print("  [Warning] 沒有找到月線技術指標數據")
        return pd.DataFrame()
    
    # 轉換日期格式
    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
    df = df[df['date'].notna()]
    df = df.sort_values(['date', 'ticker']).reset_index(drop=True)
    
    print(f"  共讀取 {len(df)} 筆月線技術指標數據（從 {df['date'].min()} 至 {df['date'].max()}）")
    return df


def _parse_ymd(date_str: Optional[str], default: Optional[pd.Timestamp] = None) -> pd.Timestamp:
    """
    解析日期字串為 Timestamp。
    支援常見格式：YYYY-MM-DD、YYYYMMDD。
    """
    if date_str is None or str(date_str).strip() == "":
        if default is None:
            raise ValueError("日期不可為空")
        return default
    return pd.Timestamp(str(date_str).strip())


def _to_yyyymmdd(ts: pd.Timestamp) -> str:
    return ts.strftime('%Y%m%d')


def _normalize_tickers(tickers: Optional[Sequence[str]]) -> List[str]:
    if not tickers:
        return ['006208', '2330']
    return [str(t).strip() for t in tickers if str(t).strip()]


def _load_stock_data_from_db(
    db_manager: DatabaseManager,
    tickers: Sequence[str],
    start_yyyymmdd: str,
    end_yyyymmdd: str,
    columns: Sequence[str],
) -> pd.DataFrame:
    stock_data_list = []
    for ticker in tickers:
        print(f"  讀取 {ticker}...")
        df = db_manager.get_stock_price(ticker=ticker, start_date=start_yyyymmdd, end_date=end_yyyymmdd)
        # PowerShell 可能會把 006208 解析成 6208，這裡做一次容錯：若查不到且為 4 位數字，嘗試補 '00'
        if df.empty and str(ticker).isdigit() and len(str(ticker)) == 4:
            alt = f"00{ticker}"
            df = db_manager.get_stock_price(ticker=alt, start_date=start_yyyymmdd, end_date=end_yyyymmdd)
            if not df.empty:
                print(f"    [Info] ticker 容錯：{ticker} -> {alt}")
        if df.empty:
            continue

        keep_cols = [c for c in columns if c in df.columns]
        df = df[keep_cols].copy()
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
        df = df[df['date'].notna()]
        df = df.sort_values(['date', 'ticker']).reset_index(drop=True)
        stock_data_list.append(df)

    if not stock_data_list:
        return pd.DataFrame()

    stock_data = pd.concat(stock_data_list, ignore_index=True)
    stock_data = stock_data.sort_values(['date', 'ticker']).reset_index(drop=True)
    return stock_data


def export_orange_data_daily(
    start_date: str = '2015-01-01',
    end_date: Optional[str] = None,
    tickers: Optional[Sequence[str]] = None,
    output_path: str = 'results/orange_analysis_data.csv',
    db_path: str = 'D:\\all_data\\taiwan_stock_all_data.db',
):
    """輸出日線 Orange 分析數據（原功能，改為可設定日期範圍）"""
    print("\n[輸出 Orange 分析數據 - 日線]")
    print("-" * 60)

    start_ts = _parse_ymd(start_date)
    end_ts = _parse_ymd(end_date, default=pd.Timestamp(datetime.now()))
    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts

    tickers = _normalize_tickers(tickers)
    print(f"時間範圍：{start_ts.strftime('%Y-%m-%d')} 至 {end_ts.strftime('%Y-%m-%d')}")
    print(f"股票代號：{tickers}")

    # 初始化數據庫管理器
    db_manager = DatabaseManager(db_path=db_path)

    # 讀取股價數據
    print("\n正在讀取股價數據...")
    stock_data = _load_stock_data_from_db(
        db_manager,
        tickers=tickers,
        start_yyyymmdd=_to_yyyymmdd(start_ts),
        end_yyyymmdd=_to_yyyymmdd(end_ts),
        columns=['date', 'ticker', 'close'],
    )
    if stock_data.empty:
        print("[Error] 無法讀取股價數據")
        return None
    print(f"  共讀取 {len(stock_data)} 筆股價數據")

    # 讀取指標數據
    print("\n正在讀取指標數據...")
    # 指標對齊採 n-2 個月，為避免一開始就對不到（尤其是區間開頭），讀取範圍往前多抓幾個月
    indicator_start_ts = start_ts.replace(day=1) - pd.DateOffset(months=3)
    indicator_start_yyyymmdd = _to_yyyymmdd(indicator_start_ts)
    indicator_end_yyyymmdd = _to_yyyymmdd(end_ts)
    indicator_df = load_indicator_data(db_manager, start_date=indicator_start_yyyymmdd, end_date=indicator_end_yyyymmdd)
    if indicator_df.empty:
        print("[Error] 無法讀取指標數據")
        return None
    print(f"  共讀取 {len(indicator_df)} 筆指標數據（從 {indicator_df['indicator_date'].min()} 至 {indicator_df['indicator_date'].max()}）")

    # 讀取融資維持率數據
    print("\n正在讀取融資維持率數據...")
    margin_df = load_margin_data(db_manager, start_date=_to_yyyymmdd(start_ts), end_date=_to_yyyymmdd(end_ts))
    if margin_df.empty:
        print("  [Warning] 沒有找到融資維持率數據")
    else:
        print(f"  共讀取 {len(margin_df)} 筆融資維持率數據（從 {margin_df['date'].min()} 至 {margin_df['date'].max()}）")

    # 合併數據：為每個股價日期添加對應的指標數據（n-2個月）
    print("\n正在合併數據（指標對齊：n-2個月）...")
    result_rows = []
    # indicator_df 可能包含用於回填的 cycle_* 欄位（例如 cycle_business_cycle_signal / cycle_business_cycle_score）
    # 這些欄位不需要輸出到 Orange CSV，僅用於內部回填驗證
    indicator_cols = [
        col for col in indicator_df.columns
        if col != 'indicator_date' and not str(col).startswith('cycle_')
    ]

    for idx, row in stock_data.iterrows():
        if idx % 1000 == 0:
            print(f"  處理進度：{idx}/{len(stock_data)} ({idx/len(stock_data)*100:.1f}%)")

        target_date = row['date']
        indicator_row = get_indicator_for_date(target_date, indicator_df)
        
        # 取得融資維持率數據
        margin_row = get_margin_for_date(target_date, margin_df) if not margin_df.empty else pd.Series(dtype=float)

        result_row = {
            'date': target_date.strftime('%Y-%m-%d'),
            'ticker': row['ticker'],
            'close': row['close']
        }

        for col in indicator_cols:
            result_row[col] = indicator_row.get(col, None)
        
        # 添加融資融券衍生指標欄位
        margin_derived_cols = [
            'short_margin_ratio',
            'margin_balance_change_rate',
            'margin_balance_net_change',
            'margin_buy_sell_ratio',
            'margin_buy_sell_net',
            'short_balance_change_rate',
            'short_balance_net_change',
            'short_buy_sell_ratio',
            'short_buy_sell_net'
        ]
        
        for col in margin_derived_cols:
            if not margin_row.empty and col in margin_row:
                result_row[col] = margin_row.get(col, None)
            else:
                result_row[col] = None

        result_rows.append(result_row)

    result_df = pd.DataFrame(result_rows)

    # 添加融資融券衍生指標相關特徵
    print("  計算融資融券衍生指標特徵...")
    result_df['date_dt'] = pd.to_datetime(result_df['date'], errors='coerce')
    result_df = result_df.sort_values(['ticker', 'date_dt']).reset_index(drop=True)
    
    # 計算衍生指標的滯後值和變化率
    for col in margin_derived_cols:
        if col in result_df.columns:
            result_df[f'{col}_lag1'] = result_df.groupby('ticker')[col].shift(1)
            result_df[f'{col}_lag2'] = result_df.groupby('ticker')[col].shift(2)
            result_df[f'{col}_change'] = result_df.groupby('ticker')[col].diff()
    
    # 前向填充融資融券衍生指標的缺失值（開頭數據）
    print("  前向填充融資融券衍生指標的缺失值...")
    lag_change_cols = [f'{col}_lag1' for col in margin_derived_cols if col in result_df.columns] + \
                      [f'{col}_lag2' for col in margin_derived_cols if col in result_df.columns] + \
                      [f'{col}_change' for col in margin_derived_cols if col in result_df.columns]
    for col in lag_change_cols:
        if col in result_df.columns:
            # 先前向填充（從上往下填充）
            result_df[col] = result_df.groupby('ticker')[col].ffill()
            # 再後向填充（從下往上填充，處理開頭的NaN）
            result_df[col] = result_df.groupby('ticker')[col].bfill()
    
    result_df = result_df.drop(columns=['date_dt'])

    # 確保欄位順序：date, ticker, close, 然後是指標欄位，最後是融資融券衍生指標
    margin_cols = margin_derived_cols + [f'{col}_lag1' for col in margin_derived_cols] + \
                  [f'{col}_lag2' for col in margin_derived_cols] + \
                  [f'{col}_change' for col in margin_derived_cols]
    margin_cols = [col for col in margin_cols if col in result_df.columns]
    column_order = ['date', 'ticker', 'close'] + indicator_cols + margin_cols
    result_df = result_df[column_order]

    # 特徵工程：添加日報酬率和時間特徵
    print("\n正在計算特徵工程...")
    result_df['date_dt'] = pd.to_datetime(result_df['date'], errors='coerce')
    result_df = result_df[result_df['date_dt'].notna()]
    result_df = result_df.sort_values(['ticker', 'date_dt']).reset_index(drop=True)

    print("  計算日報酬率...")
    result_df['daily_return'] = result_df.groupby('ticker')['close'].pct_change()
    
    # 前向填充日報酬率的缺失值（開頭數據）
    # 前向填充 daily_return 的缺失值（開頭數據）
    result_df['daily_return'] = result_df.groupby('ticker')['daily_return'].ffill()
    # 再後向填充（從下往上填充，處理開頭的NaN）
    result_df['daily_return'] = result_df.groupby('ticker')['daily_return'].bfill()

    print("  計算累積報酬率...")
    cumulative_returns = result_df.groupby('ticker')['daily_return'].apply(
        lambda x: (1 + x.fillna(0)).cumprod() - 1
    ).reset_index(level=0, drop=True)
    result_df['cumulative_return'] = cumulative_returns.values

    print("  添加時間特徵...")
    result_df['year'] = result_df['date_dt'].dt.year
    result_df['month'] = result_df['date_dt'].dt.month
    result_df['quarter'] = result_df['date_dt'].dt.quarter
    result_df['day_of_week'] = result_df['date_dt'].dt.dayofweek
    result_df['is_month_start'] = result_df['date_dt'].dt.is_month_start.astype(int)
    result_df['is_month_end'] = result_df['date_dt'].dt.is_month_end.astype(int)

    result_df = result_df.drop(columns=['date_dt'])

    time_features = ['year', 'month', 'quarter', 'day_of_week', 'is_month_start', 'is_month_end']
    margin_derived_cols = [
        'short_margin_ratio',
        'margin_balance_change_rate',
        'margin_balance_net_change',
        'margin_buy_sell_ratio',
        'margin_buy_sell_net',
        'short_balance_change_rate',
        'short_balance_net_change',
        'short_buy_sell_ratio',
        'short_buy_sell_net'
    ]
    margin_cols = margin_derived_cols + [f'{col}_lag1' for col in margin_derived_cols] + \
                  [f'{col}_lag2' for col in margin_derived_cols] + \
                  [f'{col}_change' for col in margin_derived_cols]
    margin_cols = [col for col in margin_cols if col in result_df.columns]
    column_order = ['date', 'ticker', 'close', 'daily_return', 'cumulative_return'] + time_features + indicator_cols + margin_cols
    result_df = result_df[column_order]

    # 將欄位名稱轉換為中文
    print("\n正在轉換欄位名稱為中文...")
    result_df = rename_columns_to_chinese(result_df)
    
    # 輸出 CSV 文件
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    print(f"\n正在輸出 CSV 文件：{output_path}")
    result_df.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n[完成] 成功輸出 {len(result_df)} 筆數據")
    print(f"  欄位數量：{len(result_df.columns)}")
    date_col = '日期' if '日期' in result_df.columns else 'date'
    ticker_col = '股票代號' if '股票代號' in result_df.columns else 'ticker'
    print(f"  日期範圍：{result_df[date_col].min()} 至 {result_df[date_col].max()}")
    print(f"  股票代號：{sorted(result_df[ticker_col].unique())}")
    print(f"\n前 5 筆數據預覽：")
    print(result_df.head())

    return output_path


def _first_valid(s: pd.Series):
    s2 = s.dropna()
    return s2.iloc[0] if len(s2) else np.nan


def _last_valid(s: pd.Series):
    s2 = s.dropna()
    return s2.iloc[-1] if len(s2) else np.nan


def export_orange_data_monthly(
    start_date: str = '2015-01-01',
    end_date: Optional[str] = None,
    tickers: Optional[Sequence[str]] = None,
    output_path: str = 'results/orange_monthly_ohlcv_with_indicators_006208_2330.csv',
    db_path: str = 'D:\\all_data\\taiwan_stock_all_data.db',
):
    """輸出月線 OHLCV + 總經指標（提前 2 個月對齊）"""
    print("\n[輸出 Orange 分析數據 - 月線 OHLCV + 指標]")
    print("-" * 60)

    start_ts = _parse_ymd(start_date)
    end_ts = _parse_ymd(end_date, default=pd.Timestamp(datetime.now()))
    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts

    tickers = _normalize_tickers(tickers)
    print(f"時間範圍：{start_ts.strftime('%Y-%m-%d')} 至 {end_ts.strftime('%Y-%m-%d')}")
    print(f"股票代號：{tickers}")

    db_manager = DatabaseManager(db_path=db_path)

    print("\n正在讀取日線股價數據（含 OHLCV）...")
    stock_data = _load_stock_data_from_db(
        db_manager,
        tickers=tickers,
        start_yyyymmdd=_to_yyyymmdd(start_ts),
        end_yyyymmdd=_to_yyyymmdd(end_ts),
        columns=['date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'turnover'],
    )
    if stock_data.empty:
        print("[Error] 無法讀取股價數據")
        return None
    print(f"  共讀取 {len(stock_data)} 筆日線資料")

    # 確保數值欄位為數值型
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        if col in stock_data.columns:
            stock_data[col] = pd.to_numeric(stock_data[col], errors='coerce')

    print("\n正在彙總為月線 OHLCV...")
    monthly_list = []
    for ticker, g in stock_data.groupby('ticker'):
        g = g.sort_values('date').set_index('date')
        # pandas 新版建議用 'ME'（month end）取代 'M'
        monthly = g.resample('ME').agg({
            'open': _first_valid,
            'high': 'max',
            'low': 'min',
            'close': _last_valid,
            'volume': 'sum',
            'turnover': 'sum'
        })
        monthly = monthly.dropna(subset=['close'])
        monthly = monthly.reset_index()
        monthly['ticker'] = ticker
        monthly_list.append(monthly)

    if not monthly_list:
        print("[Error] 月線彙總結果為空")
        return None

    monthly_df = pd.concat(monthly_list, ignore_index=True)
    monthly_df = monthly_df.sort_values(['date', 'ticker']).reset_index(drop=True)
    print(f"  產生 {len(monthly_df)} 筆月線資料")

    # 讀取指標數據（月資料）
    print("\n正在讀取指標數據...")
    # 指標對齊採 n-2 個月，為避免一開始就對不到（尤其是區間開頭），讀取範圍往前多抓幾個月
    indicator_start_ts = start_ts.replace(day=1) - pd.DateOffset(months=3)
    indicator_start_yyyymmdd = _to_yyyymmdd(indicator_start_ts)
    indicator_end_yyyymmdd = _to_yyyymmdd(end_ts)
    indicator_df = load_indicator_data(db_manager, start_date=indicator_start_yyyymmdd, end_date=indicator_end_yyyymmdd)
    if indicator_df.empty:
        print("[Error] 無法讀取指標數據")
        return None
    # indicator_df 可能包含用於回填的 cycle_* 欄位（例如 cycle_business_cycle_signal / cycle_business_cycle_score）
    # 這些欄位不需要輸出到 Orange CSV，僅用於內部回填驗證
    indicator_cols = [
        col for col in indicator_df.columns
        if col != 'indicator_date' and not str(col).startswith('cycle_')
    ]
    print(f"  共讀取 {len(indicator_df)} 筆指標數據（從 {indicator_df['indicator_date'].min()} 至 {indicator_df['indicator_date'].max()}）")

    # 讀取融資維持率數據
    print("\n正在讀取融資維持率數據...")
    margin_df = load_margin_data(db_manager, start_date=_to_yyyymmdd(start_ts), end_date=_to_yyyymmdd(end_ts))
    if margin_df.empty:
        print("  [Warning] 沒有找到融資維持率數據")
    else:
        print(f"  共讀取 {len(margin_df)} 筆融資維持率數據（從 {margin_df['date'].min()} 至 {margin_df['date'].max()}）")

    # 讀取月線技術指標數據（當天對當天）
    tech_monthly_df = load_monthly_technical_indicators(
        db_manager,
        tickers=tickers,
        start_date=_to_yyyymmdd(start_ts),
        end_date=_to_yyyymmdd(end_ts)
    )

    print("\n正在合併月線與指標（指標對齊：n-2個月）...")
    out_rows = []
    for _, row in monthly_df.iterrows():
        month_end: pd.Timestamp = row['date']
        indicator_row = get_indicator_for_date(month_end, indicator_df)
        
        # 取得融資維持率數據（使用當月最後一個交易日，當天對當天）
        margin_row = get_margin_for_date(month_end, margin_df) if not margin_df.empty else pd.Series(dtype=float)
        
        # 取得月線技術指標數據（當天對當天）
        tech_row = pd.Series(dtype=float)
        if not tech_monthly_df.empty:
            month_end_str = month_end.strftime('%Y-%m-%d')
            tech_monthly_df['date_str'] = tech_monthly_df['date'].dt.strftime('%Y-%m-%d')
            tech_match = tech_monthly_df[
                (tech_monthly_df['date_str'] == month_end_str) & 
                (tech_monthly_df['ticker'] == row['ticker'])
            ]
            if not tech_match.empty:
                tech_row = tech_match.iloc[0]

        out_row = {
            'date': month_end.strftime('%Y-%m-%d'),  # 月末標籤
            'ticker': row['ticker'],
            'open': row.get('open'),
            'high': row.get('high'),
            'low': row.get('low'),
            'close': row.get('close'),
            'volume': row.get('volume'),
            'turnover': row.get('turnover')
        }
        
        # 添加技術指標欄位（當天對當天）
        tech_columns = [
            'ma3', 'ma6', 'ma12',
            'price_vs_ma3', 'price_vs_ma6',
            'volatility_6', 'volatility_pct_6',
            'return_1m', 'return_3m', 'return_12m',
            'rsi', 'volume_ma3', 'volume_ratio'
        ]
        for col in tech_columns:
            if not tech_row.empty and col in tech_row:
                out_row[col] = tech_row.get(col, None)
            else:
                out_row[col] = None
        
        # 添加總經指標欄位（n-2個月時序移動）
        for col in indicator_cols:
            out_row[col] = indicator_row.get(col, None)
        
        # 添加融資融券衍生指標欄位（當天對當天）
        margin_derived_cols = [
            'short_margin_ratio',
            'margin_balance_change_rate',
            'margin_balance_net_change',
            'margin_buy_sell_ratio',
            'margin_buy_sell_net',
            'short_balance_change_rate',
            'short_balance_net_change',
            'short_buy_sell_ratio',
            'short_buy_sell_net'
        ]
        
        for col in margin_derived_cols:
            if not margin_row.empty and col in margin_row:
                out_row[col] = margin_row.get(col, None)
            else:
                out_row[col] = None
        
        out_rows.append(out_row)

    out_df = pd.DataFrame(out_rows)
    
    # 添加融資融券衍生指標相關特徵（滯後值和變化率）
    margin_derived_cols = [
        'short_margin_ratio',
        'margin_balance_change_rate',
        'margin_balance_net_change',
        'margin_buy_sell_ratio',
        'margin_buy_sell_net',
        'short_balance_change_rate',
        'short_balance_net_change',
        'short_buy_sell_ratio',
        'short_buy_sell_net'
    ]
    out_df = out_df.sort_values(['ticker', 'date']).reset_index(drop=True)
    for col in margin_derived_cols:
        if col in out_df.columns:
            out_df[f'{col}_lag1'] = out_df.groupby('ticker')[col].shift(1)
            out_df[f'{col}_lag2'] = out_df.groupby('ticker')[col].shift(2)
            out_df[f'{col}_change'] = out_df.groupby('ticker')[col].diff()
    
    # 前向填充融資融券衍生指標的缺失值（開頭數據）
    print("  前向填充融資融券衍生指標的缺失值...")
    lag_change_cols = [f'{col}_lag1' for col in margin_derived_cols if col in out_df.columns] + \
                      [f'{col}_lag2' for col in margin_derived_cols if col in out_df.columns] + \
                      [f'{col}_change' for col in margin_derived_cols if col in out_df.columns]
    
    for col in lag_change_cols:
        if col in out_df.columns:
            # 先前向填充（從上往下填充）
            out_df[col] = out_df.groupby('ticker')[col].ffill()
            # 再後向填充（從下往上填充，處理開頭的NaN）
            out_df[col] = out_df.groupby('ticker')[col].bfill()
    
    base_cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'turnover']
    tech_columns = [
        'ma3', 'ma6', 'ma12',
        'price_vs_ma3', 'price_vs_ma6',
        'volatility_6', 'volatility_pct_6',
        'return_1m', 'return_3m', 'return_12m',
        'rsi', 'volume_ma3', 'volume_ratio'
    ]
    tech_cols = [col for col in tech_columns if col in out_df.columns]
    margin_cols = margin_derived_cols + [f'{col}_lag1' for col in margin_derived_cols] + \
                  [f'{col}_lag2' for col in margin_derived_cols] + \
                  [f'{col}_change' for col in margin_derived_cols]
    margin_cols = [col for col in margin_cols if col in out_df.columns]
    out_df = out_df[base_cols + tech_cols + indicator_cols + margin_cols]

    # 將欄位名稱轉換為中文
    print("\n正在轉換欄位名稱為中文...")
    out_df = rename_columns_to_chinese(out_df)
    
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    print(f"\n正在輸出 CSV 文件：{output_path}")
    out_df.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n[完成] 成功輸出 {len(out_df)} 筆月線數據")
    print(f"  欄位數量：{len(out_df.columns)}")
    date_col = '日期' if '日期' in out_df.columns else 'date'
    ticker_col = '股票代號' if '股票代號' in out_df.columns else 'ticker'
    print(f"  日期範圍：{out_df[date_col].min()} 至 {out_df[date_col].max()}")
    print(f"  股票代號：{sorted(out_df[ticker_col].unique())}")
    print(f"\n前 5 筆數據預覽：")
    print(out_df.head())

    return output_path


def export_orange_data(*args, **kwargs):
    """
    向後相容：保留原函式名稱，預設輸出日線資料。
    （main.py 舊版只會呼叫 export_orange_data()）
    """
    return export_orange_data_daily(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description="輸出 Orange 分析數據（日線/彙整月線）")
    parser.add_argument('--frequency', choices=['daily', 'monthly'], default='daily', help='輸出頻率')
    parser.add_argument('--start-date', type=str, default='2015-01-01', help='起始日期（YYYY-MM-DD 或 YYYYMMDD）')
    parser.add_argument('--end-date', type=str, default=None, help='結束日期（YYYY-MM-DD 或 YYYYMMDD，預設今天）')
    parser.add_argument('--tickers', type=str, default='006208,2330', help='股票代號（逗號分隔）')
    parser.add_argument('--output', type=str, default=None, help='輸出檔案路徑（預設依 frequency）')
    parser.add_argument('--db-path', type=str, default='D:\\all_data\\taiwan_stock_all_data.db', help='SQLite 資料庫路徑')
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(',') if t.strip()]
    if args.frequency == 'monthly':
        output = args.output or 'results/orange_monthly_ohlcv_with_indicators_006208_2330.csv'
        export_orange_data_monthly(
            start_date=args.start_date,
            end_date=args.end_date,
            tickers=tickers,
            output_path=output,
            db_path=args.db_path
        )
    else:
        output = args.output or 'results/orange_analysis_data.csv'
        export_orange_data_daily(
            start_date=args.start_date,
            end_date=args.end_date,
            tickers=tickers,
            output_path=output,
            db_path=args.db_path
        )


if __name__ == '__main__':
    main()

