"""
Orange 策略診斷腳本
用於檢查策略為什麼沒有產生交易，輸出詳細和摘要診斷信息
"""

import os
import sys
import pandas as pd
import numpy as np

# 添加專案根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backtesting.strategy_orange import OrangePredictionStrategy
except Exception as e:
    print(f"[Error] 無法導入策略模組: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def diagnose_strategy():
    """診斷策略執行情況"""
    try:
        print("=" * 80)
        print("Orange 策略診斷分析")
        print("=" * 80)
    except Exception as e:
        print(f"[Error] 診斷腳本初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 讀取數據
    csv_path = 'results/orange_analysis_data.csv'
    if not os.path.exists(csv_path):
        print(f"[Error] CSV 文件不存在: {csv_path}")
        return
    
    print(f"\n[步驟 1] 讀取數據: {csv_path}")
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    print(f"[Info] 成功讀取 {len(df)} 筆數據")
    
    # 創建策略實例
    print(f"\n[步驟 2] 初始化策略")
    strategy = OrangePredictionStrategy(
        stock_ticker='006208',
        model_path='orange_data_export/tree.pkcls'
    )
    
    if not strategy.model_available:
        print("[Error] Orange 模型不可用")
        return
    
    print("[Success] 策略初始化成功")
    print(f"[Info] 策略參數:")
    print(f"  動量確認天數: {strategy.momentum_lookback_days}")
    print(f"  動量閾值: {strategy.momentum_threshold_pct}%")
    print(f"  價格偏離度閾值: {strategy.deviation_threshold_pct}%")
    
    # 檢查前50天的數據
    print(f"\n[步驟 3] 分析前50天數據的策略執行情況")
    print("-" * 80)
    
    state = {}  # 初始化狀態
    analysis_results = []
    trade_count = 0
    
    # 選擇前50筆有效數據
    valid_data = df[df['close'].notna()].head(50)
    
    if len(valid_data) < 10:
        print("[Error] 有效數據不足")
        return
    
    print(f"[Info] 分析 {len(valid_data)} 筆數據\n")
    
    for idx, row in valid_data.iterrows():
        date = row.get('date', idx)
        current_price = row['close']
        
        # 獲取預測價格
        predicted_price = strategy._predict_price(row)
        
        if predicted_price is None:
            analysis_results.append({
                'date': date,
                'current_price': current_price,
                'predicted_price': None,
                'deviation': None,
                'momentum_signal': None,
                'momentum_direction': None,
                'momentum_strength': None,
                'momentum_confirmation': 0,
                'prediction_history_len': 0,
                'reason': '預測失敗',
                'trade_action': None
            })
            continue
        
        # 計算偏離度
        deviation = strategy._calculate_price_deviation(current_price, predicted_price)
        
        # 檢查動量信號
        momentum_signal, momentum_direction, momentum_strength = strategy._check_momentum_signal(
            state, predicted_price
        )
        
        # 獲取動量確認狀態
        momentum_confirmation = state.get('momentum_confirmation', 0)
        prediction_history_len = len(state.get('prediction_history', []))
        
        # 模擬執行 generate_orders（但不實際交易）
        price_dict = {'006208': current_price}
        is_holding_before = state.get('state', False)
        orders = strategy.generate_orders(state, date, row, price_dict)
        is_holding_after = state.get('state', False)
        
        # 判斷交易動作
        trade_action = None
        if orders:
            trade_action = orders[0]['action']
            trade_count += 1
        
        # 分析為什麼不交易
        reason = []
        if predicted_price is None:
            reason.append('預測失敗')
        else:
            if momentum_signal is None:
                if prediction_history_len < strategy.momentum_lookback_days:
                    reason.append(f'歷史數據不足({prediction_history_len}/{strategy.momentum_lookback_days}天)')
                elif momentum_confirmation < strategy.momentum_lookback_days:
                    reason.append(f'動量未確認({momentum_confirmation}/{strategy.momentum_lookback_days}天)')
                elif abs(momentum_strength) < strategy.momentum_threshold_pct:
                    reason.append(f'動量強度不足({momentum_strength:.2f}% < {strategy.momentum_threshold_pct}%)')
                else:
                    reason.append('動量方向不一致')
            else:
                if momentum_signal == 'buy':
                    if deviation is None or deviation > -strategy.deviation_threshold_pct:
                        reason.append(f'價格偏離度不足買進條件(偏離度={deviation:.2f}%, 需要<={-strategy.deviation_threshold_pct}%)')
                    elif is_holding_before:
                        reason.append('已持有股票')
                    else:
                        reason.append('滿足買進條件')
                elif momentum_signal == 'sell':
                    if deviation is None or deviation < strategy.deviation_threshold_pct:
                        reason.append(f'價格偏離度不足賣出條件(偏離度={deviation:.2f}%, 需要>={strategy.deviation_threshold_pct}%)')
                    elif not is_holding_before:
                        reason.append('未持有股票')
                    else:
                        reason.append('滿足賣出條件')
        
        analysis_results.append({
            'date': date,
            'current_price': current_price,
            'predicted_price': predicted_price,
            'deviation': deviation,
            'momentum_signal': momentum_signal,
            'momentum_direction': momentum_direction,
            'momentum_strength': momentum_strength,
            'momentum_confirmation': momentum_confirmation,
            'prediction_history_len': prediction_history_len,
            'reason': ' | '.join(reason),
            'trade_action': trade_action
        })
    
    # 統計分析
    print("\n" + "=" * 80)
    print("摘要統計分析")
    print("=" * 80)
    
    valid_results = [r for r in analysis_results if r['predicted_price'] is not None]
    
    if len(valid_results) == 0:
        print("[Warning] 沒有有效的預測結果")
        return
    
    print(f"\n有效預測數量: {len(valid_results)} / {len(analysis_results)}")
    print(f"實際交易次數: {trade_count}")
    
    # 分析偏離度
    deviations = [r['deviation'] for r in valid_results if r['deviation'] is not None]
    if deviations:
        print(f"\n價格偏離度統計:")
        print(f"  平均偏離度: {np.mean(deviations):.2f}%")
        print(f"  最大偏離度: {np.max(deviations):.2f}%")
        print(f"  最小偏離度: {np.min(deviations):.2f}%")
        print(f"  標準差: {np.std(deviations):.2f}%")
        print(f"  絕對值 >= {strategy.deviation_threshold_pct}% 的天數: {sum(abs(d) >= strategy.deviation_threshold_pct for d in deviations)}")
        print(f"  絕對值 >= {strategy.deviation_threshold_pct * 0.6:.1f}% 的天數: {sum(abs(d) >= strategy.deviation_threshold_pct * 0.6 for d in deviations)}")
    
    # 分析動量信號
    momentum_signals = [r['momentum_signal'] for r in valid_results]
    buy_signals = sum(1 for s in momentum_signals if s == 'buy')
    sell_signals = sum(1 for s in momentum_signals if s == 'sell')
    no_signals = sum(1 for s in momentum_signals if s is None)
    
    print(f"\n動量信號統計:")
    print(f"  買進信號: {buy_signals}")
    print(f"  賣出信號: {sell_signals}")
    print(f"  無信號: {no_signals}")
    
    # 分析動量強度
    momentum_strengths = [r['momentum_strength'] for r in valid_results if r['momentum_strength'] is not None]
    if momentum_strengths:
        print(f"\n動量強度統計:")
        print(f"  平均動量: {np.mean(momentum_strengths):.2f}%")
        print(f"  最大動量: {np.max(momentum_strengths):.2f}%")
        print(f"  最小動量: {np.min(momentum_strengths):.2f}%")
        print(f"  絕對值 >= {strategy.momentum_threshold_pct}% 的天數: {sum(abs(m) >= strategy.momentum_threshold_pct for m in momentum_strengths)}")
        print(f"  絕對值 >= {strategy.momentum_threshold_pct * 0.6:.1f}% 的天數: {sum(abs(m) >= strategy.momentum_threshold_pct * 0.6 for m in momentum_strengths)}")
    
    # 檢查滿足交易條件的天數
    print(f"\n交易條件分析:")
    buy_conditions = 0
    sell_conditions = 0
    
    for r in valid_results:
        if r['momentum_signal'] == 'buy':
            if r['deviation'] is not None and r['deviation'] <= -strategy.deviation_threshold_pct:
                buy_conditions += 1
        if r['momentum_signal'] == 'sell':
            if r['deviation'] is not None and r['deviation'] >= strategy.deviation_threshold_pct:
                sell_conditions += 1
    
    print(f"  滿足買進條件的天數（動量向上+價格偏離<={-strategy.deviation_threshold_pct}%）: {buy_conditions}")
    print(f"  滿足賣出條件的天數（動量向下+價格偏離>={strategy.deviation_threshold_pct}%）: {sell_conditions}")
    
    # 統計不交易的原因
    print(f"\n不交易原因統計:")
    reason_counts = {}
    for r in valid_results:
        if r['trade_action'] is None:
            reason = r['reason']
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    
    for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count} 天")
    
    # 顯示詳細信息（前20天）
    print(f"\n" + "=" * 80)
    print("前20天詳細診斷信息")
    print("=" * 80)
    print(f"{'日期':<12} {'當前價格':<10} {'預測價格':<10} {'偏離度%':<10} {'動量':<6} {'動量強度%':<12} {'確認':<6} {'原因':<40}")
    print("-" * 110)
    
    for r in valid_results[:20]:
        date_str = str(r['date'])[:10] if r['date'] else 'N/A'
        current = f"{r['current_price']:.2f}" if r['current_price'] else "N/A"
        predicted = f"{r['predicted_price']:.2f}" if r['predicted_price'] else "N/A"
        deviation = f"{r['deviation']:.2f}" if r['deviation'] is not None else "N/A"
        direction = (r['momentum_direction'] or "N/A")[:5]
        strength = f"{r['momentum_strength']:.2f}" if r['momentum_strength'] is not None else "N/A"
        confirm = f"{r['momentum_confirmation']}/{strategy.momentum_lookback_days}" if r['momentum_confirmation'] is not None else "N/A"
        reason = r['reason'][:38] if r['reason'] else "N/A"
        action = f"[{r['trade_action']}]" if r['trade_action'] else ""
        
        print(f"{date_str:<12} {current:<10} {predicted:<10} {deviation:<10} {direction:<6} {strength:<12} {confirm:<6} {reason:<40} {action}")
    
    # 如果有交易，顯示交易詳情
    if trade_count > 0:
        print(f"\n" + "=" * 80)
        print("交易記錄")
        print("=" * 80)
        for r in valid_results:
            if r['trade_action']:
                date_str = str(r['date'])[:10] if r['date'] else 'N/A'
                print(f"\n日期: {date_str}")
                print(f"  動作: {r['trade_action']}")
                print(f"  當前價格: {r['current_price']:.2f}")
                print(f"  預測價格: {r['predicted_price']:.2f}")
                print(f"  偏離度: {r['deviation']:.2f}%")
                print(f"  動量方向: {r['momentum_direction']}")
                print(f"  動量強度: {r['momentum_strength']:.2f}%")
    
    print("\n" + "=" * 80)
    print("診斷完成")
    print("=" * 80)
    
    # 建議
    print(f"\n建議:")
    if trade_count == 0:
        print("  - 目前沒有產生任何交易，建議進一步放寬參數")
        if buy_conditions == 0 and sell_conditions == 0:
            print("  - 考慮降低動量閾值或偏離度閾值")
    else:
        print(f"  - 產生了 {trade_count} 筆交易")
        if trade_count < len(valid_results) * 0.1:
            print("  - 交易次數較少，可以考慮進一步放寬參數以增加交易機會")


if __name__ == '__main__':
    diagnose_strategy()


