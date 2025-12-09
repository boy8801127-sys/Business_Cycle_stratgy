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
    
    def _create_trade_step(self, reason, state, additional_conditions=None):
        """
        建立交易步驟資訊
        
        參數:
        - reason: 交易原因（例如：'藍燈買進'、'紅燈賣出'）
        - state: 策略狀態字典
        - additional_conditions: 額外條件列表 [{'name': str, 'value': float}, ...]
        
        回傳:
        - 交易步驟字典 {'reason': str, 'conditions': [{'name': str, 'value': float}, ...]}
        """
        conditions = []
        
        # 添加景氣燈號分數
        score = state.get('score')
        if score is not None:
            conditions.append({'name': '景氣燈號分數', 'value': score})
        
        # 添加M1B相關條件（如果有）
        m1b_yoy_momentum = state.get('m1b_yoy_momentum')
        if m1b_yoy_momentum is not None:
            conditions.append({'name': 'M1B年增率動能', 'value': m1b_yoy_momentum})
        
        m1b_mom = state.get('m1b_mom')
        if m1b_mom is not None:
            conditions.append({'name': 'M1B動能', 'value': m1b_mom})
        
        m1b_yoy_month = state.get('m1b_yoy_month')
        if m1b_yoy_month is not None:
            conditions.append({'name': 'M1B年增率', 'value': m1b_yoy_month})
        
        m1b_vs_3m_avg = state.get('m1b_vs_3m_avg')
        if m1b_vs_3m_avg is not None:
            conditions.append({'name': 'M1Bvs3月平均', 'value': m1b_vs_3m_avg})
        
        # 添加分數動能（如果有）
        score_momentum = state.get('score_momentum')
        if score_momentum is not None:
            conditions.append({'name': '景氣分數動能', 'value': score_momentum})
        
        # 添加額外條件
        if additional_conditions:
            conditions.extend(additional_conditions)
        
        return {
            'reason': reason,
            'conditions': conditions
        }
    
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
        
        # 檢查分批執行標記
        should_buy_in_split = state.get('should_buy_in_split', False)
        should_sell_in_split = state.get('should_sell_in_split', False)
        
        # SCORE <= 16（藍燈）：買進股票，賣出避險資產
        if score <= 16:
            # 如果是首次買進（state['state'] 為 False），或者是在分批買進窗口內
            if not state.get('state', False) or should_buy_in_split:
                # 只有在分批買進時間窗口內才產生訂單
                if should_buy_in_split:
                    # 添加調試日誌
                    if date.year >= 2021:
                        print(f"[DEBUG Strategy] {date.strftime('%Y-%m-%d')} 藍燈買進條件滿足: score={score}, state['state']={state.get('state', False)}, should_buy_in_split={should_buy_in_split}")
                    trade_step = self._create_trade_step('藍燈買進', state)
                    orders.append({
                        'action': 'buy',
                        'ticker': self.stock_ticker,
                        'percent': 1.0,
                        'split_execution': True,  # 標記需要分批執行
                        'trade_step': trade_step
                    })
                    # 只在首次買進時設置 state['state'] = True
                    # 後續的分批買進不會再次設置，因為已經是 True
                    if not state.get('state', False):
                        state['state'] = True
                    
                    # 如果有避險資產且持有，則賣出（也要分批）
                    if self.hedge_ticker and state.get('hedge_state', False):
                        hedge_trade_step = self._create_trade_step('藍燈賣出避險資產', state)
                        orders.append({
                            'action': 'sell',
                            'ticker': self.hedge_ticker,
                            'percent': 1.0,
                            'split_execution': True,  # 標記需要分批執行
                            'is_hedge_sell': True,  # 標記為避險資產賣出
                            'trade_step': hedge_trade_step
                        })
                        state['hedge_state'] = False
            else:
                # 添加調試日誌 - 藍燈但不在買進窗口內
                if date.year >= 2021:
                    print(f"[DEBUG Strategy] {date.strftime('%Y-%m-%d')} 藍燈但不在買進窗口: score={score}, state['state']={state.get('state', False)}, should_buy_in_split={should_buy_in_split}")
        else:
            # 添加調試日誌 - 藍燈但條件不滿足
            if date.year >= 2021 and score <= 16 and should_buy_in_split:
                print(f"[DEBUG Strategy] {date.strftime('%Y-%m-%d')} 藍燈買進條件不滿足: score={score}, state['state']={state.get('state', False)}, should_buy_in_split={should_buy_in_split}, 條件檢查: score<=16={score <= 16}, not state={not state.get('state', False)}")
        
        # SCORE >= 38（紅燈）：賣出股票，買進避險資產
        if score >= 38 and state.get('state', False):
            # 只有在分批賣出時間窗口內才產生訂單
            if should_sell_in_split:
                trade_step = self._create_trade_step('紅燈賣出', state)
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': 1.0,
                    'split_execution': True,  # 標記需要分批執行
                    'trigger_hedge_buy': True,  # 標記需要同時買進避險資產
                    'trade_step': trade_step
                })
                state['state'] = False
                
                # 如果有避險資產，則買進（需要同步分批）
                if self.hedge_ticker and not state.get('hedge_state', False):
                    hedge_trade_step = self._create_trade_step('紅燈買進避險資產', state)
                    orders.append({
                        'action': 'buy',
                        'ticker': self.hedge_ticker,
                        'percent': 1.0,
                        'split_execution': True,  # 標記需要分批執行
                        'is_hedge_buy': True,  # 標記為避險資產買進
                        'is_synced_split': True,  # 標記需要與股票賣出同步分批
                        'trade_step': hedge_trade_step
                    })
                    state['hedge_state'] = True
        
        # 16 < SCORE < 38：首次進入時買進股票
        if 16 < score < 38:
            if state.get('a', 0) == 0:
                state['a'] = 1
                if not state.get('state', False):
                    # 首次進入時直接買進（不需要分批）
                    trade_step = self._create_trade_step('首次進入買進', state)
                    orders.append({
                        'action': 'buy',
                        'ticker': self.stock_ticker,
                        'percent': 1.0,
                        'trade_step': trade_step
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
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """
        50:50 配置策略的特殊邏輯
        當景氣過熱時，不是完全賣出股票，而是保留 50%
        
        參數:
        - state: 策略狀態字典
        - date: 交易日期
        - price_dict: 價格字典
        - positions: 當前持倉字典（可選，此策略不使用）
        - portfolio_value: 當前投資組合總價值（可選，此策略不使用）
        
        回傳:
        - 訂單列表
        """
        orders = []
        score = state.get('score')
        
        if score is None:
            return orders
        
        # SCORE <= 16（藍燈）：100% 買進股票，賣出避險資產
        if score <= 16 and not state.get('state', False):
            trade_step = self._create_trade_step('藍燈買進', state)
            orders.append({
                'action': 'buy',
                'ticker': self.stock_ticker,
                'percent': 1.0,
                'trade_step': trade_step
            })
            state['state'] = True
            
            if self.hedge_ticker and state.get('hedge_state', False):
                hedge_trade_step = self._create_trade_step('藍燈賣出避險資產', state)
                orders.append({
                    'action': 'sell',
                    'ticker': self.hedge_ticker,
                    'percent': 1.0,
                    'trade_step': hedge_trade_step
                })
                state['hedge_state'] = False
        
        # SCORE >= 38（紅燈）：保留 50% 股票，買進 50% 避險資產
        elif score >= 38 and state.get('state', False):
            # 計算當前持倉比例
            if positions and portfolio_value:
                current_stock_value = positions.get(self.stock_ticker, 0) * price_dict.get(self.stock_ticker, 0)
                current_stock_pct = current_stock_value / portfolio_value if portfolio_value > 0 else 0
                
                # 如果股票比例 > 55%，需要減碼至50%
                if current_stock_pct > 0.55:
                    sell_pct = (current_stock_pct - 0.5) / current_stock_pct
                    trade_step = self._create_trade_step('紅燈減碼至50%', state, [
                        {'name': '當前股票比例', 'value': current_stock_pct}
                    ])
                    orders.append({
                        'action': 'sell',
                        'ticker': self.stock_ticker,
                        'percent': sell_pct,
                        'trigger_hedge_buy': True,
                        'hedge_ticker': self.hedge_ticker,
                        'trade_step': trade_step
                    })
                    
                    # 同步買進避險資產
                    if self.hedge_ticker:
                        current_hedge_value = positions.get(self.hedge_ticker, 0) * price_dict.get(self.hedge_ticker, 0)
                        current_hedge_pct = current_hedge_value / portfolio_value if portfolio_value > 0 else 0
                        target_hedge_pct = 0.5
                        hedge_diff = target_hedge_pct - current_hedge_pct
                        
                        if hedge_diff > 0.05:  # 5% 的容許誤差
                            hedge_trade_step = self._create_trade_step('紅燈買進避險資產至50%', state, [
                                {'name': '當前避險資產比例', 'value': current_hedge_pct},
                                {'name': '目標避險資產比例', 'value': target_hedge_pct}
                            ])
                            orders.append({
                                'action': 'buy',
                                'ticker': self.hedge_ticker,
                                'percent': hedge_diff,
                                'is_hedge_buy': True,
                                'trade_step': hedge_trade_step
                            })
                            state['hedge_state'] = True
            else:
                # 如果沒有持倉資訊，賣出50%股票並買進50%避險資產
                trade_step = self._create_trade_step('紅燈減碼至50%', state)
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': 0.5,
                    'trigger_hedge_buy': True,
                    'hedge_ticker': self.hedge_ticker,
                    'trade_step': trade_step
                })
                
                if self.hedge_ticker:
                    hedge_trade_step = self._create_trade_step('紅燈買進避險資產至50%', state)
                    orders.append({
                        'action': 'buy',
                        'ticker': self.hedge_ticker,
                        'percent': 0.5,
                        'is_hedge_buy': True,
                        'trade_step': hedge_trade_step
                    })
                    state['hedge_state'] = True
        
        # 16 < SCORE < 38：首次進入時買進股票
        elif 16 < score < 38:
            if state.get('a', 0) == 0:
                state['a'] = 1
                if not state.get('state', False):
                    trade_step = self._create_trade_step('首次進入買進', state)
                    orders.append({
                        'action': 'buy',
                        'ticker': self.stock_ticker,
                        'percent': 1.0,
                        'trade_step': trade_step
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
        
        # 根據官方景氣燈號分數區間（國發會標準）
        # 藍燈：9-16分、黃藍燈：17-22分、綠燈：23-31分、黃紅燈：32-37分、紅燈：38-45分
        if 9 <= score <= 16:
            return 'blue'  # 藍燈
        elif 17 <= score <= 22:
            return 'yellow_blue'  # 黃藍燈
        elif 23 <= score <= 31:
            return 'green'  # 綠燈
        elif 32 <= score <= 37:
            return 'yellow_red'  # 黃紅燈
        elif score >= 38:
            return 'red'  # 紅燈
        else:
            return None  # 分數 < 9，可能是資料缺失
    
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
                trade_step = self._create_trade_step('等比例配置首次買進', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': target_stock_pct,
                    'trade_step': trade_step
                })
            if target_bond_pct > 0 and self.hedge_ticker:
                trade_step = self._create_trade_step('等比例配置首次買進', state, [
                    {'name': '目標債券比例', 'value': target_bond_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.hedge_ticker,
                    'percent': target_bond_pct,
                    'trade_step': trade_step
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
                trade_step = self._create_trade_step('等比例配置增持股票', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '當前股票比例', 'value': current_stock_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': stock_diff,
                    'trade_step': trade_step
                })
            else:
                # 需要減持股票
                trade_step = self._create_trade_step('等比例配置減持股票', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '當前股票比例', 'value': current_stock_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': abs(stock_diff),
                    'trade_step': trade_step
                })
        
        if self.hedge_ticker and abs(bond_diff) > threshold:
            if bond_diff > 0:
                # 需要增持債券
                trade_step = self._create_trade_step('等比例配置增持債券', state, [
                    {'name': '目標債券比例', 'value': target_bond_pct},
                    {'name': '當前債券比例', 'value': current_bond_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.hedge_ticker,
                    'percent': bond_diff,
                    'trade_step': trade_step
                })
            else:
                # 需要減持債券
                trade_step = self._create_trade_step('等比例配置減持債券', state, [
                    {'name': '目標債券比例', 'value': target_bond_pct},
                    {'name': '當前債券比例', 'value': current_bond_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'sell',
                    'ticker': self.hedge_ticker,
                    'percent': abs(bond_diff),
                    'trade_step': trade_step
                })
        
        return orders


class TSMCProportionalAllocationStrategy(ProportionalAllocationStrategy):
    """台積電等比例配置策略（2330:短期美債，根據景氣燈號等比例配置）"""
    
    def __init__(self, stock_ticker='2330', hedge_ticker='00865B'):
        super().__init__(stock_ticker, hedge_ticker)


class BuyAndHoldStrategy:
    """買進並持有策略（基準策略）"""
    
    def __init__(self, stock_ticker='006208'):
        """
        初始化策略
        
        參數:
        - stock_ticker: 股票代號（預設 '006208'，富邦台50）
        """
        self.stock_ticker = stock_ticker
        self.bought = False
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """
        買進並持有策略：只在第一次有機會時買進，之後不再交易
        
        參數:
        - state: 策略狀態字典（此策略不使用）
        - date: 交易日期
        - price_dict: 價格字典
        - positions: 當前持倉字典（可選）
        - portfolio_value: 當前投資組合總價值（可選）
        
        回傳:
        - 訂單列表
        """
        orders = []
        
        # 只在第一次買進
        if not self.bought:
            if self.stock_ticker in price_dict:
                # BuyAndHoldStrategy 不使用 CycleStrategy 的 _create_trade_step，需要手動建立
                trade_step = {
                    'reason': '買進並持有',
                    'conditions': [
                        {'name': '策略類型', 'value': 'BuyAndHold'}
                    ]
                }
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': 1.0,  # 100% 買進
                    'trade_step': trade_step
                })
                self.bought = True
        
        return orders


class M1BFilterStrategy(CycleStrategy):
    """M1B 動能濾網策略基類"""
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """
        M1B 動能濾網策略：在紅燈區加入 M1B 動能檢測
        
        參數:
        - state: 策略狀態字典（包含 score, m1b_yoy_momentum）
        - date: 交易日期
        - price_dict: 價格字典
        - positions: 當前持倉字典（可選）
        - portfolio_value: 當前投資組合總價值（可選）
        
        回傳:
        - 訂單列表
        """
        orders = []
        score = state.get('score')
        m1b_momentum = state.get('m1b_yoy_momentum')
        
        if score is None:
            return orders
        
        # SCORE <= 16（藍燈）：買進股票，賣出避險資產
        if score <= 16 and not state.get('state', False):
            trade_step = self._create_trade_step('藍燈買進', state)
            orders.append({
                'action': 'buy',
                'ticker': self.stock_ticker,
                'percent': 1.0,
                'trade_step': trade_step
            })
            state['state'] = True
            
            if self.hedge_ticker and state.get('hedge_state', False):
                hedge_trade_step = self._create_trade_step('藍燈賣出避險資產', state)
                orders.append({
                    'action': 'sell',
                    'ticker': self.hedge_ticker,
                    'percent': 1.0,
                    'trade_step': hedge_trade_step
                })
                state['hedge_state'] = False
        
        # SCORE >= 32（紅燈）：加入 M1B 動能濾網
        elif score >= 32:
            if m1b_momentum is not None and m1b_momentum < 0:
                # 價量背離：清倉離場
                if state.get('state', False):
                    trade_step = self._create_trade_step('價量背離清倉', state, [
                        {'name': 'M1B年增率動能', 'value': m1b_momentum}
                    ])
                    orders.append({
                        'action': 'sell',
                        'ticker': self.stock_ticker,
                        'percent': 1.0,
                        'trade_step': trade_step
                    })
                    state['state'] = False
                
                if self.hedge_ticker and state.get('hedge_state', False):
                    hedge_trade_step = self._create_trade_step('價量背離清倉避險資產', state, [
                        {'name': 'M1B年增率動能', 'value': m1b_momentum}
                    ])
                    orders.append({
                        'action': 'sell',
                        'ticker': self.hedge_ticker,
                        'percent': 1.0,
                        'trade_step': hedge_trade_step
                    })
                    state['hedge_state'] = False
            else:
                # M1B 動能正常或無資料：減碼至 50%
                if state.get('state', False):
                    # 檢查當前持倉比例
                    if positions and portfolio_value:
                        current_value = positions.get(self.stock_ticker, 0) * price_dict.get(self.stock_ticker, 0)
                        current_pct = current_value / portfolio_value if portfolio_value > 0 else 0
                        if current_pct > 0.55:  # 如果超過 55%，減碼至 50%
                            trade_step = self._create_trade_step('紅燈減碼至50%', state, [
                                {'name': 'M1B年增率動能', 'value': m1b_momentum if m1b_momentum is not None else '無資料'},
                                {'name': '當前股票比例', 'value': current_pct}
                            ])
                            orders.append({
                                'action': 'sell',
                                'ticker': self.stock_ticker,
                                'percent': (current_pct - 0.5) / current_pct,
                                'trade_step': trade_step
                            })
                    else:
                        # 如果沒有持倉資訊，賣出 50%
                        trade_step = self._create_trade_step('紅燈減碼至50%', state, [
                            {'name': 'M1B年增率動能', 'value': m1b_momentum if m1b_momentum is not None else '無資料'}
                        ])
                        orders.append({
                            'action': 'sell',
                            'ticker': self.stock_ticker,
                            'percent': 0.5,
                            'trade_step': trade_step
                        })
                    
                    # 處理避險資產（如果有）：減碼時同步買進避險資產，補足到100%（50%股票 + 50%避險資產）
                    if self.hedge_ticker:
                        # 計算當前避險資產持倉比例
                        if positions and portfolio_value:
                            current_hedge_value = positions.get(self.hedge_ticker, 0) * price_dict.get(self.hedge_ticker, 0)
                            current_hedge_pct = current_hedge_value / portfolio_value if portfolio_value > 0 else 0
                            target_hedge_pct = 0.5  # 目標是50%避險資產
                            
                            # 計算需要調整的避險資產比例
                            hedge_diff = target_hedge_pct - current_hedge_pct
                            threshold = 0.05  # 5% 的容許誤差
                            
                            if abs(hedge_diff) > threshold and hedge_diff > 0:
                                hedge_trade_step = self._create_trade_step('紅燈買進避險資產至50%', state, [
                                    {'name': 'M1B年增率動能', 'value': m1b_momentum if m1b_momentum is not None else '無資料'},
                                    {'name': '當前避險資產比例', 'value': current_hedge_pct},
                                    {'name': '目標避險資產比例', 'value': target_hedge_pct}
                                ])
                                orders.append({
                                    'action': 'buy',
                                    'ticker': self.hedge_ticker,
                                    'percent': hedge_diff,
                                    'is_hedge_buy': True,
                                    'trade_step': hedge_trade_step
                                })
                                state['hedge_state'] = True
                        else:
                            # 首次配置：買進50%避險資產
                            hedge_trade_step = self._create_trade_step('紅燈買進避險資產至50%', state, [
                                {'name': 'M1B年增率動能', 'value': m1b_momentum if m1b_momentum is not None else '無資料'}
                            ])
                            orders.append({
                                'action': 'buy',
                                'ticker': self.hedge_ticker,
                                'percent': 0.5,
                                'is_hedge_buy': True,
                                'trade_step': hedge_trade_step
                            })
                            state['hedge_state'] = True
        
        # 16 < SCORE < 38：首次進入時買進股票
        elif 16 < score < 38:
            if state.get('a', 0) == 0:
                state['a'] = 1
                if not state.get('state', False):
                    trade_step = self._create_trade_step('首次進入買進', state)
                    orders.append({
                        'action': 'buy',
                        'ticker': self.stock_ticker,
                        'percent': 1.0,
                        'trade_step': trade_step
                    })
                    state['state'] = True
        
        return orders


class M1BFilterCashStrategy(M1BFilterStrategy):
    """M1B 濾網 + 現金避險策略"""
    
    def __init__(self, stock_ticker='006208'):
        super().__init__(stock_ticker, None)


class M1BFilterBondStrategy(M1BFilterStrategy):
    """M1B 濾網 + 短債避險策略"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        super().__init__(stock_ticker, hedge_ticker)


class M1BFilterProportionalStrategy(M1BFilterStrategy, ProportionalAllocationStrategy):
    """M1B 濾網 + 等比例配置策略"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        M1BFilterStrategy.__init__(self, stock_ticker, hedge_ticker)
        ProportionalAllocationStrategy.__init__(self, stock_ticker, hedge_ticker)
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """
        結合 M1B 濾網和等比例配置的邏輯
        """
        orders = []
        score = state.get('score')
        m1b_momentum = state.get('m1b_yoy_momentum')
        
        if score is None:
            return orders
        
        # 紅燈區且 M1B 動能 < 0：清倉股票，全部投入債券
        if score >= 32 and m1b_momentum is not None and m1b_momentum < 0:
            # 清倉股票
            if positions and self.stock_ticker in positions and positions[self.stock_ticker] > 0:
                trade_step = self._create_trade_step('價量背離清倉股票', state, [
                    {'name': 'M1B年增率動能', 'value': m1b_momentum}
                ])
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': 1.0,
                    'trigger_hedge_buy': True,
                    'hedge_ticker': self.hedge_ticker,
                    'trade_step': trade_step
                })
            
            # 確保買進100%債券
            if self.hedge_ticker:
                # 計算當前債券持倉比例
                if positions and portfolio_value and portfolio_value > 0:
                    current_bond_value = positions.get(self.hedge_ticker, 0) * price_dict.get(self.hedge_ticker, 0)
                    current_bond_pct = current_bond_value / portfolio_value
                    if current_bond_pct < 0.95:  # 容許5%誤差
                        hedge_trade_step = self._create_trade_step('價量背離買進100%債券', state, [
                            {'name': 'M1B年增率動能', 'value': m1b_momentum},
                            {'name': '當前債券比例', 'value': current_bond_pct}
                        ])
                        orders.append({
                            'action': 'buy',
                            'ticker': self.hedge_ticker,
                            'percent': 1.0 - current_bond_pct,
                            'is_hedge_buy': True,
                            'trade_step': hedge_trade_step
                        })
                else:
                    # 首次配置：100%債券
                    hedge_trade_step = self._create_trade_step('價量背離買進100%債券', state, [
                        {'name': 'M1B年增率動能', 'value': m1b_momentum}
                    ])
                    orders.append({
                        'action': 'buy',
                        'ticker': self.hedge_ticker,
                        'percent': 1.0,
                        'is_hedge_buy': True,
                        'trade_step': hedge_trade_step
                    })
            
            state['state'] = False
            state['hedge_state'] = True
            return orders
        
        # 其他情況使用等比例配置邏輯
        return ProportionalAllocationStrategy.generate_orders(self, state, date, price_dict, positions, portfolio_value)


class DynamicPositionStrategy(CycleStrategy):
    """動態倉位調整策略基類"""
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """
        動態倉位調整策略：根據 Score 和動能調整倉位比例
        
        參數:
        - state: 策略狀態字典（包含 score, score_momentum, m1b_yoy_momentum）
        - date: 交易日期
        - price_dict: 價格字典
        - positions: 當前持倉字典（可選）
        - portfolio_value: 當前投資組合總價值（可選）
        
        回傳:
        - 訂單列表
        """
        orders = []
        score = state.get('score')
        score_momentum = state.get('score_momentum')
        m1b_momentum = state.get('m1b_yoy_momentum')
        
        if score is None:
            return orders
        
        # 計算目標倉位
        target_position = 0.0
        
        # 藍燈（9-16分）：100% 倉位
        if 9 <= score <= 16:
            target_position = 1.0
        
        # 黃藍燈（17-22分）：根據動能調整
        elif 17 <= score <= 22:
            if score_momentum is not None and score_momentum < -2:
                # 分數驟降：50% 倉位
                target_position = 0.5
            else:
                # 正常：100% 倉位
                target_position = 1.0
        
        # 綠燈（23-31分）：根據動能調整
        elif 23 <= score <= 31:
            if score_momentum is not None and score_momentum < -2:
                # 分數驟降：50% 倉位
                target_position = 0.5
            else:
                # 正常：100% 倉位
                target_position = 1.0
        
        # 黃紅燈（32-37分）：根據 M1B 動能調整
        elif 32 <= score <= 37:
            if m1b_momentum is not None and m1b_momentum < 0:
                # 價量背離：0% 倉位（清倉）
                target_position = 0.0
            else:
                # 正常：50% 倉位
                target_position = 0.5
        
        # 紅燈（38-45分）：根據 M1B 動能調整
        elif score >= 38:
            if m1b_momentum is not None and m1b_momentum < 0:
                # 價量背離：0% 倉位（清倉）
                target_position = 0.0
            else:
                # 正常：50% 倉位
                target_position = 0.5
        
        # 根據目標倉位產生訂單
        if positions is None or portfolio_value is None or portfolio_value <= 0:
            # 首次配置
            if target_position > 0:
                # 建立交易步驟
                reason = '動態倉位首次配置'
                additional_conditions = [{'name': '目標倉位', 'value': target_position}]
                if score_momentum is not None:
                    additional_conditions.append({'name': '景氣分數動能', 'value': score_momentum})
                if m1b_momentum is not None:
                    additional_conditions.append({'name': 'M1B年增率動能', 'value': m1b_momentum})
                
                trade_step = self._create_trade_step(reason, state, additional_conditions)
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': target_position,
                    'target_position_pct': target_position,
                    'trade_step': trade_step
                })
                state['state'] = True
        else:
            # 計算當前持倉比例
            current_stock_value = positions.get(self.stock_ticker, 0) * price_dict.get(self.stock_ticker, 0)
            current_pct = current_stock_value / portfolio_value if portfolio_value > 0 else 0
            
            # 計算需要調整的比例
            diff = target_position - current_pct
            threshold = 0.05  # 5% 的容許誤差
            
            if abs(diff) > threshold:
                if diff > 0:
                    # 需要增持
                    reason = '動態倉位增持'
                    additional_conditions = [
                        {'name': '目標倉位', 'value': target_position},
                        {'name': '當前倉位', 'value': current_pct}
                    ]
                    if score_momentum is not None:
                        additional_conditions.append({'name': '景氣分數動能', 'value': score_momentum})
                    if m1b_momentum is not None:
                        additional_conditions.append({'name': 'M1B年增率動能', 'value': m1b_momentum})
                    
                    trade_step = self._create_trade_step(reason, state, additional_conditions)
                    orders.append({
                        'action': 'buy',
                        'ticker': self.stock_ticker,
                        'percent': diff,
                        'target_position_pct': target_position,
                        'trade_step': trade_step
                    })
                    state['state'] = True
                else:
                    # 需要減持
                    reason = '動態倉位減持'
                    additional_conditions = [
                        {'name': '目標倉位', 'value': target_position},
                        {'name': '當前倉位', 'value': current_pct}
                    ]
                    if score_momentum is not None:
                        additional_conditions.append({'name': '景氣分數動能', 'value': score_momentum})
                    if m1b_momentum is not None:
                        additional_conditions.append({'name': 'M1B年增率動能', 'value': m1b_momentum})
                    
                    trade_step = self._create_trade_step(reason, state, additional_conditions)
                    orders.append({
                        'action': 'sell',
                        'ticker': self.stock_ticker,
                        'percent': abs(diff),
                        'target_position_pct': target_position,
                        'trade_step': trade_step
                    })
                    if target_position == 0:
                        state['state'] = False
        
        # 處理避險資產（如果有）
        if self.hedge_ticker:
            if target_position == 0:
                # 清倉時也清空避險資產
                if state.get('hedge_state', False):
                    hedge_trade_step = self._create_trade_step('清倉避險資產', state)
                    orders.append({
                        'action': 'sell',
                        'ticker': self.hedge_ticker,
                        'percent': 1.0,
                        'trade_step': hedge_trade_step
                    })
                    state['hedge_state'] = False
            elif target_position < 1.0:
                # 減碼時：用賣出股票產生的現金買進避險資產，補足到100%
                # 計算需要買進的避險資產比例
                hedge_target_pct = 1.0 - target_position
                
                # 計算當前避險資產持倉比例
                if positions is not None and portfolio_value is not None and portfolio_value > 0:
                    current_hedge_value = positions.get(self.hedge_ticker, 0) * price_dict.get(self.hedge_ticker, 0)
                    current_hedge_pct = current_hedge_value / portfolio_value if portfolio_value > 0 else 0
                    
                    # 計算需要調整的避險資產比例
                    hedge_diff = hedge_target_pct - current_hedge_pct
                    threshold = 0.05  # 5% 的容許誤差
                    
                    if abs(hedge_diff) > threshold:
                        if hedge_diff > 0:
                            # 需要買進避險資產
                            hedge_trade_step = self._create_trade_step('動態倉位增持避險資產', state, [
                                {'name': '目標避險資產比例', 'value': hedge_target_pct},
                                {'name': '當前避險資產比例', 'value': current_hedge_pct}
                            ])
                            orders.append({
                                'action': 'buy',
                                'ticker': self.hedge_ticker,
                                'percent': hedge_diff,
                                'target_position_pct': hedge_target_pct,
                                'is_hedge_buy': True,
                                'trade_step': hedge_trade_step
                            })
                            state['hedge_state'] = True
                        else:
                            # 需要賣出避險資產（如果持倉過多）
                            hedge_trade_step = self._create_trade_step('動態倉位減持避險資產', state, [
                                {'name': '目標避險資產比例', 'value': hedge_target_pct},
                                {'name': '當前避險資產比例', 'value': current_hedge_pct}
                            ])
                            orders.append({
                                'action': 'sell',
                                'ticker': self.hedge_ticker,
                                'percent': abs(hedge_diff),
                                'target_position_pct': hedge_target_pct,
                                'trade_step': hedge_trade_step
                            })
                else:
                    # 首次配置：如果目標倉位 < 100%，買進避險資產
                    if hedge_target_pct > 0:
                        hedge_trade_step = self._create_trade_step('動態倉位首次配置避險資產', state, [
                            {'name': '目標避險資產比例', 'value': hedge_target_pct}
                        ])
                        orders.append({
                            'action': 'buy',
                            'ticker': self.hedge_ticker,
                            'percent': hedge_target_pct,
                            'target_position_pct': hedge_target_pct,
                            'is_hedge_buy': True,
                            'trade_step': hedge_trade_step
                        })
                        state['hedge_state'] = True
        
        return orders


class DynamicPositionCashStrategy(DynamicPositionStrategy):
    """動態倉位 + 現金避險策略"""
    
    def __init__(self, stock_ticker='006208'):
        super().__init__(stock_ticker, None)


class DynamicPositionBondStrategy(DynamicPositionStrategy):
    """動態倉位 + 短債避險策略"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        super().__init__(stock_ticker, hedge_ticker)


class DynamicPositionProportionalStrategy(DynamicPositionStrategy, ProportionalAllocationStrategy):
    """動態倉位 + 等比例配置策略"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        DynamicPositionStrategy.__init__(self, stock_ticker, hedge_ticker)
        ProportionalAllocationStrategy.__init__(self, stock_ticker, hedge_ticker)
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """
        結合動態倉位和等比例配置的邏輯
        """
        orders = []
        score = state.get('score')
        score_momentum = state.get('score_momentum')
        m1b_momentum = state.get('m1b_yoy_momentum')
        
        if score is None:
            return orders
        
        # 計算目標股票倉位
        target_stock_pct = 0.0
        
        # 藍燈（9-16分）：100% 倉位
        if 9 <= score <= 16:
            target_stock_pct = 1.0
        
        # 黃藍燈（17-22分）：根據動能調整
        elif 17 <= score <= 22:
            if score_momentum is not None and score_momentum < -2:
                target_stock_pct = 0.5
            else:
                target_stock_pct = 1.0
        
        # 綠燈（23-31分）：根據動能調整
        elif 23 <= score <= 31:
            if score_momentum is not None and score_momentum < -2:
                target_stock_pct = 0.5
            else:
                target_stock_pct = 1.0
        
        # 黃紅燈（32-37分）：根據 M1B 動能調整
        elif 32 <= score <= 37:
            if m1b_momentum is not None and m1b_momentum < 0:
                target_stock_pct = 0.0
            else:
                target_stock_pct = 0.5
        
        # 紅燈（38-45分）：根據 M1B 動能調整
        elif score >= 38:
            if m1b_momentum is not None and m1b_momentum < 0:
                target_stock_pct = 0.0
            else:
                target_stock_pct = 0.5
        
        # 根據燈號等級調整目標配置（結合等比例配置邏輯）
        signal_level = self._get_signal_level(score)
        if signal_level:
            base_allocation = self.allocation_rules.get(signal_level, {'stock_pct': 0.6, 'bond_pct': 0.4})
            base_stock_pct = base_allocation['stock_pct']
            # 取兩者較小值（更保守）
            target_stock_pct = min(target_stock_pct, base_stock_pct)
        
        target_bond_pct = 1.0 - target_stock_pct
        
        # 產生調整訂單
        signal_level = self._get_signal_level(score)
        if positions is None or portfolio_value is None or portfolio_value <= 0:
            if target_stock_pct > 0:
                trade_step = self._create_trade_step('動態等比例配置首次買進', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '燈號等級', 'value': signal_level if signal_level else '未知'}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': target_stock_pct,
                    'trade_step': trade_step
                })
            if target_bond_pct > 0 and self.hedge_ticker:
                trade_step = self._create_trade_step('動態等比例配置首次買進', state, [
                    {'name': '目標債券比例', 'value': target_bond_pct},
                    {'name': '燈號等級', 'value': signal_level if signal_level else '未知'}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.hedge_ticker,
                    'percent': target_bond_pct,
                    'is_hedge_buy': True,
                    'trade_step': trade_step
                })
        else:
            current_stock_value = positions.get(self.stock_ticker, 0) * price_dict.get(self.stock_ticker, 0)
            current_bond_value = positions.get(self.hedge_ticker, 0) * price_dict.get(self.hedge_ticker, 0) if self.hedge_ticker else 0
            
            current_stock_pct = current_stock_value / portfolio_value if portfolio_value > 0 else 0
            current_bond_pct = current_bond_value / portfolio_value if portfolio_value > 0 else 0
            
            stock_diff = target_stock_pct - current_stock_pct
            bond_diff = target_bond_pct - current_bond_pct
            
            threshold = 0.05
            
            if abs(stock_diff) > threshold:
                if stock_diff > 0:
                    trade_step = self._create_trade_step('動態等比例配置增持股票', state, [
                        {'name': '目標股票比例', 'value': target_stock_pct},
                        {'name': '當前股票比例', 'value': current_stock_pct},
                        {'name': '燈號等級', 'value': signal_level if signal_level else '未知'}
                    ])
                    orders.append({
                        'action': 'buy',
                        'ticker': self.stock_ticker,
                        'percent': stock_diff,
                        'trade_step': trade_step
                    })
                else:
                    trade_step = self._create_trade_step('動態等比例配置減持股票', state, [
                        {'name': '目標股票比例', 'value': target_stock_pct},
                        {'name': '當前股票比例', 'value': current_stock_pct},
                        {'name': '燈號等級', 'value': signal_level if signal_level else '未知'}
                    ])
                    orders.append({
                        'action': 'sell',
                        'ticker': self.stock_ticker,
                        'percent': abs(stock_diff),
                        'trade_step': trade_step
                    })
            
            if self.hedge_ticker and abs(bond_diff) > threshold:
                if bond_diff > 0:
                    trade_step = self._create_trade_step('動態等比例配置增持債券', state, [
                        {'name': '目標債券比例', 'value': target_bond_pct},
                        {'name': '當前債券比例', 'value': current_bond_pct},
                        {'name': '燈號等級', 'value': signal_level if signal_level else '未知'}
                    ])
                    orders.append({
                        'action': 'buy',
                        'ticker': self.hedge_ticker,
                        'percent': bond_diff,
                        'is_hedge_buy': True,
                        'trade_step': trade_step
                    })
                else:
                    trade_step = self._create_trade_step('動態等比例配置減持債券', state, [
                        {'name': '目標債券比例', 'value': target_bond_pct},
                        {'name': '當前債券比例', 'value': current_bond_pct},
                        {'name': '燈號等級', 'value': signal_level if signal_level else '未知'}
                    ])
                    orders.append({
                        'action': 'sell',
                        'ticker': self.hedge_ticker,
                        'percent': abs(bond_diff),
                        'trade_step': trade_step
                    })
        
        return orders


class MultiplierAllocationStrategy(CycleStrategy):
    """倍數放大配置策略（根據燈號等級遞減倉位）"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        super().__init__(stock_ticker, hedge_ticker)
        
        # 倍數遞減配置規則
        self.allocation_rules = {
            'blue': {'stock_pct': 1.0, 'bond_pct': 0.0},        # 藍燈（9-16）：100% 股票, 0% 債券
            'yellow_blue': {'stock_pct': 0.75, 'bond_pct': 0.25}, # 黃藍燈（17-22）：75% 股票, 25% 債券
            'green': {'stock_pct': 0.5, 'bond_pct': 0.5},       # 綠燈（23-31）：50% 股票, 50% 債券
            'yellow_red': {'stock_pct': 0.25, 'bond_pct': 0.75}, # 黃紅燈（32-37）：25% 股票, 75% 債券
            'red': {'stock_pct': 0.0, 'bond_pct': 1.0}         # 紅燈（38-45）：0% 股票, 100% 債券
        }
    
    def _get_signal_level(self, score):
        """根據景氣燈號分數判斷燈號等級（使用官方標準）"""
        if score is None:
            return None
        
        if 9 <= score <= 16:
            return 'blue'  # 藍燈
        elif 17 <= score <= 22:
            return 'yellow_blue'  # 黃藍燈
        elif 23 <= score <= 31:
            return 'green'  # 綠燈
        elif 32 <= score <= 37:
            return 'yellow_red'  # 黃紅燈
        elif score >= 38:
            return 'red'  # 紅燈
        else:
            return None  # 分數 < 9，可能是資料缺失
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """根據燈號等級產生倍數遞減配置訂單"""
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
            if target_stock_pct > 0:
                trade_step = self._create_trade_step('倍數放大首次配置', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': target_stock_pct,
                    'target_position_pct': target_stock_pct,
                    'trade_step': trade_step
                })
            if target_bond_pct > 0 and self.hedge_ticker:
                trade_step = self._create_trade_step('倍數放大首次配置', state, [
                    {'name': '目標債券比例', 'value': target_bond_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.hedge_ticker,
                    'percent': target_bond_pct,
                    'target_position_pct': target_bond_pct,
                    'is_hedge_buy': True,
                    'trade_step': trade_step
                })
            return orders
        
        # 計算當前持倉價值和比例
        current_stock_value = positions.get(self.stock_ticker, 0) * price_dict.get(self.stock_ticker, 0)
        current_bond_value = positions.get(self.hedge_ticker, 0) * price_dict.get(self.hedge_ticker, 0) if self.hedge_ticker else 0
        
        current_stock_pct = current_stock_value / portfolio_value if portfolio_value > 0 else 0
        current_bond_pct = current_bond_value / portfolio_value if portfolio_value > 0 else 0
        
        # 計算需要調整的比例
        stock_diff = target_stock_pct - current_stock_pct
        bond_diff = target_bond_pct - current_bond_pct
        
        threshold = 0.05  # 5% 的容許誤差
        
        # 產生調整訂單
        if abs(stock_diff) > threshold:
            if stock_diff > 0:
                trade_step = self._create_trade_step('倍數放大增持股票', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '當前股票比例', 'value': current_stock_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': stock_diff,
                    'target_position_pct': target_stock_pct,
                    'trade_step': trade_step
                })
            else:
                trade_step = self._create_trade_step('倍數放大減持股票', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '當前股票比例', 'value': current_stock_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': abs(stock_diff),
                    'target_position_pct': target_stock_pct,
                    'trade_step': trade_step
                })
        
        if self.hedge_ticker and abs(bond_diff) > threshold:
            if bond_diff > 0:
                trade_step = self._create_trade_step('倍數放大增持債券', state, [
                    {'name': '目標債券比例', 'value': target_bond_pct},
                    {'name': '當前債券比例', 'value': current_bond_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.hedge_ticker,
                    'percent': bond_diff,
                    'target_position_pct': target_bond_pct,
                    'is_hedge_buy': True,
                    'trade_step': trade_step
                })
            else:
                trade_step = self._create_trade_step('倍數放大減持債券', state, [
                    {'name': '目標債券比例', 'value': target_bond_pct},
                    {'name': '當前債券比例', 'value': current_bond_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'sell',
                    'ticker': self.hedge_ticker,
                    'percent': abs(bond_diff),
                    'target_position_pct': target_bond_pct,
                    'trade_step': trade_step
                })
        
        return orders


class MultiplierAllocationCashStrategy(MultiplierAllocationStrategy):
    """倍數放大 + 現金避險策略（紅燈時 100% 現金）"""
    
    def __init__(self, stock_ticker='006208'):
        super().__init__(stock_ticker, None)
    
    def generate_orders(self, state, date, price_dict, positions=None, portfolio_value=None):
        """倍數放大 + 現金避險：紅燈時全部賣出，持有現金"""
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
        # 現金策略：不需要買進避險資產，紅燈時全部賣出即可
        
        # 如果沒有持倉資訊，首次配置
        if positions is None or portfolio_value is None or portfolio_value <= 0:
            if target_stock_pct > 0:
                trade_step = self._create_trade_step('倍數放大現金策略首次買進', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': target_stock_pct,
                    'target_position_pct': target_stock_pct,
                    'trade_step': trade_step
                })
            return orders
        
        # 計算當前持倉價值和比例
        current_stock_value = positions.get(self.stock_ticker, 0) * price_dict.get(self.stock_ticker, 0)
        current_stock_pct = current_stock_value / portfolio_value if portfolio_value > 0 else 0
        
        # 計算需要調整的比例
        stock_diff = target_stock_pct - current_stock_pct
        
        threshold = 0.05  # 5% 的容許誤差
        
        # 產生調整訂單
        if abs(stock_diff) > threshold:
            if stock_diff > 0:
                trade_step = self._create_trade_step('倍數放大現金策略增持股票', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '當前股票比例', 'value': current_stock_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'buy',
                    'ticker': self.stock_ticker,
                    'percent': stock_diff,
                    'target_position_pct': target_stock_pct,
                    'trade_step': trade_step
                })
            else:
                trade_step = self._create_trade_step('倍數放大現金策略減持股票', state, [
                    {'name': '目標股票比例', 'value': target_stock_pct},
                    {'name': '當前股票比例', 'value': current_stock_pct},
                    {'name': '燈號等級', 'value': signal_level}
                ])
                orders.append({
                    'action': 'sell',
                    'ticker': self.stock_ticker,
                    'percent': abs(stock_diff),
                    'target_position_pct': target_stock_pct,
                    'trade_step': trade_step
                })
        
        return orders


class MultiplierAllocationBondStrategy(MultiplierAllocationStrategy):
    """倍數放大 + 短債避險策略（紅燈時 100% 債券）"""
    
    def __init__(self, stock_ticker='006208', hedge_ticker='00865B'):
        super().__init__(stock_ticker, hedge_ticker)

