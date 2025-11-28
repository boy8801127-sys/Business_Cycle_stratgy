"""
景氣週期投資策略實作
參考範例程式碼的策略邏輯
"""


class CycleStrategy:
    """景氣週期投資策略基類"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker=None):
        """
        初始化策略
        
        參數:
        - stock_ticker: 股票代號（預設 '006208'，富邦台50）
        - hedge_ticker: 避險資產代號（None 表示現金）
        """
        self.stock_ticker = stock_ticker
        self.hedge_ticker = hedge_ticker
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """
        根據策略狀態和景氣燈號產生訂單
        
        參數:
        - state: 策略狀態字典 {'state': bool, 'hedge_state': bool, 'score': float, 'a': int}
        - date: 交易日期
        - price_dict: 價格字典
        - positions: 當前持倉字典 {ticker: shares}（可選，用於等比例配置策略）
        - portfolio_value: 當前投資組合總價值（可選，用於等比例配置策略）
        
        回傳:
        - 訂單列表
        """
        orders = []
        score = state.get('score')
        
        if score is None:
            return orders
        
        # SCORE <= 16（藍燈）：買進股票，賣出避險資產
        if score <= 16 and not state.get('state', False):
            orders.append({
                'action': 'buy',
                'ticker': self.stock_ticker,
                'percent': 1.0  # 100% 買進股票
            })
            state['state'] = True
            
            # 如果有避險資產且持有，則賣出
            if self.hedge_ticker and state.get('hedge_state', False):
                orders.append({
                    'action': 'sell',
                    'ticker': self.hedge_ticker,
                    'percent': 1.0  # 100% 賣出避險資產
                })
                state['hedge_state'] = False
        
        # SCORE >= 38（紅燈）：賣出股票，買進避險資產
        elif score >= 38 and state.get('state', False):
            orders.append({
                'action': 'sell',
                'ticker': self.stock_ticker,
                'percent': 1.0  # 100% 賣出股票
            })
            state['state'] = False
            
            # 如果有避險資產，則買進
            if self.hedge_ticker and not state.get('hedge_state', False):
                orders.append({
                    'action': 'buy',
                    'ticker': self.hedge_ticker,
                    'percent': 1.0  # 100% 買進避險資產
                })
                state['hedge_state'] = True
        
        # 16 < SCORE < 38：首次進入時買進股票
        elif 16 < score < 38:
            if state.get('a', 0) == 0:
                state['a'] = 1
                if not state.get('state', False):
                    orders.append({
                        'action': 'buy',
                        'ticker': self.stock_ticker,
                        'percent': 1.0  # 100% 買進股票
                    })
                    state['state'] = True
        
        return orders


class ShortTermBondStrategy(CycleStrategy):
    """短天期美債避險策略"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        super().__init__(stock_ticker, hedge_ticker)


class CashStrategy(CycleStrategy):
    """現金避險策略（不需要買賣避險資產）"""
    
    def __init__(self, stock_ticker='006208'):
        super().__init__(stock_ticker, None)


class LongTermBondStrategy(CycleStrategy):
    """長天期美債避險策略"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00687B'):
        super().__init__(stock_ticker, hedge_ticker)


class InverseETFStrategy(CycleStrategy):
    """反向ETF避險策略"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00664R'):
        super().__init__(stock_ticker, hedge_ticker)


class FiftyFiftyStrategy(CycleStrategy):
    """50:50 配置策略（股票和避險資產各50%）"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        super().__init__(stock_ticker, hedge_ticker)
    
    def generate_orders(self, state, date, price_dict):
        """
        50:50 配置策略的特殊邏輯
        當景氣過熱時，不是完全賣出股票，而是保留 50%
        """
        orders = []
        score = state.get('score')
        
        if score is None:
            return orders
        
        # SCORE <= 16（藍燈）：100% 買進股票，賣出避險資產
        if score <= 16 and not state.get('state', False):
            orders.append({
                'action': 'buy',
                'ticker': self.stock_ticker,
                'percent': 1.0
            })
            state['state'] = True
            
            if self.hedge_ticker and state.get('hedge_state', False):
                orders.append({
                    'action': 'sell',
                    'ticker': self.hedge_ticker,
                    'percent': 1.0
                })
                state['hedge_state'] = False
        
        # SCORE >= 38（紅燈）：保留 50% 股票，買進 50% 避險資產
        elif score >= 38 and state.get('state', False):
            # 賣出 50% 股票
            orders.append({
                'action': 'sell',
                'ticker': self.stock_ticker,
                'percent': 0.5
            })
            
            # 買進 50% 避險資產
            if self.hedge_ticker and not state.get('hedge_state', False):
                orders.append({
                    'action': 'buy',
                    'ticker': self.hedge_ticker,
                    'percent': 0.5
                })
                state['hedge_state'] = True
        
        # 16 < SCORE < 38：首次進入時買進股票
        elif 16 < score < 38:
            if state.get('a', 0) == 0:
                state['a'] = 1
                if not state.get('state', False):
                    orders.append({
                        'action': 'buy',
                        'ticker': self.stock_ticker,
                        'percent': 1.0
                    })
                    state['state'] = True
        
        return orders


class ProportionalAllocationStrategy(CycleStrategy):
    """等比例配置策略（006208:短期美債，根據景氣燈號等比例配置）"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        super().__init__(stock_ticker, hedge_ticker)
        
        # 定義燈號等級和對應的股票配置比例
        # 燈號從低到高：藍燈、黃藍燈、綠燈、黃紅燈、紅燈
        # 股票比例從高到低：100%, 80%, 60%, 40%, 20%
        self.allocation_rules = {
            'blue': {'stock_pct': 1.0, 'bond_pct': 0.0},      # 藍燈：100% 股票, 0% 債券
            'yellow_blue': {'stock_pct': 0.8, 'bond_pct': 0.2}, # 黃藍燈：80% 股票, 20% 債券
            'green': {'stock_pct': 0.6, 'bond_pct': 0.4},     # 綠燈：60% 股票, 40% 債券
            'yellow_red': {'stock_pct': 0.4, 'bond_pct': 0.6}, # 黃紅燈：40% 股票, 60% 債券
            'red': {'stock_pct': 0.2, 'bond_pct': 0.8}        # 紅燈：20% 股票, 80% 債券
        }
    
    def _get_signal_level(self, score):
        """
        根據景氣燈號分數判斷燈號等級
        
        參數:
        - score: 景氣對策信號綜合分數
        
        回傳:
        - 燈號等級字串
        """
        if score is None:
            return None
        
        # 根據一般景氣燈號分數區間
        if score <= 16:
            return 'blue'  # 藍燈
        elif score <= 22:
            return 'yellow_blue'  # 黃藍燈
        elif score <= 31:
            return 'green'  # 綠燈
        elif score <= 38:
            return 'yellow_red'  # 黃紅燈
        else:
            return 'red'  # 紅燈
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """
        根據景氣燈號等比例配置策略產生訂單
        
        參數:
        - state: 策略狀態字典
        - date: 交易日期
        - price_dict: 價格字典
        - positions: 當前持倉字典 {ticker: shares}
        - portfolio_value: 當前投資組合總價值
        
        回傳:
        - 訂單列表
        """
        orders = []
        score = state.get('score')
        
        if score is None:
            return orders
        
        # 取得當前的燈號等級
        signal_level = self._get_signal_level(score)
        
        if signal_level is None:
            return orders
        
        # 取得目標配置比例
        target_allocation = self.allocation_rules.get(signal_level)
        
        if target_allocation is None:
            return orders
        
        target_stock_pct = target_allocation['stock_pct']
        target_bond_pct = target_allocation['bond_pct']
        
        # 如果沒有持倉資訊，首次配置
        if positions is None or portfolio_value is None or portfolio_value <= 0:
            # 首次買進目標比例的股票和債券
            if target_stock_pct > 0:
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': target_stock_pct
                })
            if target_bond_pct > 0 and self.hedge_ticker:
                orders.append({
                    'action': 'buy',
                    'ticker': self.hedge_ticker,
                    'percent': target_bond_pct
                })
            return orders
        
        # 計算當前持倉價值
        current_stock_value = positions.get(self.stock_ticker, 0) * price_dict.get(self.stock_ticker, 0)
        current_bond_value = positions.get(self.hedge_ticker, 0) * price_dict.get(self.hedge_ticker, 0) if self.hedge_ticker else 0
        
        # 計算當前持倉比例
        current_stock_pct = current_stock_value / portfolio_value if portfolio_value > 0 else 0
        current_bond_pct = current_bond_value / portfolio_value if portfolio_value > 0 else 0
        
        # 計算需要調整的比例
        stock_diff = target_stock_pct - current_stock_pct
        bond_diff = target_bond_pct - current_bond_pct
        
        # 產生調整訂單（容許小的誤差，避免頻繁交易）
        threshold = 0.05  # 5% 的容許誤差
        
        if abs(stock_diff) > threshold:
            if stock_diff > 0:
                # 需要增持股票
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': stock_diff
                })
            else:
                # 需要減持股票
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': abs(stock_diff)
                })
        
        if self.hedge_ticker and abs(bond_diff) > threshold:
            if bond_diff > 0:
                # 需要增持債券
                orders.append({
                    'action': 'buy',
                    'ticker': self.hedge_ticker,
                    'percent': bond_diff
                })
            else:
                # 需要減持債券
                orders.append({
                    'action': 'sell',
                    'ticker': self.hedge_ticker,
                    'percent': abs(bond_diff)
                })
        
        return orders


class TSMCProportionalAllocationStrategy(ProportionalAllocationStrategy):
    """台積電等比例配置策略（2330:短期美債，根據景氣燈號等比例配置）"""
    
    def __init__(self, stock_ticker='2330', hedge_ticker='00865B'):
        super().__init__(stock_ticker, hedge_ticker)

