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
        
        # 追蹤月份變化和交易標記
        prev_prev_val_shifted = None  # 上上個月的分數（用於判斷「變成」）
        prev_val_shifted = None  # 上個月的分數（用於決定交易）
        prev_date = None  # 上一個交易日
        current_month_key = None
        prev_month_key = None
        need_buy_this_month = False  # 標記本月是否需要買進
        need_sell_this_month = False  # 標記本月是否需要賣出
        
        # 每日迭代
        for i, date in enumerate(trading_days):
            self.dates.append(date)
            
            # 取得當日景氣燈號分數（使用前一日的 val_shifted）
            score = None
            val_shifted = None
            
            if date in self.cycle_data.index:
                row = self.cycle_data.loc[date]
                score = row.get('score')
                val_shifted = row.get('val_shifted')
            else:
                # 如果找不到當日資料，使用前一個有效日期的資料
                try:
                    prev_date = max([d for d in self.cycle_data.index if d <= date])
                    row = self.cycle_data.loc[prev_date]
                    score = row.get('score')
                    val_shifted = row.get('val_shifted')
                except:
                    pass
            
            if val_shifted is None:
                # 如果沒有景氣燈號資料，跳過
                continue
            
            # 更新景氣分數和動能
            # 注意：score 是當月原始分數，val_shifted 是前一個月的分數（用於交易決策）
            strategy_state['score'] = val_shifted  # 使用 val_shifted 作為交易決策依據
            
            # 追蹤月份變化
            current_month_key = (date.year, date.month)
            
            # 檢查是否跨月（考慮跨年情況）
            if prev_month_key is not None and current_month_key != prev_month_key:
                # 跨月了，檢查上一個月的燈號狀態（使用上一個交易日的 val_shifted）
                # 當月份變化時，prev_val_shifted 是上上個月的分數，val_shifted 是上個月的分數
                if prev_val_shifted is not None and val_shifted is not None:
                    prev_prev_was_blue = prev_val_shifted <= 16
                    prev_prev_was_red = prev_val_shifted >= 38
                    prev_was_blue = val_shifted <= 16
                    prev_was_red = val_shifted >= 38
                    
                    # 如果上個月是藍燈，且不是從藍燈變來的（變成藍燈），則需要買進
                    if prev_was_blue and not prev_prev_was_blue:
                        need_buy_this_month = True
                    else:
                        need_buy_this_month = False
                    
                    # 如果上個月是紅燈，且不是從紅燈變來的（變成紅燈），則需要賣出
                    if prev_was_red and not prev_prev_was_red:
                        need_sell_this_month = True
                    else:
                        need_sell_this_month = False
                else:
                    need_buy_this_month = False
                    need_sell_this_month = False
                
                # 更新月份分數追蹤
                prev_prev_val_shifted = prev_val_shifted
                prev_val_shifted = val_shifted
                prev_month_key = current_month_key
                
                # 計算分數動能
                if prev_month_score is not None and score is not None:
                    strategy_state['score_momentum'] = score - prev_month_score
                prev_month_score = score
                prev_month_date = date
            elif prev_month_key is None:
                # 第一次，初始化
                prev_val_shifted = val_shifted
                prev_prev_val_shifted = None
                prev_month_key = current_month_key
                prev_month_score = score
                prev_month_date = date
                strategy_state['score_momentum'] = None
                need_buy_this_month = False
                need_sell_this_month = False
            else:
                # 同一個月內，更新 val_shifted 追蹤（同一個月內的 val_shifted 應該相同）
                prev_val_shifted = val_shifted if val_shifted is not None else prev_val_shifted
                # score_momentum 保持不變
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
            
            # 建立價格字典
            price_dict = {}
            for _, row in date_price_data.iterrows():
                price_dict[row['ticker']] = row['close']
            
            # 檢查是否為特定交易日期（第一個或最後一個交易日）
            is_first_trading_day = month_first_trading_day.get(current_month_key) == date
            is_last_trading_day = month_last_trading_day.get(current_month_key) == date
            
            # 在 strategy_state 中設置交易時機標記
            strategy_state['is_first_trading_day'] = is_first_trading_day
            strategy_state['is_last_trading_day'] = is_last_trading_day
            strategy_state['should_buy_on_first_day'] = need_buy_this_month if is_first_trading_day else False
            strategy_state['should_sell_on_last_day'] = need_sell_this_month if is_last_trading_day else False
            
            # 執行策略
            # 為等比例配置策略提供持倉資訊
            portfolio_value_before = self._calculate_portfolio_value(date, price_dict)
            orders = strategy_func(strategy_state, date, price_dict, self.positions, portfolio_value_before)
            
            # 執行訂單
            if orders:
                for order in orders:
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
        
        return {
            'dates': self.dates,
            'portfolio_value': self.portfolio_value,
            'returns': self.returns,
            'trades': self.trades,
            'metrics': metrics,
            'final_value': self.portfolio_value[-1] if self.portfolio_value else self.initial_capital,
            'total_return': (self.portfolio_value[-1] - self.initial_capital) / self.initial_capital if self.portfolio_value else 0
        }
    
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
            
            # 記錄交易
            self.trades.append({
                'date': date,
                'action': 'buy',
                'ticker': ticker,
                'shares': shares,
                'price': price,
                'cost': cost,
                'commission': commission,
                'total_cost': total_cost
            })
        
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
            
            # 記錄交易
            self.trades.append({
                'date': date,
                'action': 'sell',
                'ticker': ticker,
                'shares': shares,
                'price': price,
                'proceeds': proceeds,
                'commission': commission,
                'tax': tax,
                'net_proceeds': net_proceeds
            })
    
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
            if trade['action'] == 'buy':
                total_trade_value += trade.get('total_cost', 0)
            elif trade['action'] == 'sell':
                total_trade_value += trade.get('proceeds', 0)
        
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
            ticker = trade['ticker']
            date = trade['date']
            action = trade['action']
            shares = trade['shares']
            
            if action == 'buy':
                if ticker not in positions:
                    positions[ticker] = []
                positions[ticker].append((date, shares))
            elif action == 'sell':
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
        
        # 追蹤每個標的的買進和賣出
        positions = {}  # {ticker: [(buy_date, buy_price, shares), ...]}
        profitable_trades = 0
        total_sell_trades = 0
        
        for trade in self.trades:
            ticker = trade['ticker']
            date = trade['date']
            action = trade['action']
            shares = trade['shares']
            price = trade['price']
            
            if action == 'buy':
                if ticker not in positions:
                    positions[ticker] = []
                positions[ticker].append((date, price, shares))
            elif action == 'sell':
                if ticker in positions and positions[ticker]:
                    total_sell_trades += 1
                    # 使用 FIFO 原則計算盈虧
                    remaining_shares = shares
                    while remaining_shares > 0 and positions[ticker]:
                        buy_date, buy_price, buy_shares = positions[ticker][0]
                        if buy_shares <= remaining_shares:
                            # 完全賣出這筆持倉
                            if price > buy_price:
                                profitable_trades += 1
                            remaining_shares -= buy_shares
                            positions[ticker].pop(0)
                        else:
                            # 部分賣出
                            if price > buy_price:
                                profitable_trades += 1
                            positions[ticker][0] = (buy_date, buy_price, buy_shares - remaining_shares)
                            remaining_shares = 0
        
        if total_sell_trades > 0:
            return (profitable_trades / total_sell_trades) * 100  # 轉換為百分比
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
        
        buy_count = sum(1 for t in self.trades if t['action'] == 'buy')
        sell_count = sum(1 for t in self.trades if t['action'] == 'sell')
        avg_holding = self._calculate_avg_holding_period()
        
        # 計算最長和最短持倉期間
        holding_periods = []
        positions = {}
        
        for trade in self.trades:
            ticker = trade['ticker']
            date = trade['date']
            action = trade['action']
            shares = trade['shares']
            
            if action == 'buy':
                if ticker not in positions:
                    positions[ticker] = []
                positions[ticker].append((date, shares))
            elif action == 'sell':
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

