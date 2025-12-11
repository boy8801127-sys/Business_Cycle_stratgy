# Orange 數據分析操作指南

本指南說明如何使用 Orange 進行股價與景氣指標的關聯分析，包含相關性分析、線性回歸分析和成對T檢定。

## 數據說明

### 數據文件
- **文件位置**：`results/orange_analysis_data.csv`
- **數據格式**：長格式（Long Format）
- **時間範圍**：2020-01-01 至當前日期
- **股票代號**：006208（富邦台50）、2330（台積電）

### 數據欄位說明

#### 基本欄位
- `date`：日期（YYYY-MM-DD格式）
- `ticker`：股票代號（006208 或 2330）
- `close`：收盤價
- `daily_return`：日報酬率（建議用於分析，不受價格水平影響）
- `cumulative_return`：累積報酬率
- `year`、`month`、`quarter`、`day_of_week`：時間特徵
- `is_month_start`、`is_month_end`：月初/月末標記

#### 指標欄位（前綴說明）
- `leading_*`：領先指標構成項目
- `coincident_*`：同時指標構成項目
- `lagging_*`：落後指標構成項目
- `signal_*`：景氣對策信號（包含綜合分數和燈號）

**重要**：指標數據已進行 n-2 個月對齊處理
- 每個日期的指標數據使用該日期所屬月份往前推 2 個月的指標值
- 例如：2020-03 的所有交易日都使用 2020-01 的指標數據

---

## 第一部分：數據載入與預處理

### 步驟 1：開啟 Orange 並載入數據

1. 開啟 Orange 應用程式
2. 從左側 Widget 面板找到 **File** widget
3. 將 **File** widget 拖放到工作區（Canvas）
4. 雙擊 **File** widget 開啟設定視窗
5. 點擊 **Browse** 按鈕，選擇 `results/orange_analysis_data.csv`
6. 確認數據預覽正確顯示
7. 點擊 **OK** 關閉設定視窗

### 步驟 2：檢查數據

1. 從 Widget 面板找到 **Data Info** widget
2. 將 **Data Info** widget 拖放到工作區
3. 將 **File** widget 的輸出連接到 **Data Info** widget
4. 雙擊 **Data Info** widget 檢查：
   - 數據筆數（應為 2890 筆左右）
   - 缺失值數量（應為 0 或很少）
   - 欄位數量和類型

5. 從 Widget 面板找到 **Data Table** widget
6. 將 **Data Table** widget 拖放到工作區
7. 將 **File** widget 的輸出連接到 **Data Table** widget
8. 雙擊 **Data Table** widget 開啟數據表格
9. 檢查以下項目：
   - 數據筆數是否正確
   - 日期格式是否正確識別
   - 數值欄位是否正確識別為連續變數（Continuous）
   - 股票代號是否正確識別為類別變數（Categorical）

**注意**：如果日期欄位未被正確識別，請在 **File** widget 中手動設定欄位類型。

### 步驟 3：處理缺失值（如需要）

如果 **Data Info** 顯示有缺失值：

#### 方法 1：使用 Preprocess Widget（推薦）

1. 從 Widget 面板找到 **Preprocess** widget
2. 將 **File** widget 的輸出連接到 **Preprocess** widget
3. 雙擊 **Preprocess** widget 開啟設定視窗
4. 在 **Impute** 選項中選擇處理方式：
   - **Mean**：平均值填充（適用於連續變數）
   - **Median**：中位數填充（對異常值較穩健）
   - **Mode**：眾數填充（適用於類別變數）
5. 點擊 **Apply** 執行處理
6. 將處理後的數據連接到後續分析

#### 方法 2：使用 Select Rows 移除缺失值

1. 從 Widget 面板找到 **Select Rows** widget
2. 將 **File** widget 的輸出連接到 **Select Rows** widget
3. 雙擊 **Select Rows** widget 開啟設定視窗
4. 在 **Filter** 標籤中選擇「**Has missing values**」或「**Contains missing values**」
5. 選擇「**Remove matching rows**」（移除包含缺失值的行）
6. 點擊 **Apply** 執行

#### 方法 3：快速定位缺失值

1. 從 Widget 面板找到 **Select Rows** widget
2. 將 **File** widget 的輸出連接到 **Select Rows** widget
3. 雙擊 **Select Rows** widget 開啟設定視窗
4. 在 **Conditions** 區域：
   - 選擇欄位（例如：`signal_景氣對策信號綜合分數`）
   - 選擇運算符：`is unknown` 或 `is missing`
5. 點擊 **OK**，將匹配的數據連接到 **Data Table** widget 查看具體位置

### 步驟 4：按股票分組（重要）

由於數據包含兩個股票（006208 和 2330），**強烈建議**分別分析以避免價格水平差異影響結果。

#### 分析 006208（富邦台50）

1. 從 Widget 面板找到 **Select Rows** widget
2. 將 **File** widget（或 **Preprocess** widget）的輸出連接到 **Select Rows** widget
3. 雙擊 **Select Rows** widget 開啟設定視窗
4. 在 **Conditions** 區域設定過濾條件：
   - **Column**：選擇 `ticker`
   - **Operator**：選擇 `equals` 或 `==`
   - **Value**：輸入 `006208`（或 `6208`，取決於數據格式）
5. **關於三個按鈕的說明**：
   - **Add Condition**：只有在需要添加**多個過濾條件**（例如：ticker == 006208 AND date > 2024-01-01）時才點擊
   - **Add All Variables**：將所有變數添加到條件列表中（幾乎不需要）
   - **Remove All**：清除所有已設定的條件（只有在想重新開始時才點擊）
   - **對於簡單的單一條件過濾，不需要點擊任何按鈕**
6. 確認底部顯示：選中約 1445 筆數據（匹配的行數）
7. 點擊 **OK** 關閉設定視窗

#### 分析 2330（台積電）

1. 複製 **Select Rows** widget（右鍵 → Duplicate）或創建新的
2. 設定條件：`ticker equals 2330`
3. 確認選中約 1445 筆數據

**重要提示**：
- `close` 欄位包含兩個股票的價格，價格水平差異很大（2330 約 1500 元，006208 約 150 元）
- **建議使用 `daily_return` 而不是 `close` 進行分析**，因為報酬率已標準化，不受價格水平影響
- 如果必須分析價格，請務必先使用 **Select Rows** 分組
- 混合兩個股票的數據會導致相關性和回歸結果嚴重失真

---

## 第二部分：相關性分析

### 步驟 1：建立相關性分析工作流程

1. 從 Widget 面板找到 **Correlations** widget
2. 將 **Correlations** widget 拖放到工作區
3. 將 **Select Rows** widget（已過濾單一股票）的輸出連接到 **Correlations** widget

**重要**：必須先使用 **Select Rows** 過濾單一股票，否則相關性結果會不準確。

### 步驟 2：執行相關性分析

1. 雙擊 **Correlations** widget 開啟設定視窗
2. 使用 **Filter** 功能過濾變數：
   - 輸入 `leading_` 只顯示領先指標
   - 輸入 `coincident_` 只顯示同時指標
   - 輸入 `lagging_` 只顯示落後指標
   - 輸入 `signal_` 只顯示信號指標
3. 選擇要分析的變數：
   - **建議選擇**：`daily_return`（日報酬率）而不是 `close`（收盤價）
   - **自變數**：選擇所有指標欄位（可使用 Ctrl+點擊多選）
   - **不要選擇**：`date`、`year`、`month`、`quarter`、`day_of_week`、`ticker`（這些會產生無意義的高相關性）
4. 選擇相關性計算方法：
   - **Pearson**：線性相關（預設）
   - **Spearman**：等級相關（適合非線性關係）
5. 點擊 **Apply** 執行分析

### 步驟 3：解讀相關性結果

**Correlations** widget 會顯示：
- **相關係數列表**：按相關係數絕對值排序（從高到低）
- **相關係數範圍**：-1 至 +1
- **綠色條形圖**：視覺化相關係數大小

**解讀原則**：
- **|r| > 0.7**：強相關
- **0.3 < |r| ≤ 0.7**：中等相關
- **|r| ≤ 0.3**：弱相關
- **p < 0.05**：統計顯著

**注意事項**：
- 忽略包含 `date`、`year`、`month` 的結果（這些只是時間趨勢，無實際意義）
- 關注 `daily_return` 與指標的相關性
- 使用結果列表上方的 **Filter** 輸入框過濾結果

### 步驟 4：視覺化相關性矩陣

1. 從 Widget 面板找到 **Heat Map** widget
2. 將 **Heat Map** widget 拖放到工作區
3. 將 **Correlations** widget 的輸出連接到 **Heat Map** widget
4. 雙擊 **Heat Map** widget 查看相關性熱圖
5. 顏色深淺代表相關性強弱，紅色表示正相關，藍色表示負相關

---

## 第三部分：線性回歸分析與預測模型

### 步驟 1：建立回歸分析工作流程

1. 從 Widget 面板找到 **Linear Regression** widget
2. 將 **Linear Regression** widget 拖放到工作區
3. 將 **Select Rows** widget（已過濾單一股票）的輸出連接到 **Linear Regression** widget

**重要**：必須先使用 **Select Rows** 過濾單一股票。

### 步驟 2：設定回歸模型

1. 雙擊 **Linear Regression** widget 開啟設定視窗
2. **目標變數（Target Variable）**：
   - **強烈建議選擇**：`daily_return`（日報酬率）
   - 或選擇 `close`（收盤價），但需注意價格水平）
3. **特徵變數（Features）**：選擇要分析的指標欄位
   - **單變數回歸**：先選擇單一指標進行測試
     - 例如：`signal_景氣對策信號綜合分數`
     - 或：`leading_貨幣總計數M1B(百萬元)`
   - **多變數回歸**：選擇多個指標同時分析
     - 建議從相關性高的指標開始
     - 逐步添加變數，觀察 R² 變化
4. 點擊 **Apply** 執行回歸分析

### 步驟 3：解讀回歸結果

**Linear Regression** widget 會顯示：

#### 模型摘要
- **R²（決定係數）**：模型解釋的變異比例（0 至 1）
  - R² 越高，模型解釋力越強
  - 一般認為 R² > 0.3 為可接受的模型
  - R² > 0.5 為良好的模型
- **調整後 R²（Adjusted R²）**：考慮變數數量後的調整值
  - 當變數較多時，調整後 R² 更準確
- **F 統計量**：整體模型顯著性檢定
- **p 值**：F 檢定的 p 值（p < 0.05 表示模型顯著）

#### 係數表
- **係數（Coefficient）**：自變數對因變數的影響程度
  - 正係數：自變數增加時，股價/報酬率上升
  - 負係數：自變數增加時，股價/報酬率下降
- **標準誤（Std. Error）**：係數估計的不確定性
- **t 值**：係數顯著性檢定統計量
- **p 值**：係數顯著性檢定的 p 值（p < 0.05 表示該變數顯著）

### 步驟 4：建立預測模型

#### 方法 1：使用 Test & Score Widget（推薦用於交叉驗證）

1. 從 Widget 面板找到 **Test & Score** widget
2. 將 **Test & Score** widget 拖放到工作區
3. 將 **Select Rows** widget 的輸出連接到 **Test & Score** widget
4. 從 Widget 面板找到 **Linear Regression** widget
5. 將 **Linear Regression** widget 連接到 **Test & Score** widget 的 **Learner** 輸入
6. 雙擊 **Linear Regression** widget 設定特徵變數（與步驟 2 相同）
7. 雙擊 **Test & Score** widget 開啟設定視窗
8. **目標變數（Target）**：選擇 `daily_return`（或 `close`）
9. **測試方法**：
   - **Cross Validation**：交叉驗證（推薦，使用所有數據）
   - **Train on train set**：訓練集訓練，測試集測試（需要先分割數據）
10. 點擊 **Apply** 執行評估

**Test & Score** widget 會顯示：
- **RMSE**（均方根誤差）：越小越好
- **MAE**（平均絕對誤差）：越小越好
- **R²**：決定係數，越大越好
- **各折的詳細結果**（如果使用交叉驗證）

#### 方法 2：使用 Train & Test Widget（時間序列預測）

對於時間序列數據，建議使用時間分割以評估真實預測能力：

1. 從 Widget 面板找到 **Select Rows** widget（用於分割訓練集）
2. 將 **File** widget（或 **Preprocess** widget）的輸出連接到 **Select Rows** widget
3. 雙擊 **Select Rows** widget 開啟設定視窗
4. 設定條件：
   - **Column**：選擇 `date`
   - **Operator**：選擇 `<` 或 `less than`
   - **Value**：輸入 `2024-01-01`（訓練集：2020-2023）
5. 點擊 **OK**，這是訓練集

6. 創建另一個 **Select Rows** widget（用於分割測試集）
7. 設定條件：
   - **Column**：選擇 `date`
   - **Operator**：選擇 `>=` 或 `greater or equal`
   - **Value**：輸入 `2024-01-01`（測試集：2024-現在）
8. 點擊 **OK**，這是測試集

9. 從 Widget 面板找到 **Train & Test** widget
10. 將訓練集的 **Select Rows** 輸出連接到 **Train & Test** widget 的 **Train Data** 輸入
11. 將測試集的 **Select Rows** 輸出連接到 **Train & Test** widget 的 **Test Data** 輸入
12. 從 Widget 面板找到 **Linear Regression** widget
13. 將 **Linear Regression** widget 連接到 **Train & Test** widget 的 **Learner** 輸入
14. 雙擊 **Linear Regression** widget 設定特徵變數（與步驟 2 相同）
15. 雙擊 **Train & Test** widget 執行訓練和測試

**Train & Test** widget 會顯示：
- **訓練集的 R² 和誤差**：模型對訓練數據的擬合程度
- **測試集的 R² 和誤差**：模型對新數據的預測能力
- **預測值與實際值的比較**：評估預測準確度

**重要**：如果測試集的 R² 遠低於訓練集，表示模型可能存在過度擬合（Overfitting）。

### 步驟 5：預測新數據

1. 從 Widget 面板找到 **Predictions** widget
2. 將訓練好的模型（從 **Train & Test** 或 **Test & Score**）連接到 **Predictions** widget 的 **Predictions** 輸入
3. 將新數據（測試集或未來數據）連接到 **Predictions** widget 的 **Data** 輸入
4. 雙擊 **Predictions** widget 查看預測結果
5. 預測結果會顯示：
   - **預測值**：模型預測的日報酬率或收盤價
   - **實際值**：真實的日報酬率或收盤價（如果有）
   - **預測誤差**：預測值與實際值的差異

### 步驟 6：視覺化回歸結果

1. 從 Widget 面板找到 **Scatter Plot** widget
2. 將 **Select Rows** widget 的輸出連接到 **Scatter Plot** widget
3. 雙擊 **Scatter Plot** widget 開啟設定視窗
4. **X 軸**：選擇指標變數（例如：`signal_景氣對策信號綜合分數`）
5. **Y 軸**：選擇 `daily_return`（或 `close`）
6. 點擊 **Apply** 查看散點圖
7. 觀察數據點的分布趨勢，驗證回歸模型的合理性

### 步驟 7：模型比較與選擇

1. 使用 **Test & Score** widget 同時測試多個模型：
   - 從 Widget 面板找到 **Linear Regression** widget
   - 從 Widget 面板找到 **Random Forest** widget（可選）
   - 從 Widget 面板找到 **SVM** widget（可選）
2. 將所有學習器連接到 **Test & Score** widget 的 **Learners** 輸入
3. 執行評估，比較各模型的：
   - **R²**：越大越好
   - **RMSE**：越小越好
   - **MAE**：越小越好
4. 選擇表現最好的模型用於預測

---

## 第四部分：成對T檢定（成對母體平均數差異檢定）

### 目的
比較不同指標對股價影響的差異，例如：
- 領先指標與同時指標對股價的影響是否顯著不同？
- 不同股票（006208 vs 2330）對同一指標的反應是否不同？

### 方法一：使用 Statistics Widget

#### 步驟 1：準備數據

1. 從 Widget 面板找到 **Select Columns** widget
2. 將 **Select Columns** widget 拖放到工作區
3. 將 **File** widget 的輸出連接到 **Select Columns** widget
4. 雙擊 **Select Columns** widget，選擇需要的欄位：
   - `ticker`（用於分組）
   - `daily_return`（報酬率）
   - 指標欄位（例如：`leading_貨幣總計數M1B(百萬元)`）

#### 步驟 2：執行成對T檢定

1. 從 Widget 面板找到 **Statistics** widget
2. 將 **Statistics** widget 拖放到工作區
3. 將 **Select Columns** widget 的輸出連接到 **Statistics** widget
4. 雙擊 **Statistics** widget 開啟設定視窗
5. **分組變數（Group By）**：選擇 `ticker`（比較不同股票）
6. **檢定變數（Test Variable）**：選擇指標欄位
7. **檢定類型**：選擇 **Paired t-test**（成對T檢定）
8. 點擊 **Apply** 執行檢定

#### 步驟 3：解讀檢定結果

**Statistics** widget 會顯示：
- **t 值**：檢定統計量
- **p 值**：顯著性水準（p < 0.05 表示兩組平均數有顯著差異）
- **平均數差異**：兩組平均數的差值
- **95% 信賴區間**：平均數差異的信賴區間

### 方法二：使用 Test & Score Widget

#### 步驟 1：建立檢定工作流程

1. 從 Widget 面板找到 **Test & Score** widget
2. 將 **Test & Score** widget 拖放到工作區
3. 將 **File** widget 的輸出連接到 **Test & Score** widget

#### 步驟 2：設定檢定參數

1. 雙擊 **Test & Score** widget 開啟設定視窗
2. **目標變數（Target）**：選擇 `daily_return`（報酬率）
3. **分組變數（Group By）**：選擇 `ticker`（比較不同股票）
4. **檢定方法**：選擇 **t-test**（T檢定）
5. 點擊 **Apply** 執行檢定

#### 步驟 3：解讀檢定結果

**Test & Score** widget 會顯示：
- 各組的平均數和標準差
- t 值和 p 值
- 平均數差異和信賴區間

### 進階分析：比較不同指標的影響

若要比較不同指標對股價的影響差異，可以：

1. 使用 **Linear Regression** widget 分別對每個指標進行回歸分析
2. 比較各指標的回歸係數和 R²
3. 使用 **Statistics** widget 比較不同指標的係數是否顯著不同

---

## 第五部分：視覺化分析

### 1. 時間序列圖（Line Chart）

1. 從 Widget 面板找到 **Line Chart** widget
2. 將 **Line Chart** widget 拖放到工作區
3. 將 **Select Rows** widget（已過濾單一股票）的輸出連接到 **Line Chart** widget
4. 雙擊 **Line Chart** widget 開啟設定視窗
5. **X 軸**：選擇 `date`（日期）
6. **Y 軸**：選擇 `daily_return`（或 `close`）或指標變數
7. 點擊 **Apply** 查看時間序列圖

### 2. 散點圖（Scatter Plot）

1. 從 Widget 面板找到 **Scatter Plot** widget
2. 將 **Scatter Plot** widget 拖放到工作區
3. 將 **Select Rows** widget 的輸出連接到 **Scatter Plot** widget
4. 雙擊 **Scatter Plot** widget 開啟設定視窗
5. **X 軸**：選擇指標變數
6. **Y 軸**：選擇 `daily_return`（或 `close`）
7. 點擊 **Apply** 查看散點圖

### 3. 相關性熱圖（Heat Map）

1. 從 Widget 面板找到 **Heat Map** widget
2. 將 **Heat Map** widget 拖放到工作區
3. 將 **Correlations** widget 的輸出連接到 **Heat Map** widget
4. 雙擊 **Heat Map** widget 查看相關性矩陣的視覺化

---

## 分析建議

### 1. 逐步分析
- 先進行相關性分析，找出與股價相關性較高的指標
- 再對相關性高的指標進行回歸分析
- 最後進行統計檢定，確認影響的顯著性

### 2. 分組分析
- **必須**按股票代號分組，避免價格水平差異影響結果
- **強烈建議**使用 `daily_return` 而不是 `close`，因為報酬率已標準化
- 可以按時間段分組，比較不同時期的關係是否穩定

### 3. 指標選擇
- 優先分析綜合指數（如 `signal_景氣對策信號綜合分數`）
- 再分析構成項目，找出最具影響力的單一指標
- 比較領先、同時、落後指標的預測能力差異

### 4. 模型驗證
- 使用交叉驗證或時間序列分割評估模型
- 比較訓練集和測試集的 R²，避免過度擬合
- 檢查回歸模型的殘差是否符合假設（常態性、同質性）

### 5. 預測模型建立流程
1. **數據準備**：使用 Select Rows 過濾單一股票
2. **特徵選擇**：根據相關性分析選擇重要指標
3. **模型訓練**：使用 Train & Test 或 Test & Score
4. **模型評估**：比較 R²、RMSE、MAE
5. **預測應用**：使用 Predictions widget 預測新數據

---

## 常見問題

### Q1：日期欄位無法正確識別
**解決方法**：在 **File** widget 中手動設定 `date` 欄位為 **Time** 類型

### Q2：某些指標欄位顯示為類別變數而非連續變數
**解決方法**：在 **File** widget 中手動設定該欄位為 **Continuous** 類型

### Q3：數據量太大導致分析緩慢
**解決方法**：
- 使用 **Select Rows** widget 篩選特定時間範圍
- 使用 **Sample** widget 進行抽樣分析

### Q4：如何比較多個指標的影響？
**解決方法**：
- 使用多變數回歸分析（在 **Linear Regression** widget 中選擇多個特徵變數）
- 比較各指標的係數大小和顯著性

### Q5：為什麼要使用 Select Rows 分組？
**原因**：
- `close` 欄位包含兩個股票的價格，價格水平差異很大（2330 約 1500 元，006208 約 150 元）
- 混合分析會導致相關性和回歸結果不準確
- 使用 `daily_return` 可以部分解決，但分組分析更準確

### Q6：如何找出缺失值？
**方法**：
- 使用 **Data Info** widget 查看缺失值統計
- 使用 **Select Rows** widget，選擇「Has missing values」或「is unknown」過濾
- 將過濾結果連接到 **Data Table** 查看具體位置

### Q7：Select Rows 的三個按鈕（Add Condition、Add All Variables、Remove All）需要點擊嗎？
**答案**：
- **Add Condition**：只有在需要**多個過濾條件**（例如：ticker == 006208 AND date > 2024-01-01）時才點擊
- **Add All Variables**：幾乎不需要，這個功能會將所有變數添加到條件列表中
- **Remove All**：只有在想清除所有已設定的條件時才點擊
- **對於簡單的單一條件過濾（如 `ticker == 006208`），不需要點擊任何按鈕**

### Q8：為什麼建議使用 daily_return 而不是 close？
**原因**：
1. **價格水平差異**：兩個股票的價格差異很大，混合分析會導致結果失真
2. **標準化**：報酬率已標準化，不受價格水平影響，更適合統計分析
3. **預測目標**：投資者通常更關心報酬率而非絕對價格
4. **模型解釋**：報酬率的回歸模型更容易解釋和應用

### Q9：如何評估預測模型的好壞？
**指標**：
- **R²**：越大越好（接近 1 表示模型解釋力強）
- **RMSE**：越小越好（表示預測誤差小）
- **MAE**：越小越好（平均絕對誤差）
- **訓練集 vs 測試集**：測試集 R² 不應遠低於訓練集（否則可能過度擬合）

---

## 參考資源

- Orange 官方文檔：https://orangedatamining.com/docs/
- Orange 教學影片：https://orangedatamining.com/tutorials/
- 統計分析方法參考：統計學教科書或線上課程

---

**最後更新**：2025-01-09
