"""
景氣週期投資策略回測引擎
簡化的回測框架，不依賴 Zipline
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pandas_market_calendars as pmc


class BacktestEngine:
    """景氣週期投資策略回測引擎"""
    
    def __init__(self, initial_capital=100000, commission_rate=0.001425, tax_rate=0.003):
        """
        初始化回測引擎
        
        參數:
        - initial_capital: 初始資金
        - commission_rate: 手續費率（預設 0.1425%）
        - tax_rate: 證交稅率（預設 0.3%，賣出時）
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        
        # 回測狀態
        self.cash = initial_capital
        self.positions = {}  # {ticker: shares}
        self.portfolio_value = []  # 每日投資組合價值
        self.returns = []  # 每日報酬率
        self.trades = []  # 交易記錄
        self.dates = []  # 日期列表
        
        # 景氣燈號資料
        self.cycle_data = None
        # M1B 資料
        self.m1b_data = None
        # 缺失價格警告追蹤
        self._missing_price_warnings = []
    
    def calculate_commission(self, value):
        """計算手續費"""
        commission = value * self.commission_rate
        return max(commission, 20)  # 最低 20 元
    
    def calculate_tax(self, value):
        """計算證交稅（賣出時）"""
        return value * self.tax_rate
    
    def get_trading_dates(self, start_date, end_date):
        """取得交易日列表"""
        cal = pmc.get_calendar('XTAI')
        trading_days = cal.valid_days(start_date=start_date, end_date=end_date)
        return [pd.Timestamp(day).date() for day in trading_days]
    
    def run_backtest(self, start_date, end_date, strategy_func, price_data, cycle_data, m1b_data=None):
        """
        執行回測
        
        參數:
        - start_date: 起始日期（'YYYY-MM-DD' 或 datetime）
        - end_date: 結束日期（'YYYY-MM-DD' 或 datetime）
        - strategy_func: 策略函數
        - price_data: 股價資料 DataFrame（包含 date, ticker, close）
        - cycle_data: 景氣燈號資料 DataFrame（包含 date, score, val_shifted）
        - m1b_data: M1B 資料 DataFrame（可選，包含 date, m1b_yoy_month, m1b_yoy_momentum, m1b_mom, m1b_vs_3m_avg）
        
        回傳:
        - 回測結果字典
        """
        # 轉換日期格式
        if isinstance(start_date, str):
            start_date = pd.Timestamp(start_date).date()
        if isinstance(end_date, str):
            end_date = pd.Timestamp(end_date).date()
        
        # 取得交易日列表
        trading_days = self.get_trading_dates(start_date, end_date)
        
        print(f"[Info] 開始回測：{start_date} 至 {end_date}")
        print(f"[Info] 交易日數：{len(trading_days)} 天")
        print(f"[Info] 初始資金：{self.initial_capital:,.0f} 元")
        
        # 準備資料
        self.cycle_data = cycle_data.copy()
        # 處理 date 欄位：轉換為 date 對象
        if 'date' in self.cycle_data.columns:
            try:
                # cycle_data 的 date 欄位已經是 pd.Timestamp 類型（datetime64）
                # 直接轉換為 date 對象（.dt.date 是屬性，返回 date 對象的 Series）
                date_col = self.cycle_data['date']
                # 檢查是否已經是 datetime 類型
                if str(date_col.dtype).startswith('datetime'):
                    self.cycle_data['date'] = date_col.dt.date
                else:
                    # 如果不是 datetime，先轉換
                    self.cycle_data['date'] = pd.to_datetime(date_col, errors='coerce').dt.date
            except Exception as e:
                print(f"[Warning] cycle_data 日期轉換失敗: {e}")
                # 如果轉換失敗，嘗試直接使用（可能是已經是 date 類型）
                pass
        self.cycle_data = self.cycle_data.set_index('date')
        
        # 準備 M1B 資料（如果提供）
        if m1b_data is not None and not m1b_data.empty:
            self.m1b_data = m1b_data.copy()
            # 確保 date 欄位存在
            if 'date' in self.m1b_data.columns:
                # M1B 資料的 date 欄位是字串格式（YYYYMMDD）
                try:
                    date_col = self.m1b_data['date']
                    # 檢查是否已經是 datetime 類型
                    if str(date_col.dtype).startswith('datetime'):
                        self.m1b_data['date'] = date_col.dt.date
                    else:
                        # 從 YYYYMMDD 字串格式轉換
                        self.m1b_data['date'] = pd.to_datetime(date_col, format='%Y%m%d', errors='coerce').dt.date
                    self.m1b_data = self.m1b_data.set_index('date')
                except Exception as e:
                    print(f"[Warning] M1B 資料日期轉換失敗: {e}")
                    import traceback
                    traceback.print_exc()
                    self.m1b_data = None
        else:
            self.m1b_data = None
        
        # 初始化策略狀態
        strategy_state = {
            'state': False,  # 是否持有股票
            'hedge_state': False,  # 是否持有避險資產
            'score': None,
            'prev_score': None,  # 上月景氣分數（用於計算分數動能）
            'a': 0,  # 是否已進入景氣循環
            'm1b_yoy_month': None,  # M1B 年增率
            'm1b_yoy_momentum': None,  # M1B 動能
            'm1b_mom': None,  # M1B 月對月變化率
            'm1b_vs_3m_avg': None,  # M1B vs 前三個月平均
            'score_momentum': None,  # 景氣分數動能
            'is_first_trading_day': False,  # 是否為當月第一個交易日
            'is_last_trading_day': False,  # 是否為當月最後一個交易日
            'should_buy_on_first_day': False,  # 是否應在當月第一個交易日買進
            'should_sell_on_last_day': False  # 是否應在當月最後一個交易日賣出
        }
        
        # 用於追蹤上一個月的景氣分數（用於計算動能）
        prev_month_score = None
        prev_month_date = None
        
        # 預先計算每個月的第一個和最後一個交易日
        month_first_trading_day = {}  # {(year, month): first_trading_day}
        month_last_trading_day = {}   # {(year, month): last_trading_day}
        
        current_month_key = None
        for date in trading_days:
            month_key = (date.year, date.month)
            if month_key not in month_first_trading_day:
                month_first_trading_day[month_key] = date
            month_last_trading_day[month_key] = date
        
        # 追蹤燈號發布和變化（新邏輯：燈號發布後交易）
        prev_published_score = None  # 前一個發布的燈號分數
        prev_published_date = None  # 前一個發布日期
        prev_published_year = None  # 前一個發布的燈號年份
        prev_published_month = None  # 前一個發布的燈號月份
        prev_date = None  # 上一個交易日
        current_month_key = None
        prev_month_key = None
        
        # 買進/賣出標記
        need_buy_after_publish = False  # 標記是否需要買進（藍燈發布後）
        buy_start_date = None  # 買進開始日期（發布後的5個交易日）
        buy_signal_year = None  # 買進信號的燈號年份
        buy_signal_month = None  # 買進信號的燈號月份
        buy_signal_score = None  # 買進信號的燈號分數
        
        need_sell_next_month = False  # 標記是否需要賣出（紅燈發布後，隔月賣出）
        sell_month = None  # 賣出月份（隔月）
        sell_signal_year = None  # 賣出信號的燈號年份
        sell_signal_month = None  # 賣出信號的燈號月份
        sell_signal_score = None  # 賣出信號的燈號分數
        
        # 當前使用的燈號資訊（用於交易記錄）
        current_signal_year = None
        current_signal_month = None
        current_signal_score = None
        
        # 分批執行追蹤機制
        buy_split_orders = {}  # {ticker: {'total_percent': float, 'executed_percent': float, 'days_remaining': int, 'start_date': date}}
        sell_split_orders = {}  # 同上
        grid_split_orders = {}  # {(ticker, action): {'total_percent': float, 'executed_percent': float, 'days_remaining': int, 'start_date': date}}
        
        # 預先計算每個月的前5個交易日和第四個禮拜的5個交易日（用於分批執行）
        month_first_five_days = {}  # {(year, month): [date1, date2, date3, date4, date5]}
        month_fourth_week_five_days = {}  # {(year, month): [date1, date2, date3, date4, date5]}
        
        for month_key in month_first_trading_day.keys():
            # 計算前5個交易日
            first_day = month_first_trading_day[month_key]
            month_trading_days = [d for d in trading_days if (d.year, d.month) == month_key]
            if len(month_trading_days) >= 5:
                month_first_five_days[month_key] = month_trading_days[:5]
            else:
                # 如果交易日不足5天，使用所有交易日
                month_first_five_days[month_key] = month_trading_days
            
            # 計算第四個禮拜開始的5個交易日（從最後一個交易日回推5天）
            if month_trading_days:
                # 從最後一個交易日往前取5個交易日
                # pandas_market_calendars 已經自動處理了假日和特殊休市日（如颱風假），
                # 所以 trading_days 只包含實際的交易日，不需要額外處理「順延」邏輯
                if len(month_trading_days) >= 5:
                    # 從最後往前取5個交易日
                    month_fourth_week_five_days[month_key] = month_trading_days[-5:]
                else:
                    # 如果當月交易日不足5天，繼續到下個月的交易日補足
                    remaining_days = 5 - len(month_trading_days)
                    if remaining_days > 0:
                        # 計算下個月的月份鍵
                        next_month = (month_key[0] + (1 if month_key[1] == 12 else 0),
                                    (month_key[1] % 12) + 1)
                        next_month_days = [d for d in trading_days 
                                         if (d.year, d.month) == next_month]
                        if next_month_days:
                            # 當月的最後幾天 + 下個月的前幾天
                            month_fourth_week_five_days[month_key] = (
                                month_trading_days + next_month_days[:remaining_days]
                            )
                        else:
                            # 如果下個月也沒有交易日，只使用當月的
                            month_fourth_week_five_days[month_key] = month_trading_days
                    else:
                        month_fourth_week_five_days[month_key] = month_trading_days
            else:
                month_fourth_week_five_days[month_key] = []
        
        # 每日迭代
        for i, date in enumerate(trading_days):
            # 取得當日景氣燈號資料
            score = None
            publish_date = None
            data_year = None
            data_month = None
            
            if date in self.cycle_data.index:
                row = self.cycle_data.loc[date]
                score = row.get('score')
                publish_date = row.get('publish_date')
                data_year = row.get('data_year')
                data_month = row.get('data_month')
            else:
                # 如果找不到當日資料，使用前一個有效日期的資料
                try:
                    prev_date = max([d for d in self.cycle_data.index if d <= date])
                    row = self.cycle_data.loc[prev_date]
                    score = row.get('score')
                    publish_date = row.get('publish_date')
                    data_year = row.get('data_year')
                    data_month = row.get('data_month')
                except:
                    pass
            
            if score is None:
                # 如果沒有景氣燈號資料，跳過
                continue
            
            # 更新景氣分數
            strategy_state['score'] = score
            current_signal_year = data_year
            current_signal_month = data_month
            current_signal_score = score
            
            # 追蹤月份變化（用於計算動能）
            current_month_key = (date.year, date.month)
            
            # 檢測燈號發布（發布日期是N+1月27日）
            if publish_date is not None:
                # 將publish_date轉換為date對象進行比較
                if isinstance(publish_date, pd.Timestamp):
                    publish_date_date = publish_date.date()
                elif isinstance(publish_date, datetime):
                    publish_date_date = publish_date.date()
                else:
                    publish_date_date = pd.Timestamp(publish_date).date()
                
                # 檢查是否為發布日期（或發布日期之後的第一個交易日）
                if date >= publish_date_date:
                    # 檢測燈號變化
                    if prev_published_score is not None:
                        # 檢測買進信號：從非藍燈變成藍燈
                        prev_was_blue = 9 <= prev_published_score <= 16
                        current_is_blue = 9 <= score <= 16
                        
                        # 添加調試日誌
                        if date.year >= 2021:  # 只記錄 2021 年後的日誌
                            print(f"[DEBUG] {date.strftime('%Y-%m-%d')} 信號檢測: prev_score={prev_published_score}, current_score={score}, prev_was_blue={prev_was_blue}, current_is_blue={current_is_blue}")
                        
                        if not prev_was_blue and current_is_blue:
                            # 添加調試日誌
                            print(f"[DEBUG] {date.strftime('%Y-%m-%d')} 觸發藍燈買進信號！設置 need_buy_after_publish=True")
                            # 觸發買進：在發布後的5個交易日執行
                            # 重置賣出標記（如果有的話）
                            need_sell_next_month = False
                            sell_month = None
                            need_buy_after_publish = True
                            buy_start_date = date  # 從發布日期開始
                            buy_signal_year = data_year
                            buy_signal_month = data_month
                            buy_signal_score = score
                        
                        # 檢測賣出信號：從非紅燈變成紅燈
                        prev_was_red = prev_published_score >= 38
                        current_is_red = score >= 38
                        
                        if not prev_was_red and current_is_red:
                            # 觸發賣出：在隔月的最後5個交易日執行
                            # 重置買進標記（如果有的話）
                            need_buy_after_publish = False
                            buy_start_date = None
                            need_sell_next_month = True
                            # 計算隔月（發布月份的下一個月）
                            if isinstance(publish_date, pd.Timestamp):
                                sell_month = (publish_date.year, publish_date.month + 1 if publish_date.month < 12 else (publish_date.year + 1, 1))
                            else:
                                pub_date = pd.Timestamp(publish_date)
                                sell_month = (pub_date.year, pub_date.month + 1 if pub_date.month < 12 else (pub_date.year + 1, 1))
                            sell_signal_year = data_year
                            sell_signal_month = data_month
                            sell_signal_score = score
                    
                    # 更新前一個發布的燈號
                    prev_published_score = score
                    prev_published_date = date
                    prev_published_year = data_year
                    prev_published_month = data_month
            
            # 計算分數動能（用於策略判斷）
            if prev_month_key is not None and current_month_key != prev_month_key:
                # 跨月了，計算動能
                if prev_month_score is not None and score is not None:
                    strategy_state['score_momentum'] = score - prev_month_score
                prev_month_score = score
                prev_month_date = date
                prev_month_key = current_month_key
            elif prev_month_key is None:
                # 第一次，初始化
                prev_month_key = current_month_key
                prev_month_score = score
                prev_month_date = date
                strategy_state['score_momentum'] = None
            else:
                # 同一個月內，動能保持不變
                pass
            
            # 更新上一個交易日
            prev_date = date
            
            # 取得 M1B 資料（如果可用）
            if self.m1b_data is not None:
                # M1B 是月資料，需要找到對應的月份資料
                m1b_row = None
                if date in self.m1b_data.index:
                    m1b_row = self.m1b_data.loc[date]
                else:
                    # 如果找不到當日資料，使用前一個有效日期的資料
                    try:
                        prev_m1b_date = max([d for d in self.m1b_data.index if d <= date])
                        m1b_row = self.m1b_data.loc[prev_m1b_date]
                    except:
                        pass
                
                if m1b_row is not None:
                    strategy_state['m1b_yoy_month'] = m1b_row.get('m1b_yoy_month')
                    strategy_state['m1b_yoy_momentum'] = m1b_row.get('m1b_yoy_momentum')
                    strategy_state['m1b_mom'] = m1b_row.get('m1b_mom')
                    strategy_state['m1b_vs_3m_avg'] = m1b_row.get('m1b_vs_3m_avg')
            
            # 取得當日股價資料
            date_str = date.strftime('%Y%m%d')
            date_price_data = price_data[price_data['date'] == date_str].copy()
            
            if date_price_data.empty:
                # 如果沒有股價資料，跳過
                continue
            
            # 確認有股價資料後，才添加日期（確保 dates、portfolio_value、returns 長度一致）
            self.dates.append(date)
            
            # 建立價格字典
            price_dict = {}
            for _, row in date_price_data.iterrows():
                price_dict[row['ticker']] = row['close']
            
            # 檢查是否為特定交易日期（第一個或最後一個交易日）
            is_first_trading_day = month_first_trading_day.get(current_month_key) == date
            is_last_trading_day = month_last_trading_day.get(current_month_key) == date
            
            # 計算買進窗口（發布後的5個交易日）
            should_buy_in_split = False
            buy_split_day = None
            if need_buy_after_publish and buy_start_date is not None:
                # 找到發布日期之後的5個交易日
                future_days = [d for d in trading_days if d >= buy_start_date]
                if len(future_days) >= 5:
                    buy_window = future_days[:5]
                else:
                    buy_window = future_days
                
                if date in buy_window:
                    should_buy_in_split = True
                    try:
                        buy_split_day = buy_window.index(date) + 1  # 1-5
                    except ValueError:
                        buy_split_day = None
                    # 添加調試日誌
                    if date.year >= 2021:
                        print(f"[DEBUG] {date.strftime('%Y-%m-%d')} 在買進窗口內，should_buy_in_split=True, buy_split_day={buy_split_day}")
                else:
                    # 買進窗口已結束，重置標記
                    if buy_window and date > buy_window[-1]:
                        # 添加調試日誌
                        if date.year >= 2021:
                            print(f"[DEBUG] {date.strftime('%Y-%m-%d')} 買進窗口已結束（窗口結束日期={buy_window[-1]}），重置 need_buy_after_publish=False")
                        need_buy_after_publish = False
                        buy_start_date = None
                    elif date.year >= 2021 and buy_window:
                        print(f"[DEBUG] {date.strftime('%Y-%m-%d')} 不在買進窗口內，窗口結束日期={buy_window[-1]}")
            
            # 計算賣出窗口（隔月的最後5個交易日）
            should_sell_in_split = False
            sell_split_day = None
            if need_sell_next_month and sell_month is not None:
                # 找到隔月的最後5個交易日
                sell_month_days = [d for d in trading_days if (d.year, d.month) == sell_month]
                if len(sell_month_days) >= 5:
                    sell_window = sell_month_days[-5:]
                else:
                    # 如果當月交易日不足5天，繼續到下個月的交易日補足
                    remaining_days = 5 - len(sell_month_days)
                    if remaining_days > 0:
                        next_month = (sell_month[0] + (1 if sell_month[1] == 12 else 0),
                                    (sell_month[1] % 12) + 1)
                        next_month_days = [d for d in trading_days 
                                         if (d.year, d.month) == next_month]
                        if next_month_days:
                            sell_window = sell_month_days + next_month_days[:remaining_days]
                        else:
                            sell_window = sell_month_days
                    else:
                        sell_window = sell_month_days
                
                if date in sell_window:
                    should_sell_in_split = True
                    try:
                        sell_split_day = sell_window.index(date) + 1  # 1-5
                    except ValueError:
                        sell_split_day = None
                else:
                    # 賣出窗口已結束，重置標記
                    if sell_month is not None:
                        # 檢查是否已經過了賣出月份（考慮跨月情況）
                        sell_window_end_date = sell_window[-1] if sell_window else None
                        if sell_window_end_date and date > sell_window_end_date:
                            need_sell_next_month = False
                            sell_month = None
                        elif (date.year, date.month) > sell_month:
                            # 如果當前日期已經超過賣出月份，也重置
                            need_sell_next_month = False
                            sell_month = None
            
            # 檢查是否在前5個或第四個禮拜的交易日內（用於其他策略的分批執行）
            is_in_first_five_days = date in month_first_five_days.get(current_month_key, [])
            # 檢查是否在第四個禮拜的交易日內（可能跨月）
            is_in_fourth_week_five_days = (date in month_fourth_week_five_days.get(current_month_key, []) or
                                           date in month_fourth_week_five_days.get(prev_month_key, []))
            
            # 定義需要買進/賣出的標記（基於新邏輯，用於向後相容）
            need_buy_this_month = need_buy_after_publish and should_buy_in_split
            need_sell_this_month = need_sell_next_month and should_sell_in_split
            
            # 保存當前使用的燈號資訊（用於交易記錄）- 移到這裡，在使用 should_buy_in_split 和 should_sell_in_split 之後
            self._current_signal_year = current_signal_year
            self._current_signal_month = current_signal_month
            self._current_signal_score = current_signal_score
            self._buy_signal_year = buy_signal_year if need_buy_this_month else None
            self._buy_signal_month = buy_signal_month if need_buy_this_month else None
            self._buy_signal_score = buy_signal_score if need_buy_this_month else None
            self._sell_signal_year = sell_signal_year if need_sell_this_month else None
            self._sell_signal_month = sell_signal_month if need_sell_this_month else None
            self._sell_signal_score = sell_signal_score if need_sell_this_month else None
            
            # 在 strategy_state 中設置交易時機標記
            strategy_state['is_first_trading_day'] = is_first_trading_day
            strategy_state['is_last_trading_day'] = is_last_trading_day
            strategy_state['should_buy_in_split'] = should_buy_in_split
            strategy_state['should_sell_in_split'] = should_sell_in_split
            strategy_state['buy_split_day'] = buy_split_day
            strategy_state['sell_split_day'] = sell_split_day
            # 保留舊的標記以向後相容（用於其他策略）
            strategy_state['should_buy_on_first_day'] = False
            strategy_state['should_sell_on_last_day'] = False
            
            # 執行策略（先執行策略以取得ticker資訊）
            # 為等比例配置策略提供持倉資訊
            portfolio_value_before = self._calculate_portfolio_value(date, price_dict)
            # 保存策略狀態以供交易記錄使用（濾網參數等）
            self._current_strategy_state = strategy_state.copy()
            # 添加調試日誌
            if date.year >= 2021 and (need_buy_this_month or need_sell_this_month):
                print(f"[DEBUG] {date.strftime('%Y-%m-%d')} 策略執行前: need_buy_this_month={need_buy_this_month}, need_sell_this_month={need_sell_this_month}, need_buy_after_publish={need_buy_after_publish}, need_sell_next_month={need_sell_next_month}, should_buy_in_split={should_buy_in_split}, should_sell_in_split={should_sell_in_split}, state['state']={strategy_state.get('state', 'None')}, score={strategy_state.get('score', 'None')}")
            orders = strategy_func(strategy_state, date, price_dict, self.positions, portfolio_value_before)
            # 添加調試日誌
            if date.year >= 2021 and (need_buy_this_month or need_sell_this_month):
                print(f"[DEBUG] {date.strftime('%Y-%m-%d')} 策略執行後: 產生 {len(orders)} 筆訂單, state['state']={strategy_state.get('state', 'None')}")
            
            # 處理分批執行和策略產生的訂單
            orders_to_execute = []
            
            # 檢查是否有待執行的分批訂單（基本策略）
            # 買進分批：從發布日期開始的5個交易日內
            for ticker in list(buy_split_orders.keys()):
                if ticker in price_dict and should_buy_in_split:
                    split_order = buy_split_orders[ticker]
                    if split_order['days_remaining'] > 0:
                        # 計算今天要執行的比例
                        # 使用買進窗口的總天數
                        if buy_start_date is not None:
                            future_days = [d for d in trading_days if d >= buy_start_date]
                            if len(future_days) >= 5:
                                buy_window = future_days[:5]
                            else:
                                buy_window = future_days
                            total_days = len(buy_window)
                        else:
                            total_days = len(month_first_five_days.get(current_month_key, []))
                        
                        if total_days > 0:
                            # 計算今天要執行的比例
                            if split_order['days_remaining'] == 1:
                                # 最後一天：執行剩餘的所有比例
                                today_percent = split_order['total_percent'] - split_order['executed_percent']
                            else:
                                # 其他天：平均分配
                                today_percent = split_order['total_percent'] / total_days
                        else:
                            # 如果沒有計算出交易日，使用預設5天
                            if split_order['days_remaining'] == 1:
                                today_percent = split_order['total_percent'] - split_order['executed_percent']
                            else:
                                today_percent = split_order['total_percent'] / 5
                        
                        orders_to_execute.append({
                            'action': 'buy',
                            'ticker': ticker,
                            'percent': today_percent,
                            'is_split_order': True,
                            'trade_step': split_order.get('trade_step')  # 保留原始交易步驟
                        })
                        
                        # 更新進度
                        split_order['executed_percent'] += today_percent
                        split_order['days_remaining'] -= 1
                        if split_order['days_remaining'] == 0:
                            del buy_split_orders[ticker]
            
            # 賣出分批：在第四個禮拜的5個交易日內
            for ticker in list(sell_split_orders.keys()):
                if ticker in price_dict and ticker in self.positions and self.positions[ticker] > 0 and should_sell_in_split:
                    split_order = sell_split_orders[ticker]
                    if split_order['days_remaining'] > 0:
                        # 計算今天要執行的比例
                        fourth_week_days = month_fourth_week_five_days.get(current_month_key, [])
                        if date not in fourth_week_days and prev_month_key:
                            fourth_week_days = month_fourth_week_five_days.get(prev_month_key, [])
                        total_days = len(fourth_week_days) if fourth_week_days else split_order.get('initial_days', 5)
                        if total_days > 0:
                            today_percent = split_order['total_percent'] / total_days
                        else:
                            today_percent = split_order['total_percent']
                        
                        sell_order = {
                            'action': 'sell',
                            'ticker': ticker,
                            'percent': today_percent,
                            'is_split_order': True,
                            'trade_step': split_order.get('trade_step')  # 保留原始交易步驟
                        }
                        
                        # 檢查是否需要同步買進避險資產
                        hedge_ticker = split_order.get('hedge_ticker')
                        if hedge_ticker and hedge_ticker in price_dict:
                            sell_order['trigger_hedge_buy'] = True
                            sell_order['hedge_ticker'] = hedge_ticker
                            # 從原始訂單中獲取避險資產的交易步驟（如果有）
                            sell_order['hedge_trade_step'] = split_order.get('hedge_trade_step')
                        
                        orders_to_execute.append(sell_order)
                        
                        # 更新進度
                        split_order['executed_percent'] += today_percent
                        split_order['days_remaining'] -= 1
                        if split_order['days_remaining'] == 0:
                            del sell_split_orders[ticker]
            
            # 處理策略產生的訂單
            if orders:
                for order in orders:
                    ticker = order.get('ticker')
                    action = order.get('action')
                    percent = order.get('percent', 0)
                    is_hedge_buy = order.get('is_hedge_buy', False)
                    is_synced_split = order.get('is_synced_split', False)
                    trigger_hedge_buy = order.get('trigger_hedge_buy', False)
                    is_hedge_sell = order.get('is_hedge_sell', False)
                    
                    # 檢查訂單是否需要分批執行（根據 split_execution 標記）
                    if order.get('split_execution', False):
                        if action == 'buy' and should_buy_in_split:
                            # 這是需要分批執行的買進訂單
                            if ticker not in buy_split_orders:
                                # 初始化分批訂單（只在分批時間窗口內的第一天）
                                if buy_start_date is not None:
                                    future_days = [d for d in trading_days if d >= buy_start_date]
                                    if len(future_days) >= 5:
                                        buy_window = future_days[:5]
                                    else:
                                        buy_window = future_days
                                    total_days = len(buy_window)
                                else:
                                    total_days = len(month_first_five_days.get(current_month_key, []))
                                
                                if total_days == 0:
                                    total_days = 5  # 預設5天
                                
                                buy_split_orders[ticker] = {
                                    'total_percent': percent,
                                    'executed_percent': 0.0,
                                    'days_remaining': total_days,
                                    'start_date': date,
                                    'trade_step': order.get('trade_step')  # 保存原始交易步驟
                                }
                            # 如果不在分批時間窗口內，忽略這個訂單（因為我們已經在分批執行）
                            if ticker not in buy_split_orders or not should_buy_in_split:
                                continue
                            # 分批執行邏輯在上面已經處理，這裡跳過
                            continue
                    
                        elif action == 'sell' and is_hedge_sell and should_buy_in_split:
                            # 避險資產的賣出也要分批執行（在藍燈買進股票時）
                            if ticker not in sell_split_orders:
                                # 初始化分批訂單（只在分批時間窗口內的第一天）
                                if buy_start_date is not None:
                                    future_days = [d for d in trading_days if d >= buy_start_date]
                                    if len(future_days) >= 5:
                                        buy_window = future_days[:5]
                                    else:
                                        buy_window = future_days
                                    total_days = len(buy_window)
                                else:
                                    total_days = len(month_first_five_days.get(current_month_key, []))
                                
                                if total_days == 0:
                                    total_days = 5  # 預設5天
                                
                                sell_split_orders[ticker] = {
                                    'total_percent': percent,
                                    'executed_percent': 0.0,
                                    'days_remaining': total_days,
                                    'start_date': date,
                                    'is_hedge_sell': True,
                                    'trade_step': order.get('trade_step')  # 保存原始交易步驟
                                }
                            # 如果不在分批時間窗口內，忽略這個訂單（因為我們已經在分批執行）
                            if ticker not in sell_split_orders or not should_buy_in_split:
                                continue
                            # 分批執行邏輯在上面已經處理，這裡跳過
                            continue
                    
                        elif action == 'sell' and should_sell_in_split and trigger_hedge_buy:
                            # 處理基本策略的賣出信號（需要同步買進避險資產）
                            # 股票賣出分批執行（第四個禮拜開始）
                            if ticker not in sell_split_orders and should_sell_in_split:
                                fourth_week_days = month_fourth_week_five_days.get(current_month_key, [])
                                if date not in fourth_week_days and prev_month_key:
                                    fourth_week_days = month_fourth_week_five_days.get(prev_month_key, [])
                                total_days = len(fourth_week_days) if fourth_week_days else 5
                                
                                # 同時記錄需要同步買進的避險資產ticker和交易步驟
                                hedge_ticker = None
                                hedge_trade_step = None
                                for o in orders:
                                    if o.get('is_hedge_buy', False) and o.get('is_synced_split', False):
                                        hedge_ticker = o.get('ticker')
                                        hedge_trade_step = o.get('trade_step')
                                        break
                                
                                sell_split_orders[ticker] = {
                                    'total_percent': percent,
                                    'executed_percent': 0.0,
                                    'days_remaining': total_days,
                                    'start_date': date,
                                    'initial_days': total_days,
                                    'trade_step': order.get('trade_step'),  # 保存原始交易步驟
                                    'hedge_trade_step': hedge_trade_step  # 保存避險資產交易步驟
                                }
                                
                                if hedge_ticker:
                                    sell_split_orders[ticker]['hedge_ticker'] = hedge_ticker
                            
                            # 同時初始化避險資產的買進分批訂單（從同一個orders列表中尋找）
                            hedge_ticker = sell_split_orders.get(ticker, {}).get('hedge_ticker')
                            if not hedge_ticker:
                                for o in orders:
                                    if o.get('is_hedge_buy', False) and o.get('is_synced_split', False):
                                        hedge_ticker = o.get('ticker')
                                        break
                            
                            if hedge_ticker and hedge_ticker not in buy_split_orders and should_sell_in_split:
                                fourth_week_days = month_fourth_week_five_days.get(current_month_key, [])
                                if date not in fourth_week_days and prev_month_key:
                                    fourth_week_days = month_fourth_week_five_days.get(prev_month_key, [])
                                total_days = len(fourth_week_days) if fourth_week_days else 5
                                # 從賣出訂單中獲取避險資產的交易步驟
                                hedge_trade_step = sell_split_orders.get(ticker, {}).get('hedge_trade_step')
                                if not hedge_trade_step:
                                    # 如果沒有，從原始訂單中尋找
                                    for o in orders:
                                        if o.get('is_hedge_buy', False) and o.get('is_synced_split', False):
                                            hedge_trade_step = o.get('trade_step')
                                            break
                                
                                buy_split_orders[hedge_ticker] = {
                                    'total_percent': 1.0,
                                    'executed_percent': 0.0,
                                    'days_remaining': total_days,
                                    'start_date': date,
                                    'is_hedge_buy': True,
                                    'synced_with_sell': ticker,  # 記錄與哪個ticker同步
                                    'initial_days': total_days,
                                    'trade_step': hedge_trade_step  # 保存避險資產交易步驟
                                }
                            
                            # 如果不在分批時間窗口內，忽略這個訂單（因為我們已經在分批執行）
                            if ticker not in sell_split_orders or not should_sell_in_split:
                                continue
                            # 分批執行邏輯在上面已經處理，這裡跳過
                            continue
                    
                    # 處理避險資產的同步買進（已經在上面處理，這裡跳過）
                    if is_hedge_buy and is_synced_split:
                        continue
                    
                        elif action == 'sell' and should_sell_in_split:
                            # 處理一般賣出信號（不需要觸發避險資產買進的情況）
                            # 這是基本策略的賣出信號，需要分批執行（第四個禮拜開始）
                            if ticker not in sell_split_orders and should_sell_in_split:
                                # 初始化分批訂單（只在分批時間窗口內的第一天）
                                fourth_week_days = month_fourth_week_five_days.get(current_month_key, [])
                                if date not in fourth_week_days and prev_month_key:
                                    fourth_week_days = month_fourth_week_five_days.get(prev_month_key, [])
                                total_days = len(fourth_week_days) if fourth_week_days else 5
                                sell_split_orders[ticker] = {
                                    'total_percent': percent,
                                    'executed_percent': 0.0,
                                    'days_remaining': total_days,
                                    'start_date': date,
                                    'initial_days': total_days,
                                    'trade_step': order.get('trade_step')  # 保存原始交易步驟
                                }
                            # 如果不在分批時間窗口內，忽略這個訂單（因為我們已經在分批執行）
                            if ticker not in sell_split_orders or not should_sell_in_split:
                                continue
                            # 分批執行邏輯在上面已經處理，這裡跳過
                            continue
                    
                    # 檢查是否為網格式策略的倉位調整（也需要分批執行）
                    # 網格式策略：倉位調整（percent通常在0.05-0.95之間）
                    if abs(percent) > 0.05 and percent < 0.9:
                        # 這是網格式策略的倉位調整，需要分批執行
                        order_key = (ticker, action)
                        if order_key not in grid_split_orders:
                            # 初始化分批訂單
                            grid_split_orders[order_key] = {
                                'total_percent': percent,
                                'executed_percent': 0.0,
                                'days_remaining': 5,  # 網格式策略固定5天
                                'start_date': date,
                                'trade_step': order.get('trade_step')  # 保存原始交易步驟
                            }
                        
                        # 執行當天的部分
                        split_order = grid_split_orders[order_key]
                        if split_order['days_remaining'] > 0:
                            today_percent = split_order['total_percent'] / 5
                            orders_to_execute.append({
                                'action': action,
                                'ticker': ticker,
                                'percent': today_percent,
                                'is_split_order': True,
                                'trade_step': split_order.get('trade_step')  # 保留原始交易步驟
                            })
                            
                            split_order['executed_percent'] += today_percent
                            split_order['days_remaining'] -= 1
                            if split_order['days_remaining'] == 0:
                                del grid_split_orders[order_key]
                        continue
                    
                    # 其他訂單直接執行（例如：小額調整、避險資產買賣等）
                    orders_to_execute.append(order)
            
            # 執行所有訂單
            for order in orders_to_execute:
                self._execute_order(order, date, price_dict)
            
            # 計算投資組合價值
            portfolio_value = self._calculate_portfolio_value(date, price_dict)
            self.portfolio_value.append(portfolio_value)
            
            # 計算報酬率
            if i == 0:
                self.returns.append(0.0)
            else:
                prev_value = self.portfolio_value[-2] if len(self.portfolio_value) > 1 else self.initial_capital
                daily_return = (portfolio_value - prev_value) / prev_value
                self.returns.append(daily_return)
        
        # 計算績效指標
        metrics = self._calculate_metrics()
        
        # 輸出缺失價格警告摘要
        if hasattr(self, '_missing_price_warnings') and self._missing_price_warnings:
            missing_by_ticker = {}
            for warning in self._missing_price_warnings:
                ticker = warning['ticker']
                if ticker not in missing_by_ticker:
                    missing_by_ticker[ticker] = []
                missing_by_ticker[ticker].append(warning)
            
            print(f"\n[Warning] 共有 {len(self._missing_price_warnings)} 筆訂單因缺少價格資料而被跳過：")
            for ticker, warnings in missing_by_ticker.items():
                print(f"  {ticker}: {len(warnings)} 筆（首次發生日期：{warnings[0]['date'].strftime('%Y-%m-%d')}）")
        
        # 計算最終持倉資訊
        final_positions = {}
        if self.dates and price_data is not None and len(self.dates) > 0:
            last_date = self.dates[-1]
            last_date_str = last_date.strftime('%Y%m%d')
            last_price_data = price_data[price_data['date'] == last_date_str]
            
            for ticker, shares in self.positions.items():
                ticker_prices = last_price_data[last_price_data['ticker'] == ticker]
                if not ticker_prices.empty:
                    price = ticker_prices.iloc[0]['close']
                    final_positions[ticker] = {
                        'shares': shares,
                        'price': price,
                        'value': shares * price
                    }
                else:
                    # 如果最後一天沒有價格，使用最後一個有效價格
                    ticker_prices = price_data[price_data['ticker'] == ticker]
                    if not ticker_prices.empty:
                        price = ticker_prices.iloc[-1]['close']
                        final_positions[ticker] = {
                            'shares': shares,
                            'price': price,
                            'value': shares * price
                        }
        
        return {
            'dates': self.dates,
            'portfolio_value': self.portfolio_value,
            'returns': self.returns,
            'trades': self.trades,
            'metrics': metrics,
            'final_value': self.portfolio_value[-1] if self.portfolio_value else self.initial_capital,
            'total_return': (self.portfolio_value[-1] - self.initial_capital) / self.initial_capital if self.portfolio_value else 0,
            'final_positions': final_positions,  # 新增
            'final_cash': self.cash,  # 新增
            'positions': self.positions  # 新增（簡化版，只有股數）
        }
    
    def _format_trade_step(self, trade_step, is_hedge=False):
        """
        格式化交易步驟字串
        
        參數:
        - trade_step: 交易步驟字典 {'reason': str, 'conditions': [{'name': str, 'value': float}, ...]}
        - is_hedge: 是否為避險資產交易
        
        回傳:
        - 格式化的交易步驟字串，例如：「藍燈買進 | 景氣燈號分數: 12.0 | M1B動能: -0.5」
        """
        if not trade_step:
            if is_hedge:
                return '同步買進避險資產'
            return '未知原因'
        
        reason = trade_step.get('reason', '未知原因')
        conditions = trade_step.get('conditions', [])
        
        if not conditions:
            return reason
        
        # 格式化條件字串
        condition_strs = []
        for condition in conditions:
            name = condition.get('name', '')
            value = condition.get('value')
            
            if name and value is not None:
                # 格式化數值
                if isinstance(value, float):
                    value_str = f"{value:.2f}"
                elif isinstance(value, (int, str)):
                    value_str = str(value)
                else:
                    value_str = str(value)
                
                condition_strs.append(f"{name}: {value_str}")
        
        if condition_strs:
            return f"{reason} | {' | '.join(condition_strs)}"
        else:
            return reason
    
    def _execute_order(self, order, date, price_dict):
        """
        執行訂單
        
        參數:
        - order: 訂單字典 {'action': 'buy'/'sell', 'ticker': str, 'shares': int, 'percent': float}
        - date: 交易日期
        - price_dict: 價格字典
        """
        action = order.get('action')
        ticker = order.get('ticker')
        
        if ticker not in price_dict:
            print(f"[Warning] {date.strftime('%Y-%m-%d')} {ticker} 無價格資料，跳過訂單")
            # 記錄到交易日誌以便後續分析
            if hasattr(self, '_missing_price_warnings'):
                self._missing_price_warnings.append({
                    'date': date,
                    'ticker': ticker,
                    'action': action
                })
            return
        
        price = price_dict[ticker]
        
        if action == 'buy':
            # 買進
            shares = order.get('shares', 0)
            percent = order.get('percent', 0)
            
            if percent > 0:
                # 使用百分比計算股數
                target_value = (self.cash + self._calculate_positions_value(price_dict)) * percent
                shares = int(target_value / price / 1000) * 1000  # 以千股為單位
            
            if shares <= 0:
                return
            
            cost = shares * price
            commission = self.calculate_commission(cost)
            total_cost = cost + commission
            
            if total_cost > self.cash:
                # 現金不足，調整股數
                available_cash = self.cash - commission
                shares = int(available_cash / price / 1000) * 1000
                cost = shares * price
                total_cost = cost + commission
            
            if shares <= 0 or total_cost > self.cash:
                return
            
            # 執行買進
            self.cash -= total_cost
            
            if ticker in self.positions:
                self.positions[ticker] += shares
            else:
                self.positions[ticker] = shares
            
            # 記錄交易（包含濾網參數和持倉比例）
            trade_record = {
                '日期': date,
                '動作': '買進',
                '交易步驟': self._format_trade_step(order.get('trade_step'), is_hedge=order.get('is_hedge_buy', False)),
                '標的代號': ticker,
                '股數': shares,  # 股數保持整數
                '價格': round(price, 2),
                '成本': round(cost, 2),
                '手續費': round(commission, 2),
                '總成本': round(total_cost, 2)
            }
            
            # 添加濾網參數（如果有）
            if hasattr(self, '_current_strategy_state'):
                state = self._current_strategy_state
                if state.get('m1b_yoy_month') is not None:
                    trade_record['M1B年增率'] = round(state.get('m1b_yoy_month'), 2)
                if state.get('m1b_yoy_momentum') is not None:
                    trade_record['M1B年增率動能'] = round(state.get('m1b_yoy_momentum'), 2)
                if state.get('m1b_mom') is not None:
                    trade_record['M1B動能'] = round(state.get('m1b_mom'), 2)
                if state.get('m1b_vs_3m_avg') is not None:
                    trade_record['M1Bvs3月平均'] = round(state.get('m1b_vs_3m_avg'), 2)
            
            # 添加持倉比例（如果有）
            if order.get('target_position_pct') is not None:
                trade_record['目標持倉比例'] = round(order.get('target_position_pct'), 2)
            if order.get('target_stock_pct') is not None:
                trade_record['目標股票比例'] = round(order.get('target_stock_pct'), 2)
            if order.get('target_bond_pct') is not None:
                trade_record['目標債券比例'] = round(order.get('target_bond_pct'), 2)
            
            # 添加燈號資訊（買進時優先使用買進信號的燈號，否則使用當前燈號）
            if hasattr(self, '_buy_signal_year') and self._buy_signal_year is not None:
                trade_record['燈號年份'] = self._buy_signal_year
                trade_record['燈號月份'] = self._buy_signal_month
                trade_record['燈號分數'] = round(self._buy_signal_score, 2) if self._buy_signal_score is not None else None
            elif hasattr(self, '_current_signal_year') and self._current_signal_year is not None:
                trade_record['燈號年份'] = self._current_signal_year
                trade_record['燈號月份'] = self._current_signal_month
                trade_record['燈號分數'] = round(self._current_signal_score, 2) if self._current_signal_score is not None else None
            
            self.trades.append(trade_record)
        
        elif action == 'sell':
            # 賣出
            shares = order.get('shares', 0)
            percent = order.get('percent', 0)
            
            if ticker not in self.positions or self.positions[ticker] <= 0:
                return
            
            if percent > 0:
                # 使用百分比計算股數
                current_shares = self.positions[ticker]
                shares = int(current_shares * percent / 1000) * 1000
            
            shares = min(shares, self.positions[ticker])
            
            if shares <= 0:
                return
            
            proceeds = shares * price
            commission = self.calculate_commission(proceeds)
            tax = self.calculate_tax(proceeds)
            net_proceeds = proceeds - commission - tax
            
            # 執行賣出
            self.positions[ticker] -= shares
            if self.positions[ticker] <= 0:
                del self.positions[ticker]
            
            self.cash += net_proceeds
            
            # 記錄交易（包含濾網參數和持倉比例）
            trade_record = {
                '日期': date,
                '動作': '賣出',
                '交易步驟': self._format_trade_step(order.get('trade_step')),
                '標的代號': ticker,
                '股數': shares,  # 股數保持整數
                '價格': round(price, 2),
                '收入': round(proceeds, 2),
                '手續費': round(commission, 2),
                '證交稅': round(tax, 2),
                '淨收入': round(net_proceeds, 2)
            }
            
            # 添加濾網參數（如果有）
            if hasattr(self, '_current_strategy_state'):
                state = self._current_strategy_state
                if state.get('m1b_yoy_month') is not None:
                    trade_record['M1B年增率'] = round(state.get('m1b_yoy_month'), 2)
                if state.get('m1b_yoy_momentum') is not None:
                    trade_record['M1B年增率動能'] = round(state.get('m1b_yoy_momentum'), 2)
                if state.get('m1b_mom') is not None:
                    trade_record['M1B動能'] = round(state.get('m1b_mom'), 2)
                if state.get('m1b_vs_3m_avg') is not None:
                    trade_record['M1Bvs3月平均'] = round(state.get('m1b_vs_3m_avg'), 2)
            
            # 添加持倉比例（如果有）
            if order.get('target_position_pct') is not None:
                trade_record['目標持倉比例'] = round(order.get('target_position_pct'), 2)
            if order.get('target_stock_pct') is not None:
                trade_record['目標股票比例'] = round(order.get('target_stock_pct'), 2)
            if order.get('target_bond_pct') is not None:
                trade_record['目標債券比例'] = round(order.get('target_bond_pct'), 2)
            
            # 添加燈號資訊（賣出時優先使用賣出信號的燈號，否則使用當前燈號）
            if hasattr(self, '_sell_signal_year') and self._sell_signal_year is not None:
                trade_record['燈號年份'] = self._sell_signal_year
                trade_record['燈號月份'] = self._sell_signal_month
                trade_record['燈號分數'] = round(self._sell_signal_score, 2) if self._sell_signal_score is not None else None
            elif hasattr(self, '_current_signal_year') and self._current_signal_year is not None:
                trade_record['燈號年份'] = self._current_signal_year
                trade_record['燈號月份'] = self._current_signal_month
                trade_record['燈號分數'] = round(self._current_signal_score, 2) if self._current_signal_score is not None else None
            
            self.trades.append(trade_record)
            
            # 檢查是否需要同步買進避險資產（用賣出得到的現金）
            if order.get('trigger_hedge_buy', False):
                hedge_ticker = order.get('hedge_ticker')
                if hedge_ticker and hedge_ticker in price_dict:
                    # 用賣出得到的淨收入買進避險資產
                    hedge_price = price_dict[hedge_ticker]
                    available_cash = net_proceeds  # 使用賣出得到的現金
                    
                    if available_cash > 0 and hedge_price > 0:
                        # 計算可買進的股數（以千股為單位）
                        hedge_shares = int(available_cash / hedge_price / 1000) * 1000
                        
                        if hedge_shares > 0:
                            hedge_cost = hedge_shares * hedge_price
                            hedge_commission = self.calculate_commission(hedge_cost)
                            hedge_total_cost = hedge_cost + hedge_commission
                            
                            # 確保不超過可用現金
                            if hedge_total_cost > available_cash:
                                # 調整股數
                                available_after_commission = available_cash - hedge_commission
                                if available_after_commission > 0:
                                    hedge_shares = int(available_after_commission / hedge_price / 1000) * 1000
                                    hedge_cost = hedge_shares * hedge_price
                                    hedge_total_cost = hedge_cost + hedge_commission
                            
                            if hedge_shares > 0 and hedge_total_cost <= available_cash:
                                # 執行買進
                                self.cash -= hedge_total_cost
                                
                                if hedge_ticker in self.positions:
                                    self.positions[hedge_ticker] += hedge_shares
                                else:
                                    self.positions[hedge_ticker] = hedge_shares
                                
                                # 記錄避險資產買進交易
                                # 從原始訂單中獲取交易步驟（如果有），否則使用預設值
                                hedge_trade_step = order.get('hedge_trade_step') or order.get('trade_step')
                                if not hedge_trade_step:
                                    # 如果沒有交易步驟，檢查是否有避險資產的訂單
                                    hedge_trade_step = None
                                
                                hedge_trade_record = {
                                    '日期': date,
                                    '動作': '買進',
                                    '交易步驟': self._format_trade_step(hedge_trade_step, is_hedge=True),
                                    '標的代號': hedge_ticker,
                                    '股數': hedge_shares,
                                    '價格': round(hedge_price, 2),
                                    '成本': round(hedge_cost, 2),
                                    '手續費': round(hedge_commission, 2),
                                    '總成本': round(hedge_total_cost, 2),
                                    'is_hedge_buy': True,
                                    'synced_with_sell': ticker
                                }
                                
                                # 添加濾網參數（如果有）
                                if hasattr(self, '_current_strategy_state'):
                                    state = self._current_strategy_state
                                    if state.get('m1b_yoy_month') is not None:
                                        hedge_trade_record['M1B年增率'] = round(state.get('m1b_yoy_month'), 2)
                                    if state.get('m1b_yoy_momentum') is not None:
                                        hedge_trade_record['M1B年增率動能'] = round(state.get('m1b_yoy_momentum'), 2)
                                    if state.get('m1b_mom') is not None:
                                        hedge_trade_record['M1B動能'] = round(state.get('m1b_mom'), 2)
                                    if state.get('m1b_vs_3m_avg') is not None:
                                        hedge_trade_record['M1Bvs3月平均'] = round(state.get('m1b_vs_3m_avg'), 2)
                                
                                # 添加持倉比例（如果有）
                                if order.get('target_position_pct') is not None:
                                    hedge_trade_record['目標持倉比例'] = round(order.get('target_position_pct'), 2)
                                
                                # 添加燈號資訊（如果有）
                                if hasattr(self, '_current_signal_year') and self._current_signal_year is not None:
                                    hedge_trade_record['燈號年份'] = self._current_signal_year
                                    hedge_trade_record['燈號月份'] = self._current_signal_month
                                    hedge_trade_record['燈號分數'] = round(self._current_signal_score, 2) if self._current_signal_score is not None else None
                                
                                self.trades.append(hedge_trade_record)
    
    def _calculate_positions_value(self, price_dict):
        """計算持倉價值"""
        total_value = 0
        for ticker, shares in self.positions.items():
            if ticker in price_dict:
                total_value += shares * price_dict[ticker]
        return total_value
    
    def _calculate_portfolio_value(self, date, price_dict):
        """計算投資組合總價值"""
        positions_value = self._calculate_positions_value(price_dict)
        return self.cash + positions_value
    
    def _calculate_metrics(self):
        """計算績效指標"""
        if not self.returns:
            return {}
        
        returns_array = np.array(self.returns)
        
        # 總報酬率
        total_return = (self.portfolio_value[-1] - self.initial_capital) / self.initial_capital if self.portfolio_value else 0
        
        # 年化報酬率
        years = len(self.dates) / 252  # 假設一年 252 個交易日
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 波動度（年化）
        volatility = np.std(returns_array) * np.sqrt(252)
        
        # 夏普比率（假設無風險利率為 0）
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # 最大回落
        cumulative = np.cumprod(1 + returns_array)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        # 計算額外指標
        turnover_rate = self._calculate_turnover_rate()
        avg_holding_period = self._calculate_avg_holding_period()
        win_rate = self._calculate_win_rate()
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': len(self.trades),
            'turnover_rate': turnover_rate,
            'avg_holding_period': avg_holding_period,
            'win_rate': win_rate
        }
    
    def _calculate_turnover_rate(self):
        """計算換手率（年化）"""
        if not self.trades or not self.portfolio_value:
            return 0.0
        
        # 計算總交易金額
        total_trade_value = 0
        for trade in self.trades:
            # 兼容中英文鍵名
            action = trade.get('動作') or trade.get('action', '')
            if action == '買進' or action == 'buy':
                total_trade_value += trade.get('總成本', trade.get('total_cost', 0))
            elif action == '賣出' or action == 'sell':
                total_trade_value += trade.get('收入', trade.get('proceeds', 0))
        
        # 計算平均投資組合價值
        if self.portfolio_value:
            avg_portfolio_value = np.mean(self.portfolio_value)
        else:
            avg_portfolio_value = self.initial_capital
        
        # 計算年化換手率
        if avg_portfolio_value > 0:
            years = len(self.dates) / 252 if self.dates else 1
            turnover_rate = (total_trade_value / avg_portfolio_value) / years if years > 0 else 0
            return turnover_rate * 100  # 轉換為百分比
        return 0.0
    
    def _calculate_avg_holding_period(self):
        """計算平均持倉期間（天）"""
        if not self.trades:
            return 0.0
        
        # 追蹤每個標的的買進和賣出時間
        positions = {}  # {ticker: [(buy_date, shares), ...]}
        holding_periods = []
        
        for trade in self.trades:
            # 兼容中英文鍵名
            ticker = trade.get('標的代號') or trade.get('ticker', '')
            date = trade.get('日期') or trade.get('date')
            action = trade.get('動作') or trade.get('action', '')
            shares = trade.get('股數') or trade.get('shares', 0)
            
            if not date or not ticker:
                continue
            
            if action == '買進' or action == 'buy':
                if ticker not in positions:
                    positions[ticker] = []
                positions[ticker].append((date, shares))
            elif action == '賣出' or action == 'sell':
                if ticker in positions and positions[ticker]:
                    # 使用 FIFO 原則計算持倉期間
                    remaining_shares = shares
                    while remaining_shares > 0 and positions[ticker]:
                        buy_date, buy_shares = positions[ticker][0]
                        if buy_shares <= remaining_shares:
                            # 完全賣出這筆持倉
                            holding_days = (date - buy_date).days
                            holding_periods.append(holding_days)
                            remaining_shares -= buy_shares
                            positions[ticker].pop(0)
                        else:
                            # 部分賣出
                            holding_days = (date - buy_date).days
                            holding_periods.append(holding_days)
                            positions[ticker][0] = (buy_date, buy_shares - remaining_shares)
                            remaining_shares = 0
        
        if holding_periods:
            return np.mean(holding_periods)
        return 0.0
    
    def _calculate_win_rate(self):
        """計算勝率（獲利交易比例）"""
        if not self.trades:
            return 0.0
        
        # 追蹤每個標的的買進和賣出配對
        positions = {}  # {ticker: [(buy_date, buy_price, shares), ...]}
        trade_pairs = []  # [(buy_price, sell_price, shares), ...] 完整的買賣配對
        
        for trade in self.trades:
            # 兼容中英文鍵名
            ticker = trade.get('標的代號') or trade.get('ticker', '')
            date = trade.get('日期') or trade.get('date')
            action = trade.get('動作') or trade.get('action', '')
            shares = trade.get('股數') or trade.get('shares', 0)
            price = trade.get('價格') or trade.get('price', 0)
            
            if not date or not ticker or price == 0:
                continue
            
            if action == '買進' or action == 'buy':
                if ticker not in positions:
                    positions[ticker] = []
                positions[ticker].append((date, price, shares))
            elif action == '賣出' or action == 'sell':
                if ticker in positions and positions[ticker]:
                    # 使用 FIFO 原則計算盈虧
                    remaining_shares = shares
                    while remaining_shares > 0 and positions[ticker]:
                        buy_date, buy_price, buy_shares = positions[ticker][0]
                        if buy_shares <= remaining_shares:
                            # 完全賣出這筆持倉
                            trade_pairs.append((buy_price, price, buy_shares))
                            remaining_shares -= buy_shares
                            positions[ticker].pop(0)
                        else:
                            # 部分賣出：將這筆買進分成兩部分
                            # 賣出的部分作為一個完整的配對
                            trade_pairs.append((buy_price, price, remaining_shares))
                            # 剩餘的部分保留在 positions 中
                            positions[ticker][0] = (buy_date, buy_price, buy_shares - remaining_shares)
                            remaining_shares = 0
        
        # 計算勝率：每筆完整的買賣配對計算一次
        if trade_pairs:
            profitable_pairs = sum(1 for buy_price, sell_price, _ in trade_pairs if sell_price > buy_price)
            total_pairs = len(trade_pairs)
            if total_pairs > 0:
                return (profitable_pairs / total_pairs) * 100  # 轉換為百分比
        
        return 0.0
    
    def generate_position_summary(self):
        """產生持倉變動摘要"""
        if not self.trades:
            return {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'avg_holding_period': 0,
                'max_holding_period': 0,
                'min_holding_period': 0
            }
        
        # 兼容中英文鍵名
        buy_count = sum(1 for t in self.trades if (t.get('動作') == '買進' or t.get('action') == 'buy'))
        sell_count = sum(1 for t in self.trades if (t.get('動作') == '賣出' or t.get('action') == 'sell'))
        avg_holding = self._calculate_avg_holding_period()
        
        # 計算最長和最短持倉期間
        holding_periods = []
        positions = {}
        
        for trade in self.trades:
            # 兼容中英文鍵名
            ticker = trade.get('標的代號') or trade.get('ticker', '')
            date = trade.get('日期') or trade.get('date')
            action = trade.get('動作') or trade.get('action', '')
            shares = trade.get('股數') or trade.get('shares', 0)
            
            if not date or not ticker:
                continue
            
            if action == '買進' or action == 'buy':
                if ticker not in positions:
                    positions[ticker] = []
                positions[ticker].append((date, shares))
            elif action == '賣出' or action == 'sell':
                if ticker in positions and positions[ticker]:
                    remaining_shares = shares
                    while remaining_shares > 0 and positions[ticker]:
                        buy_date, buy_shares = positions[ticker][0]
                        if buy_shares <= remaining_shares:
                            holding_days = (date - buy_date).days
                            holding_periods.append(holding_days)
                            remaining_shares -= buy_shares
                            positions[ticker].pop(0)
                        else:
                            holding_days = (date - buy_date).days
                            holding_periods.append(holding_days)
                            positions[ticker][0] = (buy_date, buy_shares - remaining_shares)
                            remaining_shares = 0
        
        max_holding = max(holding_periods) if holding_periods else 0
        min_holding = min(holding_periods) if holding_periods else 0
        
        return {
            'total_trades': len(self.trades),
            'buy_trades': buy_count,
            'sell_trades': sell_count,
            'avg_holding_period': avg_holding,
            'max_holding_period': max_holding,
            'min_holding_period': min_holding
        }

