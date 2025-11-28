# Orange 預測工作流程指引

本文件說明如何使用 Orange 進行景氣燈號預測 006208（富邦台50）的未來報酬率。

## 前置準備

### 1. 安裝 Orange

1. 前往 [Orange 官方網站](https://orangedatamining.com/)
2. 下載並安裝 Orange（建議安裝最新穩定版本）
3. 啟動 Orange

### 2. 準備資料

使用資料導出腳本產生 CSV 檔案：

```bash
cd D:\Business_Cycle_stratgy
python orange_data_export/export_for_prediction.py
```

預設會產生 `orange_data_export/prediction_data.csv` 檔案。

#### 自訂參數

```bash
# 指定日期範圍
python orange_data_export/export_for_prediction.py --start-date 20200101 --end-date 20241231

# 指定預測未來天數（例如：10天）
python orange_data_export/export_for_prediction.py --future-days 10

# 指定輸出檔案
python orange_data_export/export_for_prediction.py --output my_data.csv
```

## 資料欄位說明

導出的 CSV 檔案包含以下欄位：

### 基本資訊
- **date**: 日期
- **ticker**: 股票代號（006208）
- **close**: 當日收盤價

### 景氣燈號特徵
- **cycle_score**: 當月景氣對策信號綜合分數
- **signal_encoded**: 燈號編碼（1=藍燈，2=黃藍燈，3=綠燈，4=黃紅燈，5=紅燈）
- **score_lag1, score_lag2, score_lag3**: 前1、2、3個月的分數（滯後特徵）
- **score_change**: 分數變化（當前分數 - 前一分數）
- **score_change_pct**: 分數變化百分比

### 技術指標特徵
- **ma5, ma20, ma60**: 5日、20日、60日移動平均線
- **price_vs_ma5, price_vs_ma20**: 股價相對於移動平均線的位置（%）
- **volatility_20, volatility_pct_20**: 過去20天的波動率
- **return_1d, return_5d, return_20d**: 過去1、5、20天的報酬率（%）
- **rsi**: RSI 相對強弱指標（14天）

### 成交量特徵（如果有）
- **volume**: 成交量
- **volume_ma5**: 5日平均成交量
- **volume_ratio**: 成交量比率（當前成交量 / 平均成交量）

### 目標變數（預測目標）
- **future_return_5d**: 未來5天報酬率（%）- 這是我們要預測的主要目標
- **future_direction_5d**: 未來5天漲跌方向（1=上漲，0=下跌）- 分類問題目標

## Orange 工作流程設計

### 步驟一：讀取資料

1. 在 Orange 工作區中，從左側面板拖曳 **File** 節點到畫布
2. 雙擊 File 節點
3. 瀏覽並選擇 `orange_data_export/prediction_data.csv` 檔案
4. 確認資料正確載入（點擊節點查看資料預覽）

### 步驟二：資料預處理

#### 2.1 選擇欄位

1. 拖曳 **Select Columns** 節點到畫布
2. 連接 File → Select Columns
3. 雙擊 Select Columns 節點
4. 選擇要使用的特徵欄位：
   - **特徵欄位**：勾選所有景氣燈號和技術指標特徵
   - **目標欄位**：勾選 `future_return_5d`（或 `future_direction_5d` 如果是分類問題）
   - **排除欄位**：移除 `date`, `ticker`（不需要用於預測）

#### 2.2 處理缺失值

1. 拖曳 **Impute** 節點到畫布
2. 連接 Select Columns → Impute
3. 雙擊 Impute 節點，選擇缺失值填補方法：
   - **Average/Most frequent**：用平均值（數值）或最常見值（類別）填補
   - **Remove rows with missing values**：刪除包含缺失值的行（不建議，可能損失資料）

### 步驟三：分割訓練集和測試集

1. 拖曳 **Data Sampler** 節點到畫布
2. 連接 Impute → Data Sampler
3. 雙擊 Data Sampler 節點：
   - **Sampling type**: 選擇 "Fixed proportion of data"
   - **Sample size**: 80%（訓練集）或 70%（根據資料量調整）
   - **Stratify**: 勾選此選項以保持目標變數的分布

**輸出**：
- **Sampled Data**：訓練集（用於訓練模型）
- **Remaining Data**：測試集（用於評估模型）

### 步驟四：建立預測模型

選擇迴歸問題（預測報酬率%）或分類問題（預測漲跌方向）。

#### 選項 A：迴歸模型（預測報酬率%）

##### 4.1 線性迴歸（Linear Regression）

1. 拖曳 **Linear Regression** 節點到畫布
2. 連接 Data Sampler (Sampled Data) → Linear Regression
3. 雙擊 Linear Regression 節點，設定參數（通常使用預設值即可）
4. 連接 Linear Regression → Data Sampler (Remaining Data)

##### 4.2 隨機森林（Random Forest）

1. 拖曳 **Random Forest** 節點到畫布
2. 連接 Data Sampler (Sampled Data) → Random Forest
3. 雙擊 Random Forest 節點：
   - **Number of trees**: 100（增加可提高準確度，但計算時間更長）
   - **Min. instances in leaves**: 5
4. 連接 Random Forest → Data Sampler (Remaining Data)

##### 4.3 神經網路（Neural Network）

1. 拖曳 **Neural Network** 節點到畫布
2. 連接 Data Sampler (Sampled Data) → Neural Network
3. 雙擊 Neural Network 節點：
   - **Hidden layer sizes**: 100,50（兩層隱藏層）
   - **Activation**: ReLU
   - **Solver**: Adam
4. 連接 Neural Network → Data Sampler (Remaining Data)

##### 4.4 支援向量機迴歸（SVM Regression）

1. 拖曳 **SVM** 節點到畫布
2. 連接 Data Sampler (Sampled Data) → SVM
3. 雙擊 SVM 節點：
   - **SVM type**: Epsilon-SVR（迴歸模式）
   - **Kernel**: RBF
4. 連接 SVM → Data Sampler (Remaining Data)

#### 選項 B：分類模型（預測漲跌方向）

如果使用 `future_direction_5d` 作為目標變數，可以使用分類模型：

1. **Tree**：決策樹
2. **Random Forest**：隨機森林（分類模式）
3. **Neural Network**：神經網路（分類模式）
4. **SVM**：支援向量機（分類模式）

### 步驟五：模型評估

#### 5.1 迴歸評估

1. 拖曳 **Predictions** 節點到畫布
2. 連接模型節點 → Predictions
3. 連接 Data Sampler (Remaining Data) → Predictions（第二個輸入）

4. 拖曳 **Regression Evaluation** 節點到畫布
5. 連接 Predictions → Regression Evaluation
6. 雙擊 Regression Evaluation 節點查看評估指標：
   - **RMSE**（均方根誤差）：越小越好
   - **MAE**（平均絕對誤差）：越小越好
   - **R²**（決定係數）：越接近 1 越好

#### 5.2 視覺化預測結果

1. 拖曳 **Scatter Plot** 節點到畫布
2. 連接 Predictions → Scatter Plot
3. 雙擊 Scatter Plot 節點：
   - **X-axis**: 選擇實際值（`future_return_5d`）
   - **Y-axis**: 選擇預測值
   - 理想情況下，點應該接近對角線（y=x）

### 步驟六：特徵重要性分析

了解哪些特徵對預測最重要：

1. 拖曳 **Rank** 節點到畫布
2. 連接 Data Sampler (Sampled Data) → Rank
3. 雙擊 Rank 節點：
   - **Ranking method**: 選擇 "Information Gain" 或 "Gini"
   - 查看特徵重要性排序

### 步驟七：模型比較

比較多個模型的表現：

1. 拖曳 **Test and Score** 節點到畫布
2. 連接 Data Sampler (Sampled Data) → Test and Score
3. 連接多個模型節點到 Test and Score（使用 Ctrl+點擊連接多個）
4. 雙擊 Test and Score 節點：
   - **Test type**: 選擇 "Test on train data" 或 "Cross validation"
   - 查看各模型的評估指標比較

## 完整工作流程範例

建議的工作流程結構：

```
File → Select Columns → Impute → Data Sampler
                                    ↓
                            ┌───────┴───────┐
                            ↓               ↓
                    (Sampled Data)   (Remaining Data)
                            ↓               ↓
                    ┌───────┼───────────────┐
                    ↓       ↓               ↓
            Linear Reg  Random Forest  Neural Network
                    ↓       ↓               ↓
                    └───────┼───────────────┘
                            ↓
                        Predictions
                            ↓
                    ┌───────┴───────┐
                    ↓               ↓
        Regression Evaluation   Scatter Plot
```

## 進階技巧

### 1. 特徵選擇

如果特徵太多，可以進行特徵選擇：

1. 拖曳 **Feature Selection** 節點到畫布
2. 連接 Impute → Feature Selection
3. 選擇要保留的重要特徵
4. 連接 Feature Selection → Data Sampler

### 2. 超參數調優

使用 **Rank** 和 **Test and Score** 節點測試不同的參數設定，找出最佳組合。

### 3. 時間序列交叉驗證

如果使用時間序列資料，建議使用時間序列分割而非隨機分割：

1. 在 Data Sampler 中選擇 "Fixed proportion" 時，確保按日期排序
2. 使用較早的資料作為訓練集，較新的資料作為測試集

### 4. 處理不平衡資料

如果漲跌方向不平衡（例如：上漲天數遠多於下跌天數）：

1. 使用 **SMOTE** 節點（需要安裝 Orange3-DataFusion add-on）進行過採樣
2. 或調整分類模型的 class_weight 參數

## 結果解讀

### 迴歸模型結果

- **RMSE < 2%**：表示預測誤差平均小於 2 個百分點
- **R² > 0.3**：表示模型能解釋 30% 以上的變異（金融市場通常較難預測，0.3 已經算不錯）

### 分類模型結果

- **準確率 > 55%**：表示預測方向正確率超過 55%（金融市場預測準確率通常不會太高）
- 查看混淆矩陣，了解模型對上漲/下跌的預測能力

## 注意事項

1. **資料洩漏**：確保特徵中不包含未來資訊（例如：未來的股價）
2. **過度擬合**：如果訓練集表現很好但測試集表現很差，可能是過度擬合
3. **時間序列特性**：股價資料有時間序列特性，簡單的隨機分割可能不合適
4. **市場變化**：過去有效的模式未來可能失效，需要持續更新模型

## 常見問題

### Q: 如何改變預測天數？

A: 在執行資料導出腳本時使用 `--future-days` 參數，例如：
```bash
python orange_data_export/export_for_prediction.py --future-days 10
```

### Q: 如何加入更多特徵？

A: 編輯 `orange_data_export/export_for_prediction.py` 的 `create_features` 方法，加入新的特徵計算邏輯。

### Q: 模型預測不準確怎麼辦？

A: 可以嘗試：
1. 增加更多特徵（例如：市場整體表現、產業指數等）
2. 調整模型參數
3. 嘗試不同的模型
4. 檢查資料品質（是否有異常值、缺失值過多等）

## 參考資源

- [Orange 官方文件](https://orangedatamining.com/docs/)
- [Orange 教學影片](https://www.youtube.com/c/OrangeDataMining)
- [機器學習基礎](https://scikit-learn.org/stable/)

## 下一步

完成模型訓練後，您可以：

1. 使用訓練好的模型進行實際預測
2. 建立自動化的預測流程
3. 結合其他技術指標或市場資訊
4. 實作組合策略（例如：預測報酬率 + 風險控制）

