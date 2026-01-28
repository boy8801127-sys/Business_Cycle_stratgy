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


def load_indicator_data():
    """讀取所有指標數據（領先、同時、落後、綜合指標）"""
    base_path = 'business_cycle'
    
    # 讀取領先指標構成項目
    leading_path = os.path.join(base_path, '領先指標構成項目.csv')
    leading_df = pd.read_csv(leading_path, encoding='utf-8')
    leading_df['indicator_date'] = pd.to_datetime(leading_df['Date'], format='%Y%m')
    # 添加前綴
    leading_cols = {col: f'leading_{col}' for col in leading_df.columns if col not in ['Date', 'indicator_date']}
    leading_df = leading_df.rename(columns=leading_cols)
    
    # 讀取同時指標構成項目
    coincident_path = os.path.join(base_path, '同時指標構成項目.csv')
    coincident_df = pd.read_csv(coincident_path, encoding='utf-8')
    coincident_df['indicator_date'] = pd.to_datetime(coincident_df['Date'], format='%Y%m')
    # 添加前綴
    coincident_cols = {col: f'coincident_{col}' for col in coincident_df.columns if col not in ['Date', 'indicator_date']}
    coincident_df = coincident_df.rename(columns=coincident_cols)
    
    # 讀取落後指標構成項目
    lagging_path = os.path.join(base_path, '落後指標構成項目.csv')
    lagging_df = pd.read_csv(lagging_path, encoding='utf-8')
    lagging_df['indicator_date'] = pd.to_datetime(lagging_df['Date'], format='%Y%m')
    # 添加前綴
    lagging_cols = {col: f'lagging_{col}' for col in lagging_df.columns if col not in ['Date', 'indicator_date']}
    lagging_df = lagging_df.rename(columns=lagging_cols)
    
    # 讀取景氣指標與燈號（包含綜合指數和燈號分數）
    signal_path = os.path.join(base_path, '景氣指標與燈號.csv')
    signal_df = pd.read_csv(signal_path, encoding='utf-8')
    signal_df['indicator_date'] = pd.to_datetime(signal_df['Date'], format='%Y%m')
    # 添加前綴
    signal_cols = {col: f'signal_{col}' for col in signal_df.columns if col not in ['Date', 'indicator_date']}
    signal_df = signal_df.rename(columns=signal_cols)
    
    # 合併所有指標數據（使用 inner join 確保所有指標都有相同的日期）
    merged_indicators = leading_df.merge(
        coincident_df[['indicator_date'] + [col for col in coincident_df.columns if col.startswith('coincident_')]],
        on='indicator_date',
        how='inner'
    ).merge(
        lagging_df[['indicator_date'] + [col for col in lagging_df.columns if col.startswith('lagging_')]],
        on='indicator_date',
        how='inner'
    ).merge(
        signal_df[['indicator_date'] + [col for col in signal_df.columns if col.startswith('signal_')]],
        on='indicator_date',
        how='inner'
    )
    
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
    indicator_df = load_indicator_data()
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
    indicator_cols = [col for col in indicator_df.columns if col != 'indicator_date']

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

    # 輸出 CSV 文件
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    print(f"\n正在輸出 CSV 文件：{output_path}")
    result_df.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n[完成] 成功輸出 {len(result_df)} 筆數據")
    print(f"  欄位數量：{len(result_df.columns)}")
    print(f"  日期範圍：{result_df['date'].min()} 至 {result_df['date'].max()}")
    print(f"  股票代號：{sorted(result_df['ticker'].unique())}")
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
    indicator_df = load_indicator_data()
    indicator_cols = [col for col in indicator_df.columns if col != 'indicator_date']
    print(f"  共讀取 {len(indicator_df)} 筆指標數據（從 {indicator_df['indicator_date'].min()} 至 {indicator_df['indicator_date'].max()}）")

    # 讀取融資維持率數據
    print("\n正在讀取融資維持率數據...")
    margin_df = load_margin_data(db_manager, start_date=_to_yyyymmdd(start_ts), end_date=_to_yyyymmdd(end_ts))
    if margin_df.empty:
        print("  [Warning] 沒有找到融資維持率數據")
    else:
        print(f"  共讀取 {len(margin_df)} 筆融資維持率數據（從 {margin_df['date'].min()} 至 {margin_df['date'].max()}）")

    print("\n正在合併月線與指標（指標對齊：n-2個月）...")
    out_rows = []
    for _, row in monthly_df.iterrows():
        month_end: pd.Timestamp = row['date']
        indicator_row = get_indicator_for_date(month_end, indicator_df)
        
        # 取得融資維持率數據（使用當月最後一個交易日）
        margin_row = get_margin_for_date(month_end, margin_df) if not margin_df.empty else pd.Series(dtype=float)

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
        for col in indicator_cols:
            out_row[col] = indicator_row.get(col, None)
        
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
    
    base_cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'turnover']
    margin_cols = margin_derived_cols + [f'{col}_lag1' for col in margin_derived_cols] + \
                  [f'{col}_lag2' for col in margin_derived_cols] + \
                  [f'{col}_change' for col in margin_derived_cols]
    margin_cols = [col for col in margin_cols if col in out_df.columns]
    out_df = out_df[base_cols + indicator_cols + margin_cols]

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    print(f"\n正在輸出 CSV 文件：{output_path}")
    out_df.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\n[完成] 成功輸出 {len(out_df)} 筆月線數據")
    print(f"  欄位數量：{len(out_df.columns)}")
    print(f"  日期範圍：{out_df['date'].min()} 至 {out_df['date'].max()}")
    print(f"  股票代號：{sorted(out_df['ticker'].unique())}")
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

