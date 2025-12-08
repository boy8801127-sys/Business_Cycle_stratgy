"""
專案說明文件自動更新腳本
當專案關鍵檔案變更時，自動更新 PROJECT_CONTEXT.md 和相關文件
"""

import os
import sys
import ast
import hashlib
from datetime import datetime
from pathlib import Path

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_file_hash(file_path):
    """計算檔案雜湊值"""
    if not os.path.exists(file_path):
        return None
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def get_class_names(file_path):
    """從Python檔案中提取類別名稱"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=file_path)
        
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
        return classes
    except Exception as e:
        print(f"[Warning] 無法解析 {file_path}: {e}")
        return []


def get_function_names(file_path):
    """從Python檔案中提取函數名稱"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=file_path)
        
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
        return functions
    except Exception as e:
        print(f"[Warning] 無法解析 {file_path}: {e}")
        return []


def check_file_changes():
    """檢查關鍵檔案是否有變更"""
    key_files = {
        'backtesting/backtest_engine.py': '回測引擎',
        'backtesting/strategy.py': '策略邏輯',
        'backtesting/backtest_validator.py': '驗證檢查',
        'data_collection/cycle_data_collector.py': '景氣資料收集',
        'data_collection/m1b_calculator.py': 'M1B計算',
        'main.py': '主程式'
    }
    
    changes = {}
    hash_file = project_root / '.project_context_hashes.txt'
    
    # 讀取之前的雜湊值
    previous_hashes = {}
    if hash_file.exists():
        with open(hash_file, 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    file_path, file_hash = line.strip().split(':', 1)
                    previous_hashes[file_path] = file_hash
    
    # 檢查每個關鍵檔案
    for file_path, description in key_files.items():
        full_path = project_root / file_path
        if full_path.exists():
            current_hash = get_file_hash(full_path)
            previous_hash = previous_hashes.get(file_path)
            
            if current_hash != previous_hash:
                changes[file_path] = {
                    'description': description,
                    'previous_hash': previous_hash,
                    'current_hash': current_hash
                }
    
    # 儲存新的雜湊值
    with open(hash_file, 'w', encoding='utf-8') as f:
        for file_path, file_hash in previous_hashes.items():
            if (project_root / file_path).exists():
                f.write(f"{file_path}:{file_hash}\n")
        for file_path, info in changes.items():
            f.write(f"{file_path}:{info['current_hash']}\n")
    
    return changes


def update_project_context():
    """更新 PROJECT_CONTEXT.md"""
    context_file = project_root / 'docs' / 'PROJECT_CONTEXT.md'
    
    if not context_file.exists():
        print(f"[Error] 找不到 {context_file}")
        return False
    
    # 讀取現有文件
    with open(context_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 更新最後更新時間
    current_time = datetime.now().strftime('%Y-%m-%d')
    content = content.replace(
        '**最後更新時間**：2025-01-08',
        f'**最後更新時間**：{current_time}'
    )
    
    # 更新更新記錄
    update_section = f"""
### {current_time}
- 自動更新：檢測到關鍵檔案變更
"""
    
    if '## 更新記錄' in content:
        # 在更新記錄開頭插入新記錄
        content = content.replace(
            '## 更新記錄',
            f'## 更新記錄{update_section}'
        )
    else:
        # 如果沒有更新記錄區段，在文件末尾添加
        content += f'\n\n## 更新記錄{update_section}'
    
    # 寫回文件
    with open(context_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[Info] 已更新 {context_file}")
    return True


def update_strategy_explanation():
    """更新策略說明文件（如果需要）"""
    strategy_file = project_root / 'docs' / 'STRATEGY_EXPLANATION.md'
    
    if not strategy_file.exists():
        return False
    
    # 檢查策略檔案是否有變更
    strategy_py = project_root / 'backtesting' / 'strategy.py'
    if not strategy_py.exists():
        return False
    
    # 提取策略類別名稱
    classes = get_class_names(strategy_py)
    strategy_classes = [c for c in classes if 'Strategy' in c]
    
    print(f"[Info] 發現 {len(strategy_classes)} 個策略類別：{', '.join(strategy_classes)}")
    
    # 這裡可以添加更詳細的策略說明更新邏輯
    # 目前只是記錄，不進行實際更新
    
    return True


def main():
    """主函數"""
    print("="*60)
    print("專案說明文件自動更新")
    print("="*60)
    
    # 檢查檔案變更
    changes = check_file_changes()
    
    if not changes:
        print("[Info] 未檢測到關鍵檔案變更")
        return
    
    print(f"[Info] 檢測到 {len(changes)} 個檔案變更：")
    for file_path, info in changes.items():
        print(f"  - {file_path} ({info['description']})")
    
    # 更新專案說明文件
    print("\n[Info] 更新專案說明文件...")
    update_project_context()
    
    # 更新策略說明文件（如果需要）
    print("\n[Info] 檢查策略說明文件...")
    update_strategy_explanation()
    
    print("\n[Info] 更新完成！")


if __name__ == '__main__':
    main()

