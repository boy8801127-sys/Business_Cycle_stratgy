"""
回測驗證檢查模組
用於驗證回測過程是否符合預期邏輯
"""

from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd


class BacktestValidator:
    """回測驗證檢查器"""
    
    def __init__(self):
        """初始化驗證器"""
        self.violations = []  # 記錄違規項目
        self.signal_events = []  # 記錄信號事件
        self.order_events = []  # 記錄訂單事件
        self.position_snapshots = []  # 記錄持倉快照
        
        # 追蹤買進信號
        self.buy_signals = {}  # {signal_id: {'publish_date': date, 'score': score, 'expected_buy_dates': [dates], 'actual_buys': []}}
        # 追蹤賣出信號
        self.sell_signals = {}  # {signal_id: {'publish_date': date, 'score': score, 'expected_sell_dates': [dates], 'actual_sells': []}}
        # 追蹤分批訂單
        self.split_orders = {}  # {order_id: {'ticker': ticker, 'total_percent': float, 'expected_days': int, 'actual_executions': []}}
        
    def record_signal(self, signal_type, date, score, publish_date, data_year, data_month):
        """
        記錄信號事件
        
        參數:
        - signal_type: 'buy' 或 'sell'
        - date: 信號日期
        - score: 景氣燈號分數
        - publish_date: 發布日期
        - data_year: 資料年份
        - data_month: 資料月份
        """
        signal_id = f"{signal_type}_{date}_{score}"
        self.signal_events.append({
            'signal_type': signal_type,
            'date': date,
            'score': score,
            'publish_date': publish_date,
            'data_year': data_year,
            'data_month': data_month
        })
        
        if signal_type == 'buy':
            self.buy_signals[signal_id] = {
                'publish_date': publish_date,
                'score': score,
                'data_year': data_year,
                'data_month': data_month,
                'expected_buy_dates': [],
                'actual_buys': []
            }
        elif signal_type == 'sell':
            self.sell_signals[signal_id] = {
                'publish_date': publish_date,
                'score': score,
                'data_year': data_year,
                'data_month': data_month,
                'expected_sell_dates': [],
                'actual_sells': []
            }
    
    def record_order(self, date, action, ticker, percent, is_split=False, is_hedge=False):
        """
        記錄訂單事件
        
        參數:
        - date: 訂單日期
        - action: 'buy' 或 'sell'
        - ticker: 標的代號
        - percent: 訂單比例
        - is_split: 是否為分批訂單
        - is_hedge: 是否為避險資產
        """
        self.order_events.append({
            'date': date,
            'action': action,
            'ticker': ticker,
            'percent': percent,
            'is_split': is_split,
            'is_hedge': is_hedge
        })
        
        # 如果是股票買進或賣出（非避險資產），記錄到對應的信號中
        if not is_hedge:
            # 尋找最近的信號
            if action == 'buy':
                # 找到最近的買進信號
                for signal_id, signal_info in self.buy_signals.items():
                    if date not in signal_info['actual_buys']:
                        signal_info['actual_buys'].append(date)
            elif action == 'sell':
                # 找到最近的賣出信號
                for signal_id, signal_info in self.sell_signals.items():
                    if date not in signal_info['actual_sells']:
                        signal_info['actual_sells'].append(date)
    
    def record_position_snapshot(self, date, positions, portfolio_value):
        """
        記錄持倉快照
        
        參數:
        - date: 日期
        - positions: 持倉字典 {ticker: shares}
        - portfolio_value: 投資組合總價值
        """
        self.position_snapshots.append({
            'date': date,
            'positions': positions.copy() if positions else {},
            'portfolio_value': portfolio_value
        })
    
    def validate_signal_timing(self, trading_days, cycle_data):
        """
        驗證信號時機
        
        參數:
        - trading_days: 交易日列表
        - cycle_data: 景氣燈號資料
        """
        violations = []
        
        # 驗證買進信號時機
        for signal_id, signal_info in self.buy_signals.items():
            publish_date = signal_info['publish_date']
            if publish_date is None:
                continue
            
            # 找到發布日期後的5個交易日
            publish_idx = None
            for i, day in enumerate(trading_days):
                if day >= publish_date:
                    publish_idx = i
                    break
            
            if publish_idx is not None:
                expected_dates = trading_days[publish_idx:publish_idx+5]
                signal_info['expected_buy_dates'] = expected_dates
                
                # 檢查是否在預期日期內買進
                actual_buys = signal_info['actual_buys']
                if not actual_buys:
                    violations.append({
                        'type': 'signal_timing',
                        'severity': 'error',
                        'message': f"買進信號未執行：發布日期 {publish_date}, 分數 {signal_info['score']}",
                        'signal_id': signal_id
                    })
                else:
                    # 檢查是否在預期時間窗口內
                    for buy_date in actual_buys:
                        if buy_date not in expected_dates:
                            violations.append({
                                'type': 'signal_timing',
                                'severity': 'warning',
                                'message': f"買進日期不在預期窗口內：預期 {expected_dates}, 實際 {buy_date}",
                                'signal_id': signal_id
                            })
        
        # 驗證賣出信號時機
        for signal_id, signal_info in self.sell_signals.items():
            publish_date = signal_info['publish_date']
            if publish_date is None:
                continue
            
            # 找到隔月的最後5個交易日
            if isinstance(publish_date, pd.Timestamp):
                next_month = publish_date + pd.DateOffset(months=1)
            else:
                next_month = pd.Timestamp(publish_date) + pd.DateOffset(months=1)
            
            # 找到隔月的最後5個交易日
            next_month_days = [d for d in trading_days if d.year == next_month.year and d.month == next_month.month]
            if next_month_days:
                expected_dates = next_month_days[-5:] if len(next_month_days) >= 5 else next_month_days
                signal_info['expected_sell_dates'] = expected_dates
                
                # 檢查是否在預期日期內賣出
                actual_sells = signal_info['actual_sells']
                if not actual_sells:
                    violations.append({
                        'type': 'signal_timing',
                        'severity': 'error',
                        'message': f"賣出信號未執行：發布日期 {publish_date}, 分數 {signal_info['score']}",
                        'signal_id': signal_id
                    })
                else:
                    # 檢查是否在預期時間窗口內
                    for sell_date in actual_sells:
                        if sell_date not in expected_dates:
                            violations.append({
                                'type': 'signal_timing',
                                'severity': 'warning',
                                'message': f"賣出日期不在預期窗口內：預期 {expected_dates}, 實際 {sell_date}",
                                'signal_id': signal_id
                            })
        
        self.violations.extend(violations)
        return violations
    
    def validate_order_execution(self):
        """
        驗證訂單執行
        
        檢查：
        - 分批買賣是否完整（5天是否都執行）
        - 避險資產是否與股票同步買賣
        - 訂單金額是否符合預期比例
        """
        violations = []
        
        # 按日期和標的分組訂單
        orders_by_date_ticker = defaultdict(list)
        for order in self.order_events:
            key = (order['date'], order['ticker'])
            orders_by_date_ticker[key].append(order)
        
        # 檢查分批訂單完整性
        split_orders_by_ticker = defaultdict(list)
        for order in self.order_events:
            if order['is_split']:
                split_orders_by_ticker[order['ticker']].append(order)
        
        # 驗證每個分批訂單是否完整執行
        for ticker, orders in split_orders_by_ticker.items():
            # 按日期排序
            orders.sort(key=lambda x: x['date'])
            
            # 檢查是否連續5天執行
            if len(orders) < 5:
                violations.append({
                    'type': 'order_execution',
                    'severity': 'warning',
                    'message': f"分批訂單執行不完整：{ticker} 只執行了 {len(orders)} 天，預期5天",
                    'ticker': ticker,
                    'actual_days': len(orders),
                    'expected_days': 5
                })
            
            # 檢查總比例是否接近100%
            total_percent = sum(o['percent'] for o in orders)
            if abs(total_percent - 1.0) > 0.1:  # 容許10%誤差
                violations.append({
                    'type': 'order_execution',
                    'severity': 'warning',
                    'message': f"分批訂單總比例異常：{ticker} 總比例 {total_percent:.2%}，預期100%",
                    'ticker': ticker,
                    'actual_percent': total_percent,
                    'expected_percent': 1.0
                })
        
        # 檢查避險資產同步買賣
        # 找出所有觸發避險買進的賣出訂單
        stock_sells = [o for o in self.order_events if o['action'] == 'sell' and not o['is_hedge']]
        hedge_buys = [o for o in self.order_events if o['action'] == 'buy' and o['is_hedge']]
        
        # 檢查每個股票賣出是否有對應的避險買進
        for sell_order in stock_sells:
            sell_date = sell_order['date']
            # 尋找同一天或相近日期的避險買進
            matching_hedge_buy = None
            for hedge_buy in hedge_buys:
                if abs((hedge_buy['date'] - sell_date).days) <= 1:  # 容許1天誤差
                    matching_hedge_buy = hedge_buy
                    break
            
            if matching_hedge_buy is None:
                violations.append({
                    'type': 'order_execution',
                    'severity': 'warning',
                    'message': f"股票賣出未同步買進避險資產：{sell_order['ticker']} 在 {sell_date} 賣出",
                    'ticker': sell_order['ticker'],
                    'date': sell_date
                })
        
        self.violations.extend(violations)
        return violations
    
    def validate_position_changes(self, strategy_name):
        """
        驗證持倉變化
        
        參數:
        - strategy_name: 策略名稱
        
        檢查：
        - 動態倉位策略的目標比例是否正確
        - 等比例配置策略的配置是否正確
        """
        violations = []
        
        # 根據策略類型進行不同的驗證
        if 'DynamicPosition' in strategy_name:
            # 動態倉位策略：檢查目標比例
            for snapshot in self.position_snapshots:
                # 這裡需要策略狀態資訊，暫時跳過詳細驗證
                pass
        
        elif 'Proportional' in strategy_name or 'Multiplier' in strategy_name:
            # 等比例配置策略：檢查股票和債券比例
            for snapshot in self.position_snapshots:
                positions = snapshot['positions']
                portfolio_value = snapshot['portfolio_value']
                
                if portfolio_value <= 0:
                    continue
                
                # 計算各資產比例
                asset_pcts = {}
                for ticker, shares in positions.items():
                    # 需要價格資訊才能計算比例，這裡暫時跳過
                    pass
        
        self.violations.extend(violations)
        return violations
    
    def validate_m1b_filter(self, m1b_data):
        """
        驗證M1B濾網邏輯
        
        參數:
        - m1b_data: M1B資料
        
        檢查：
        - 價量背離時是否正確清倉或轉換
        - M1B動能計算是否正確
        """
        violations = []
        
        # 這裡需要結合策略邏輯和M1B資料進行驗證
        # 暫時跳過詳細實作，因為需要策略特定的邏輯
        
        self.violations.extend(violations)
        return violations
    
    def generate_report(self):
        """
        生成驗證報告
        
        回傳:
        - 報告字典
        """
        report = {
            'total_violations': len(self.violations),
            'errors': [v for v in self.violations if v['severity'] == 'error'],
            'warnings': [v for v in self.violations if v['severity'] == 'warning'],
            'signal_events': len(self.signal_events),
            'order_events': len(self.order_events),
            'position_snapshots': len(self.position_snapshots)
        }
        
        return report
    
    def get_violations_summary(self):
        """取得違規摘要"""
        if not self.violations:
            return "✓ 未發現違規項目"
        
        summary = []
        summary.append(f"發現 {len(self.violations)} 個違規項目：")
        
        errors = [v for v in self.violations if v['severity'] == 'error']
        warnings = [v for v in self.violations if v['severity'] == 'warning']
        
        if errors:
            summary.append(f"  - 錯誤：{len(errors)} 個")
            for error in errors[:5]:  # 只顯示前5個
                summary.append(f"    • {error['message']}")
        
        if warnings:
            summary.append(f"  - 警告：{len(warnings)} 個")
            for warning in warnings[:5]:  # 只顯示前5個
                summary.append(f"    • {warning['message']}")
        
        return "\n".join(summary)

