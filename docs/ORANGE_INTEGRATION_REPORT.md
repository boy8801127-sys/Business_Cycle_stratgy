# Orange 模型整合報告

**日期**：2025-12-14  
**狀態**：Domain Bug 已修復，預測功能正常，但策略無法產生交易

---

## 執行摘要

本報告總結了 Orange 模型整合到量化交易系統的過程，包括：
1. Orange 數據分析與預測工作流程
2. 策略設計邏輯
3. 技術實現與 Bug 修復
4. 當前問題與限制

---

## 一、Orange 模型概述

### 1.1 模型特性

- **模型類型**：決策樹模型（Tree Model）
- **模型文件**：`orange_data_export/tree.pkcls`
- **預測目標**：收盤價（`close`）
- **使用特徵**（3個）：
  1. `signal_領先指標綜合指數`
  2. `coincident_海關出口值(十億元)`
  3. `lagging_全體金融機構放款與投資(10億元)`

### 1.2 數據來源

- **數據文件**：`results/orange_analysis_data.csv`
- **數據格式**：長格式（Long Format）
- **時間範圍**：2020-01-01 至今
- **關鍵特性**：指標數據已進行 n-2 個月對齊處理（使用前2個月的指標值）

---

## 二、Orange 分析工作流程（濃縮版）

### 2.1 數據準備階段

1. **數據載入**：使用 Orange File widget 載入 CSV
2. **數據檢查**：使用 Data Info 和 Data Table widgets
3. **缺失值處理**：使用 Preprocess widget 或 Select Rows widget
4. **數據分組**：**必須**使用 Select Rows widget 按股票代號（ticker）分組，避免價格水平差異影響結果

**重要提示**：
- 建議使用 `daily_return`（日報酬率）而非 `close`（收盤價）進行分析
- 必須先分組再進行相關性或回歸分析

### 2.2 分析類型

#### 相關性分析
- **工具**：Correlations widget → Heat Map widget
- **方法**：Pearson（線性）或 Spearman（等級相關）
- **解讀**：|r| > 0.7 為強相關，0.3 < |r| ≤ 0.7 為中等相關

#### 線性回歸分析
- **工具**：Linear Regression widget → Test & Score widget
- **評估指標**：R²、RMSE、MAE
- **目標變數**：建議使用 `daily_return`（日報酬率）

#### 成對T檢定
- **工具**：Statistics widget 或 Test & Score widget
- **用途**：比較不同指標或不同股票對股價影響的差異

---

## 三、交易策略設計

### 3.1 策略架構

`OrangePredictionStrategy` 採用**複合策略邏輯**，包含四個核心組件：

1. **動量策略（主要信號）**
   - 追蹤預測價格的變化趨勢
   - 需要連續N天（預設2天）同方向變化
   - 累積變化需超過閾值（預設2%）

2. **均值回歸策略（輔助過濾）**
   - 當實際價格偏離預測價格時進場
   - 買進：當前價格低於預測價格 >= 3%（負偏離）
   - 賣出：當前價格高於預測價格 >= 3%（正偏離）

3. **雙重確認機制**
   - 需要連續N天動量信號都指向同一方向
   - 減少假訊號

4. **風險調整機制**
   - 根據預測穩定性動態調整倉位（20%-100%）
   - 波動率越低，倉位越大

### 3.2 交易條件

**買進條件**（需同時滿足）：
1. ✅ 動量向上確認（連續N天預測價格上升，累積變化 >= 閾值）
2. ✅ 價格被低估（當前價格低於預測價格 >= 3%）
3. ✅ 未持有股票

**賣出條件**（需同時滿足）：
1. ✅ 動量向下確認（連續N天預測價格下降，累積變化 >= 閾值）
2. ✅ 價格被高估（當前價格高於預測價格 >= 3%）
3. ✅ 已持有股票

### 3.3 策略參數（當前設定）

- `momentum_lookback_days = 2`：動量確認需要的天數
- `momentum_threshold_pct = 2.0`：動量變化閾值（%）
- `deviation_threshold_pct = 3.0`：價格偏離閾值（%）
- `stability_lookback_days = 7`：計算穩定性的回顧天數
- `max_volatility_for_full_position = 2.0`：允許全倉的最大波動率（%）

---

## 四、技術實現與 Bug 修復

### 4.1 模型載入器（OrangeModelLoader）

**文件位置**：`backtesting/orange_model_loader.py`

**主要功能**：
- 載入 Orange `.pkcls` 模型文件（使用 pickle）
- 提取模型 Domain 和特徵名稱
- 將輸入數據轉換為 Orange Table 格式
- 執行預測並返回結果

**關鍵修復**：
- ✅ **Domain 問題修復**：預測時只使用 Domain 的 attributes（特徵），不包含 class_var（目標變量）
- ✅ **無頭模式支援**：設置 `QT_QPA_PLATFORM='offscreen'` 避免 PyQt GUI 依賴
- ✅ **錯誤處理**：提供清晰的錯誤訊息（例如：PyQt 缺失時提示安裝）

### 4.2 策略實現（OrangePredictionStrategy）

**文件位置**：`backtesting/strategy_orange.py`

**主要功能**：
- 載入 Orange 模型
- 提取特徵並進行預測
- 執行複合策略邏輯
- 產生交易訂單

**錯誤處理**：
- 如果模型載入失敗，策略不執行（`model_available = False`）
- 如果預測失敗，返回空訂單列表
- 在主程序（`main.py`）中，如果模型不可用，會跳過該策略

---

## 五、當前問題與限制

### 5.1 已修復的問題

✅ **Domain Bug**：
- **問題**：預測時出現 `"Invalid number of class columns (0 != 1)"` 錯誤
- **原因**：使用完整的 Domain（包含 class_var）建立 Table，但預測時不提供目標變量
- **修復**：修改 `_convert_to_orange_table` 方法，使用 `Domain(self.domain.attributes)` 只包含特徵
- **狀態**：已修復並驗證（日誌顯示預測成功）

### 5.2 當前存在的問題

#### 問題 1：預測值幾乎完全相同

**現象**：
- 所有預測值都是 `104.05666666666666`（固定值）
- 導致動量強度始終為 0.0
- 無法產生動量信號

**可能原因**：
1. **數據問題**：多個日期的特徵值相同
   - 例如：`signal_領先指標綜合指數 = 83.70344279`（固定值）
   - `coincident_海關出口值(十億元) = 751.69`（固定值）
   - `lagging_全體金融機構放款與投資(10億元) = 43548.0`（固定值）

2. **模型特性**：決策樹模型對相同輸入總是產生相同輸出
   - 如果多個日期的特徵值相同，預測值也會相同

3. **數據對齊問題**：n-2 個月對齊導致多個交易日使用相同的指標值
   - 例如：2020-03 的所有交易日都使用 2020-01 的指標數據

**影響**：
- 動量策略無法運作（動量始終為 0）
- 無法滿足交易條件（需要動量信號 + 偏離度）
- 即使偏離度很大（-50%），也無法產生交易

#### 問題 2：特徵值缺失（NaN）

**現象**：
- 部分日期的 `signal_領先指標綜合指數` 值為 NaN
- 導致這些日期無法進行預測

**影響**：
- 減少了可用於預測的數據點
- 但這不是主要問題（已修復的日期可以預測）

#### 問題 3：策略邏輯不適應當前數據特性

**當前情況**：
- 預測值相同 → 動量為 0 → 無動量信號
- 即使偏離度很大（-50%），也無法交易

**策略假設**：
- 預測價格會有變化趨勢（用於動量策略）
- 實際情況：預測值幾乎不變

---

## 六、為什麼 Orange 模型無法用於當前量化交易模型

### 6.1 根本原因分析

基於運行時日誌證據，問題的核心在於：

1. **數據對齊機制導致特徵值重複**
   - n-2 個月對齊：多個交易日使用相同的月度指標值
   - 例如：整個 2020-03 月份的所有交易日都使用 2020-01 的指標數據
   - 結果：多個日期的三個特徵值完全相同

2. **決策樹模型的確定性輸出**
   - 決策樹模型對相同輸入總是產生相同輸出
   - 當特徵值相同時，預測值也相同
   - 結果：多個連續日期預測值完全相同（104.05666666666666）

3. **策略邏輯依賴預測值變化**
   - 動量策略需要預測價格的變化趨勢
   - 當預測值不變時，動量始終為 0，無法產生信號
   - 結果：即使偏離度很大（-50%），也無法滿足交易條件

### 6.2 具體證據（來自運行日誌）

從 `debug.log` 中觀察到：

```
日期: 2020-03-02
特徵: signal_領先指標綜合指數=83.70344279, coincident_海關出口值=751.69, lagging_全體金融機構放款與投資=43548.0
預測價格: 104.05666666666666

日期: 2020-03-03
特徵: signal_領先指標綜合指數=83.70344279, coincident_海關出口值=751.69, lagging_全體金融機構放款與投資=43548.0
預測價格: 104.05666666666666

日期: 2020-03-04
特徵: signal_領先指標綜合指數=83.70344279, coincident_海關出口值=751.69, lagging_全體金融機構放款與投資=43548.0
預測價格: 104.05666666666666
...
```

**所有連續日期都使用相同的特徵值，導致預測值完全相同。**

### 6.3 設計衝突

| 組件 | 設計假設 | 實際情況 |
|------|---------|---------|
| **數據對齊** | 使用月度指標預測日線股價，n-2 對齊確保時序正確 | 導致多個交易日特徵值相同 |
| **模型特性** | 決策樹模型對相同輸入產生相同輸出 | 預測值不變 |
| **策略邏輯** | 動量策略依賴預測值變化 | 預測值不變，動量為 0 |
| **交易條件** | 需要動量信號 + 偏離度 | 動量始終為 null，無法交易 |

### 6.4 可能的解決方向（未來改進）

1. **修改策略邏輯**
   - 當偏離度極大時（例如 >30%），放寬或移除動量條件
   - 或者完全移除動量策略，只使用均值回歸

2. **修改數據處理**
   - 使用插值或平滑處理，讓特徵值有變化
   - 或者使用日度指標（如果有的話）

3. **使用不同的模型**
   - 考慮使用能處理時間序列的模型（例如：LSTM、ARIMA）
   - 或者使用能產生概率輸出的模型（不確定性建模）

4. **重新評估模型適用性**
   - 評估模型是否適合用於日線級別的量化交易
   - 或者調整預測目標（例如：預測未來N天報酬率而非絕對價格）

---

## 七、技術細節

### 7.1 模型載入流程

```python
1. 設置無頭模式（QT_QPA_PLATFORM='offscreen'）
2. 使用 pickle.load() 載入 .pkcls 文件
3. 提取 Domain 和特徵名稱
4. 準備預測用 Domain（只包含 attributes）
```

### 7.2 預測流程

```python
1. 從 row 中提取 3 個特徵
2. 檢查特徵是否有缺失值（NaN）
3. 創建 DataFrame
4. 轉換為 Orange Table（使用預測用 Domain）
5. 調用 model(table) 進行預測
6. 提取預測值（從 Table.Y 或直接數組）
```

### 7.3 策略執行流程

```python
1. 檢查模型是否可用
2. 提取特徵並預測價格
3. 更新預測歷史
4. 計算動量信號（需要連續N天確認）
5. 計算價格偏離度
6. 檢查交易條件（動量 + 偏離度 + 持倉狀態）
7. 計算風險調整倉位
8. 產生交易訂單
```

---

## 八、總結

### 8.1 已完成的工作

✅ **技術整合**：
- Orange 模型載入器實現
- 預測功能實現
- Domain Bug 修復

✅ **策略設計**：
- 複合策略邏輯實現
- 動量 + 均值回歸 + 風險調整

✅ **錯誤處理**：
- 模型載入失敗處理
- 預測失敗處理
- 特徵缺失處理

### 8.2 待解決的問題

❌ **策略無法產生交易**：
- 根本原因：預測值相同導致動量策略失效
- 數據特性：月度指標對齊導致特徵值重複
- 模型特性：決策樹確定性輸出

### 8.3 建議的後續工作

1. **短期**（修改策略邏輯）：
   - 評估是否移除動量策略，只使用均值回歸
   - 或者當偏離度極大時，放寬動量條件

2. **中期**（數據處理改進）：
   - 評估數據對齊策略是否適合日線交易
   - 考慮使用插值或平滑處理

3. **長期**（模型改進）：
   - 評估是否使用其他模型類型
   - 或者調整預測目標（預測報酬率而非絕對價格）

---

## 九、Orange 相關 Python 文件說明

本節詳細說明專案中所有與 Orange 模型相關的 Python 文件，包括其功能、使用方式和在系統中的作用。

### 9.1 核心功能文件

#### `backtesting/orange_model_loader.py`

**功能**：Orange 模型載入器，負責載入 `.pkcls` 模型文件並執行預測

**主要類別**：
- `OrangeModelLoader`：模型載入與預測的核心類別

**主要方法**：
- `__init__(model_path)`：初始化並載入模型
- `predict(data)`：使用模型進行預測
- `get_feature_names()`：取得模型使用的特徵名稱

**使用方式**：
```python
from backtesting.orange_model_loader import OrangeModelLoader

# 載入模型
loader = OrangeModelLoader('orange_data_export/tree.pkcls')

# 進行預測（需要 pandas DataFrame）
import pandas as pd
feature_data = pd.DataFrame({
    'signal_領先指標綜合指數': [85.0],
    'coincident_海關出口值(十億元)': [900.0],
    'lagging_全體金融機構放款與投資(10億元)': [43000.0]
})
predictions = loader.predict(feature_data)  # 返回 numpy array
```

**重要特性**：
- ✅ 支援無頭模式（headless mode），避免 PyQt GUI 依賴
- ✅ 自動處理 Domain 轉換（預測時只使用 attributes，不包含 class_var）
- ✅ 錯誤處理：如果 Orange 庫未安裝，會拋出 ImportError

**依賴**：`orange3`、`PyQt5`（建議安裝以支持模型載入）

---

#### `backtesting/strategy_orange.py`

**功能**：Orange 智能預測交易策略實現

**主要類別**：
- `OrangePredictionStrategy`：基於 Orange 模型預測的交易策略

**主要方法**：
- `__init__(stock_ticker, hedge_ticker, model_path)`：初始化策略
- `generate_orders(state, date, row, price_dict, ...)`：產生交易訂單
- `_predict_price(row)`：使用 Orange 模型預測價格
- `_check_momentum_signal(state, current_prediction)`：檢查動量信號
- `_calculate_price_deviation(current_price, predicted_price)`：計算價格偏離度

**使用方式**：
```python
from backtesting.strategy_orange import OrangePredictionStrategy

# 創建策略實例
strategy = OrangePredictionStrategy(
    stock_ticker='006208',
    model_path='orange_data_export/tree.pkcls'
)

# 檢查模型是否可用
if strategy.model_available:
    # 在回測中使用
    orders = strategy.generate_orders(state, date, row, price_dict)
else:
    print(f"模型不可用: {strategy.load_error}")
```

**重要特性**：
- ✅ 條件導入：如果 Orange 庫不可用，策略不會崩潰
- ✅ 複合策略邏輯：動量 + 均值回歸 + 風險調整
- ✅ 錯誤處理：預測失敗時返回空訂單列表，不影響其他策略

**在系統中的角色**：
- 在 `main.py` 中通過條件導入使用（選項 12：執行回測）
- 如果模型不可用，策略選項不會出現在選單中
- 如果模型載入失敗，在"全部策略執行"時會被跳過

---

### 9.2 數據導出腳本

#### `scripts/export_orange_data.py`

**功能**：將股價數據與景氣指標合併，輸出為 Orange 分析用的 CSV 文件

**主要函數**：
- `export_orange_data()`：主要導出函數

**輸出文件**：
- `results/orange_analysis_data.csv`：合併後的數據（長格式）

**使用方式**：
1. **通過 main.py 使用**（推薦）：
   - 執行 `main.py`
   - 選擇「11. 輸出 Orange 分析數據（股價 + 指標數據）」
   - 自動執行導出

2. **直接執行腳本**：
```python
from scripts.export_orange_data import export_orange_data
export_orange_data()
```

**輸出數據格式**：
- 包含所有股票價格數據（006208、2330）
- 包含所有領先、同時、落後指標
- 包含景氣對策信號（綜合分數、燈號）
- 指標數據已進行 n-2 個月對齊處理

**依賴**：
- `data_collection.database_manager.DatabaseManager`
- 需要 `business_cycle/` 資料夾中的指標 CSV 文件

---

#### `orange_data_export/export_for_prediction.py`

**功能**：導出用於 Orange 預測模型的訓練/預測數據，包含特徵和目標變數

**主要類別**：
- `PredictionDataExporter`：預測數據導出器

**主要功能**：
- 從資料庫載入股票數據
- 計算技術指標特徵（移動平均線、RSI、波動率等）
- 計算目標變數（未來N天報酬率）
- 合併景氣燈號數據
- 輸出為 CSV 文件

**使用方式**：
```bash
# 基本使用
python orange_data_export/export_for_prediction.py

# 指定日期範圍
python orange_data_export/export_for_prediction.py --start-date 20200101 --end-date 20241231

# 指定預測未來天數
python orange_data_export/export_for_prediction.py --future-days 10

# 指定輸出文件
python orange_data_export/export_for_prediction.py --output my_data.csv
```

**輸出文件**：
- `orange_data_export/prediction_data.csv`（預設）

**用途**：
- 用於在 Orange 中訓練預測模型
- 包含特徵和目標變數，適合機器學習

**注意**：此腳本主要用於模型訓練階段，與回測系統使用不同的數據格式

---

### 9.3 測試與診斷腳本

#### `orange_data_export/test_model.py`

**功能**：測試 Orange 模型是否可以正常載入和預測

**主要函數**：
- `test_model_loading()`：測試模型載入
- `test_prediction()`：測試模型預測功能

**使用方式**：
```bash
# 在專案根目錄執行
python orange_data_export/test_model.py
```

**輸出內容**：
- 模型載入狀態
- 模型使用的特徵名稱
- 測試數據的預測結果
- 預測準確度評估

**適用場景**：
- ✅ 初次安裝 Orange 後驗證模型是否可以正常使用
- ✅ 模型文件損壞或路徑錯誤時的診斷
- ✅ 確認模型預測功能正常

---

#### `orange_data_export/diagnose_strategy.py`

**功能**：診斷 Orange 策略為什麼沒有產生交易，輸出詳細的診斷信息

**主要函數**：
- `diagnose_strategy()`：執行策略診斷分析

**使用方式**：
```bash
# 在專案根目錄執行
python orange_data_export/diagnose_strategy.py
```

**輸出內容**：
- 策略參數設定
- 預測成功/失敗統計
- 價格偏離度統計
- 動量信號統計
- 動量強度統計
- 交易條件分析（滿足買進/賣出條件的天數）
- 不交易原因統計
- 前20天詳細診斷信息

**適用場景**：
- ✅ 策略無法產生交易時，找出原因
- ✅ 調整策略參數前的數據分析
- ✅ 理解策略邏輯是否符合預期

**依賴**：
- 需要 `results/orange_analysis_data.csv` 文件存在

---

#### `orange_data_export/inspect_model.py`

**功能**：查看 Orange 模型（`tree.pkcls`）的詳細內容和信息

**主要函數**：
- `inspect_model(model_path)`：檢查模型的詳細信息

**使用方式**：
```bash
# 需要虛擬環境中有 Orange 庫
# 激活虛擬環境後執行
python orange_data_export/inspect_model.py
```

**輸出內容**：
- 模型類型和模組路徑
- Domain 信息（特徵和目標變數）
- 樹模型結構（節點數量、樹高度等）
- 模型規則（如果可用）
- 預測功能測試

**適用場景**：
- ✅ 查看模型使用的特徵名稱
- ✅ 了解模型的結構和參數
- ✅ 驗證模型是否可以正常預測
- ✅ 檢查模型的 Domain 配置

**依賴**：
- 需要安裝 `orange3` 庫
- 建議在虛擬環境中執行

---

#### `orange_data_export/inspect_model_simple.py`

**功能**：簡單的模型檢查腳本，不需要 Orange 庫也能查看基本結構

**主要函數**：
- `inspect_model_simple(model_path)`：簡單檢查模型文件內容

**使用方式**：
```bash
# 不需要 Orange 庫
python orange_data_export/inspect_model_simple.py
```

**輸出內容**：
- 模型文件大小
- 模型對象類型
- 模型屬性列表（前30個）
- Domain 相關屬性
- 樹結構基本信息

**適用場景**：
- ✅ 快速檢查模型文件是否存在
- ✅ 查看模型的基本類型信息
- ✅ 當 Orange 庫未安裝時，仍能查看基本信息

**限制**：
- 只能查看基本結構，無法查看完整的 Domain 信息
- 無法測試預測功能

---

### 9.4 文件依賴關係

```
main.py (選項 11, 12)
  ├─ scripts/export_orange_data.py (數據導出)
  │   └─ data_collection.database_manager
  │
  └─ backtesting/strategy_orange.py (策略執行)
      └─ backtesting/orange_model_loader.py (模型載入)
          └─ orange3 庫 + tree.pkcls 模型文件

orange_data_export/diagnose_strategy.py
  └─ backtesting/strategy_orange.py

orange_data_export/test_model.py
  └─ backtesting/orange_model_loader.py

orange_data_export/inspect_model.py
  └─ orange3 庫 + tree.pkcls

orange_data_export/inspect_model_simple.py
  └─ (無依賴，只使用 pickle)
```

---

### 9.5 文件使用流程建議

**初次使用 Orange 模型時**：

1. **檢查模型文件**：
   ```bash
   python orange_data_export/inspect_model_simple.py
   ```

2. **測試模型載入**：
   ```bash
   python orange_data_export/test_model.py
   ```

3. **查看模型詳細信息**（需要 Orange 庫）：
   ```bash
   python orange_data_export/inspect_model.py
   ```

4. **準備數據**（通過 main.py 選項 11 或直接執行）：
   ```bash
   python scripts/export_orange_data.py
   ```

5. **執行回測**（通過 main.py 選項 12）

**策略無法產生交易時**：

1. **執行診斷腳本**：
   ```bash
   python orange_data_export/diagnose_strategy.py
   ```

2. **根據診斷結果調整策略參數或邏輯**

---

### 9.6 文件維護注意事項

1. **模型文件**（`tree.pkcls`）：
   - ⚠️ **重要**：模型文件是二進制文件，不可直接編輯
   - ⚠️ **備份建議**：建議定期備份模型文件
   - ✅ 如果模型文件損壞，需要重新在 Orange 中訓練

2. **核心代碼文件**（`orange_model_loader.py`, `strategy_orange.py`）：
   - ✅ 已實現條件導入，不會影響其他功能
   - ✅ 如果 Orange 庫未安裝，系統仍可正常運行（只是策略不可用）

3. **測試腳本**：
   - ✅ 可以安全刪除，不影響核心功能
   - ⚠️ 但建議保留，方便未來調試

---

## 附錄：相關文件

- **Orange 數據分析操作指南**：`docs/ORANGE_ANALYSIS_GUIDE.md`
- **Orange 預測工作流程指引**：`docs/ORANGE_PREDICTION_GUIDE.md`
- **Orange 智能預測交易策略邏輯說明**：`docs/ORANGE_STRATEGY_LOGIC.md`
- **模型載入器**：`backtesting/orange_model_loader.py`
- **策略實現**：`backtesting/strategy_orange.py`
- **診斷腳本**：`orange_data_export/diagnose_strategy.py`
- **模型檢查腳本**：`orange_data_export/inspect_model.py`

---

**報告生成時間**：2025-12-14  
**下次評估建議**：解決策略無法交易問題後
