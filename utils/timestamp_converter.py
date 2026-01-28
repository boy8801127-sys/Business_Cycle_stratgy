"""
時間戳轉換工具
將時間戳（timestamp）轉換為人類可讀的時間格式
支援秒級（10位）和毫秒級（13位）時間戳
"""

from datetime import datetime
import sys


def timestamp_to_datetime(timestamp, timezone='Asia/Taipei'):
    """
    將時間戳轉換為日期時間字串
    
    參數:
    - timestamp: 時間戳（整數或字串），支援秒級（10位）或毫秒級（13位）
    - timezone: 時區（預設 'Asia/Taipei'），如果為 None 則使用 UTC
    
    返回:
    - datetime 物件和格式化字串
    """
    try:
        # 轉換為整數
        if isinstance(timestamp, str):
            timestamp = int(timestamp)
        
        # 判斷是秒級還是毫秒級時間戳
        if timestamp > 1e12:  # 大於 10^12，視為毫秒級
            # 毫秒級時間戳，轉換為秒
            dt = datetime.fromtimestamp(timestamp / 1000.0)
            timestamp_type = "毫秒級"
        else:
            # 秒級時間戳
            dt = datetime.fromtimestamp(timestamp)
            timestamp_type = "秒級"
        
        # 格式化輸出
        formatted_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        iso_str = dt.isoformat()
        
        return {
            'datetime': dt,
            'formatted': formatted_str,
            'iso': iso_str,
            'type': timestamp_type,
            'timestamp': timestamp
        }
    except (ValueError, OSError) as e:
        raise ValueError(f"無法轉換時間戳 {timestamp}: {e}")


def convert_timestamp(timestamp):
    """
    轉換時間戳並顯示結果
    
    參數:
    - timestamp: 時間戳（整數或字串）
    """
    try:
        result = timestamp_to_datetime(timestamp)
        
        print(f"\n{'='*60}")
        print(f"時間戳轉換結果")
        print(f"{'='*60}")
        print(f"時間戳：{result['timestamp']}")
        print(f"類型：{result['type']}")
        print(f"日期時間：{result['formatted']}")
        print(f"ISO 格式：{result['iso']}")
        print(f"{'='*60}\n")
        
        return result
    except Exception as e:
        print(f"[Error] 轉換失敗: {e}")
        return None


def batch_convert(timestamps):
    """
    批次轉換多個時間戳
    
    參數:
    - timestamps: 時間戳列表
    """
    print(f"\n{'='*60}")
    print(f"批次轉換時間戳（共 {len(timestamps)} 個）")
    print(f"{'='*60}\n")
    
    results = []
    for idx, ts in enumerate(timestamps, 1):
        print(f"[{idx}/{len(timestamps)}] 轉換 {ts}...")
        try:
            result = timestamp_to_datetime(ts)
            results.append(result)
            print(f"  → {result['formatted']}")
        except Exception as e:
            print(f"  ✗ 失敗: {e}")
            results.append(None)
    
    return results


def main():
    """主程式：從命令列參數或互動式輸入讀取時間戳"""
    if len(sys.argv) > 1:
        # 從命令列參數讀取
        for arg in sys.argv[1:]:
            convert_timestamp(arg)
    else:
        # 互動式輸入
        print("\n時間戳轉換工具")
        print("=" * 60)
        print("輸入時間戳（支援秒級和毫秒級），輸入 'q' 退出")
        print("範例：1769529600000 或 1769529600")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\n請輸入時間戳: ").strip()
                
                if user_input.lower() in ('q', 'quit', 'exit', '退出'):
                    print("\n[Info] 退出程式")
                    break
                
                if not user_input:
                    continue
                
                # 支援多個時間戳（用逗號或空格分隔）
                if ',' in user_input:
                    timestamps = [ts.strip() for ts in user_input.split(',')]
                    batch_convert(timestamps)
                elif ' ' in user_input:
                    timestamps = [ts.strip() for ts in user_input.split()]
                    batch_convert(timestamps)
                else:
                    convert_timestamp(user_input)
                    
            except KeyboardInterrupt:
                print("\n\n[Info] 程式已中斷")
                break
            except Exception as e:
                print(f"[Error] 發生錯誤: {e}")


if __name__ == '__main__':
    # 測試範例
    if len(sys.argv) == 1:
        print("測試模式：轉換範例時間戳 1769529600000")
        convert_timestamp(1769529600000)
        print("\n" + "="*60)
        print("如需轉換其他時間戳，請執行：")
        print("  python utils/timestamp_converter.py <時間戳>")
        print("或直接執行：")
        print("  python utils/timestamp_converter.py")
        print("="*60 + "\n")
    
    main()
