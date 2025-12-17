# Orange 模型整合報告

**日期**：2025-12-16  
**狀態**：策略已優化為純均值回歸策略，可正常產生交易信號

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

### 3.1 策略架構（已更新為純均值回歸策略）

`OrangePredictionStrategy` 採用**純均值回歸策略**，適應月度數據特性（同月內預測值相同）：

1. **價格預測**
   - 使用 Orange 模型預測收盤價
   - 輸入特徵：領先指標綜合指數、海關出口值、金融機構放款與投資

2. **均值回歸策略（核心邏輯）**
   - 當實際價格偏離預測價格時進場
   - 買進：當前價格 < 預測價格 × (1 - 5%) 且未持有
   - 賣出：當前價格 > 預測價格 × (1 + 5%) 且已持有

3. **風險調整機制**
   - 根據預測穩定性動態調整倉位（20%-100%）
   - 計算最近 7 天的預測波動率
   - 波動率越低，倉位越大（最多 100%，最少 20%）

### 3.2 策略運作流程

每個交易日執行以下步驟：

```
1. 獲取當前收盤價
   ↓
2. 使用 Orange 模型預測收盤價（基於 3 個特徵）
   - 輸入特徵：領先指標綜合指數、海關出口值、金融機構放款與投資
   - 模型類型：決策樹模型
   ↓
3. 計算價格偏離度
   - 公式：deviation = (當前價格 - 預測價格) / 預測價格 × 100%
   - 負值：當前價格 < 預測價格（被低估）
   - 正值：當前價格 > 預測價格（被高估）
   ↓
4. 更新預測歷史（用於計算穩定性）
   - 保存最近 N 天的預測值（N = stability_lookback_days）
   ↓
5. 計算預測穩定性（標準差）
   - 使用最近 7 天的預測值計算波動率
   ↓
6. 計算倉位大小（根據穩定性調整）
   - 波動率 ≤ 2%：100% 倉位
   - 波動率 2%-10%：線性遞減（100% → 20%）
   - 波動率 ≥ 10%：20% 倉位
   ↓
7. 檢查交易條件
   - 買進：deviation <= -5% 且 未持有
   - 賣出：deviation >= 5% 且 已持有
   ↓
8. 產生交易訂單並更新持倉狀態
```

### 3.3 交易條件（簡化版）

**買進條件**（需同時滿足）：
1. ✅ 價格被低估：當前價格 < 預測價格 × (1 - 5%)
2. ✅ 未持有股票

**賣出條件**（需同時滿足）：
1. ✅ 價格被高估：當前價格 > 預測價格 × (1 + 5%)
2. ✅ 已持有股票

### 3.4 策略參數（當前設定與調整指南）

**參數位置**：`backtesting/strategy_orange.py` 第 89-125 行

1. **`deviation_threshold_pct = 5.0`**（第 90 行）
   - **說明**：價格偏離閾值（%），當前價格與預測價格的偏差達到此值時進行交易
   - **預設值**：5.0%
   - **調整建議**：
     - 降低（如 3.0%）→ 更頻繁交易，捕捉更多機會，但可能增加假訊號
     - 提高（如 7.0-10.0%）→ 更保守，只在明顯偏離時交易，減少交易次數
   - **影響**：直接影響交易頻率，是最重要的參數

2. **`stability_lookback_days = 7`**（第 105 行）
   - **說明**：計算預測穩定性時使用的歷史預測天數
   - **預設值**：7 天
   - **調整建議**：
     - 降低（如 5）→ 更敏感於近期波動，倉位調整更靈活
     - 提高（如 10-14）→ 更平滑的穩定性計算，倉位調整更穩定
   - **影響**：影響倉位大小的計算，間接影響風險控制

3. **`max_volatility_for_full_position = 2.0`**（第 106 行）
   - **說明**：允許使用 100% 倉位的最大預測波動率（%）
   - **預設值**：2.0%
   - **倉位計算邏輯**（見 `_calculate_position_size` 方法，第 303-331 行）：
     - 波動率 ≤ 2%：使用 100% 倉位
     - 波動率 2%-10%：線性遞減（2%→100%，10%→20%）
     - 波動率 ≥ 10%：使用 20% 倉位
   - **調整建議**：
     - 降低（如 1.5%）→ 更保守，更容易降低倉位
     - 提高（如 3.0%）→ 更積極，更容易使用全倉
   - **影響**：影響倉位大小，間接影響風險和報酬

4. **`max_volatility = 10.0`**（第 323 行，在 `_calculate_position_size` 方法中）
   - **說明**：當波動率達到此值時使用最小倉位（20%）
   - **預設值**：10.0%
   - **調整建議**：可根據風險承受度調整（建議範圍：8.0-12.0）

### 3.5 策略邏輯說明

**為什麼選擇純均值回歸策略？**

1. **適應月度數據特性**：
   - 預測數據以月為單位，同一個月內所有交易日使用相同的特徵值
   - 因此同月內的預測值完全相同，無法產生動量信號
   - 純均值回歸策略不依賴預測值的變化，只關注價格與預測的偏差

2. **邏輯簡單清晰**：
   - 當價格被低估時（低於預測 5% 以上）買進
   - 當價格被高估時（高於預測 5% 以上）賣出
   - 假設價格會向預測值回歸

3. **風險管理**：
   - 根據預測穩定性動態調整倉位
   - 當預測波動較大時，降低倉位以控制風險

**回測表現**（2020-01-01 至 2025-11-30）：
- 總報酬率：263.28%
- 年化報酬率：25.39%
- 最大回撤：34.09%
- 夏普比率：1.46
- 交易次數：7 次

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
- 執行純均值回歸策略邏輯
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

### 5.2 已解決的問題

#### ✅ 問題 1：預測值相同導致動量策略失效（已解決）

**原問題**：
- 預測數據以月為單位，同一個月內預測值完全相同
- 動量策略無法運作（動量始終為 0）
- 無法滿足交易條件（需要動量信號 + 偏離度）

**解決方案**：
- 將策略改為純均值回歸策略
- 移除動量策略邏輯，只根據價格偏離度進行交易
- 適應月度數據特性，不依賴預測值的變化

**結果**：
- ✅ 策略可以正常產生交易信號
- ✅ 回測結果良好（總報酬率 263.28%，年化報酬率 25.39%，夏普比率 1.46）

#### ✅ 問題 2：特徵值缺失（已處理）

**現象**：
- 部分日期的特徵值為 NaN
- 導致這些日期無法進行預測

**處理方式**：
- 在 `_predict_price` 方法中檢查特徵是否有效
- 如果特徵缺失，返回 None，不執行交易
- 這不影響整體策略運作（僅跳過該日期）

### 5.3 當前策略狀態

**策略類型**：純均值回歸策略

**交易邏輯**：
- 買進：當前價格 < 預測價格 × (1 - 5%)
- 賣出：當前價格 > 預測價格 × (1 + 5%)

**回測表現**（2020-01-01 至 2025-11-30）：
- 總報酬率：263.28%
- 年化報酬率：25.39%
- 最大回撤：34.09%
- 夏普比率：1.46
- 交易次數：7 次

**優點**：
- ✅ 邏輯簡單清晰，易於理解
- ✅ 適應月度數據特性
- ✅ 包含風險管理機制（動態倉位調整）
- ✅ 回測表現良好

**注意事項**：
- 策略依賴 Orange 模型的預測準確度
- 需要定期檢查模型預測品質
- 可以根據實際表現調整參數（如偏離度閾值）

---

## 六、為什麼 Orange 模型無法用於當前量化交易模型（歷史背景）

> **注意**：本章節描述的是策略優化前的問題分析，現已通過改為純均值回歸策略解決。保留此章節作為歷史背景和技術參考。

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
7. 保存預測價格到 state（用於回測結果輸出）
```

### 7.3 策略執行流程

```python
1. 檢查模型是否可用
2. 提取特徵並預測價格
3. 保存預測價格到 state（用於回測結果輸出）
4. 更新預測歷史（用於計算穩定性）
5. 計算價格偏離度
6. 計算預測穩定性（標準差）
7. 計算風險調整倉位（根據穩定性）
8. 檢查交易條件（偏離度 + 持倉狀態）
9. 產生交易訂單
```

---

## 八、總結

### 8.1 已完成的工作

✅ **技術整合**：
- Orange 模型載入器實現
- 預測功能實現
- Domain Bug 修復

✅ **策略設計**：
- 純均值回歸策略邏輯實現
- 基於價格偏離預測價格的程度進行交易
- 風險調整機制（根據預測穩定性動態調整倉位）

✅ **錯誤處理**：
- 模型載入失敗處理
- 預測失敗處理
- 特徵缺失處理

### 8.2 當前策略狀態

✅ **策略已優化並正常運作**：
- 策略類型：純均值回歸策略
- 交易邏輯：根據價格偏離預測價格的程度進行交易
- 回測表現：總報酬率 263.28%，年化報酬率 25.39%，夏普比率 1.46

**新增功能**：
- ✅ 回測結果中新增「模型預測價格」欄位，提高策略透明度
- ✅ 策略參數添加詳細註釋，方便調整和維護

### 8.3 後續優化方向

1. **參數調優**：
   - 根據實際表現調整 `deviation_threshold_pct`（偏離度閾值）
   - 調整 `stability_lookback_days` 和 `max_volatility_for_full_position` 以優化風險控制

2. **策略改進**：
   - 考慮增加止損/止盈機制
   - 評估是否加入其他過濾條件（如成交量、技術指標等）

3. **模型改進**：
   - 定期評估模型預測準確度
   - 考慮使用更多特徵或更新模型

4. **風險管理**：
   - 進一步優化倉位調整邏輯
   - 考慮加入最大回撤控制機制

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
- `__init__(stock_ticker, hedge_ticker, model_path, use_multi_model, model_price_ranges)`：初始化策略（支援單模型或多模型模式）
- `generate_orders(state, date, row, price_dict, ...)`：產生交易訂單
- `_predict_price(row)`：使用 Orange 模型預測價格（支援多模型選擇）
- `_calculate_price_deviation(current_price, predicted_price)`：計算價格偏離度
- `_calculate_position_size(state)`：根據預測穩定性計算倉位大小

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
- ✅ 純均值回歸策略邏輯：基於價格偏離預測價格的程度進行交易
- ✅ 多模型支援：可根據價格區間選擇不同的模型（需手動配置）
- ✅ 風險調整機制：根據預測穩定性動態調整倉位（20%-100%）
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
- 交易條件分析（滿足買進/賣出條件的天數）
- 不交易原因統計
- 前20天詳細診斷信息

**注意**：此診斷腳本可能仍包含動量相關的統計（如果腳本未更新），但當前策略已不再使用動量信號。

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

### Orange 相關文件

- **Orange 模型整合報告**：`docs/ORANGE_INTEGRATION_REPORT.md`（本文件，包含完整的工作流程、策略設計和技術實現說明）
- **策略說明文件**：`docs/STRATEGY_EXPLANATION.md`（包含新系統和舊系統的策略說明）

### 核心程式文件

- **模型載入器**：`backtesting/orange_model_loader.py`
- **策略實現**：`backtesting/strategy_orange.py`
- **診斷腳本**：`orange_data_export/diagnose_strategy.py`
- **模型檢查腳本**：`orange_data_export/inspect_model.py`
- **簡單模型檢查腳本**：`orange_data_export/inspect_model_simple.py`

---

**報告生成時間**：2025-12-16  
**最後更新**：策略已優化為純均值回歸策略，可正常產生交易信號，回測表現良好
