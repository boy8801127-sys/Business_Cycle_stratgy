# Power BI M1B 年增率與 006208 相關性分析指引

本文件說明如何在 Power BI 中進行 M1B 年增率與 006208（富邦台50）股價的相關性分析。

## 前置準備

1. **確認資料已匯入**：使用 `main.py` 選項 1 匯入領先指標資料，並確認 M1B 年增率已自動計算
2. **連接資料庫**：參考 [Power BI 連接指引](POWER_BI_SETUP.md) 連接 SQLite 資料庫
3. **載入必要資料表**：
   - `leading_indicators_data`（包含 M1B 年增率）
   - `tw_stock_price_data`（包含 006208 股價）

## 步驟一：建立資料關聯

### 1.1 建立日期關聯

1. 在 Power BI 的「模型」視圖中
2. 將 `leading_indicators_data.date` 拖曳到 `tw_stock_price_data.date`
3. 確認關聯類型為「多對一」（Many to One）
4. 交叉篩選方向選擇「雙向」

### 1.2 建立計算表（可選）

為了更方便分析，可以建立一個計算表，合併 M1B 和 006208 資料：

1. 在「資料」視圖中，選擇「建立資料表」
2. 使用 DAX 公式：

```dax
M1B_Stock_Analysis = 
SELECTCOLUMNS(
    FILTER(
        CROSSJOIN(
            'leading_indicators_data',
            FILTER('tw_stock_price_data', 'tw_stock_price_data'[ticker] = "006208")
        ),
        'leading_indicators_data'[date] = 'tw_stock_price_data'[date]
    ),
    "Date", 'leading_indicators_data'[date],
    "M1B_Money_Supply", 'leading_indicators_data'[m1b_money_supply],
    "M1B_YoY_Month", 'leading_indicators_data'[m1b_yoy_month],
    "M1B_YoY_Rolling_12M", 'leading_indicators_data'[m1b_yoy_rolling_12m],
    "Stock_Close", 'tw_stock_price_data'[close],
    "Stock_Return", CALCULATE(
        ('tw_stock_price_data'[close] - 
         LOOKUPVALUE('tw_stock_price_data'[close], 'tw_stock_price_data'[date], 
                     'leading_indicators_data'[date] - 1)) / 
        LOOKUPVALUE('tw_stock_price_data'[close], 'tw_stock_price_data'[date], 
                    'leading_indicators_data'[date] - 1) * 100
    )
)
```

## 步驟二：建立散點圖（相關性分析）

### 2.1 M1B 月對月年增率 vs 006208 收盤價

1. 建立新的「散點圖」視覺化
2. X 軸：`leading_indicators_data[m1b_yoy_month]` 或 `M1B_Stock_Analysis[M1B_YoY_Month]`
3. Y 軸：`tw_stock_price_data[close]`（篩選 `ticker = "006208"`）
4. 圖例：可以加入 `business_cycle_data[signal]`（景氣燈號）作為顏色標記

### 2.2 M1B 滾動12個月年增率 vs 006208 收盤價

重複上述步驟，將 X 軸改為 `m1b_yoy_rolling_12m`

### 2.3 解讀散點圖

- **正相關**：點從左下到右上分布，表示 M1B 年增率上升時股價也上升
- **負相關**：點從左上到右下分布，表示 M1B 年增率上升時股價下降
- **無相關**：點隨機分布，表示兩者無明顯關係
- **注意偽相關**：如文件所述，如果兩者都是非平穩數據，可能出現偽相關

## 步驟三：計算相關係數

### 3.1 使用 DAX 計算相關係數

建立新的「卡片圖」視覺化，使用以下 DAX 公式：

```dax
Correlation_M1B_YoY_Month_Stock = 
VAR FilteredData = 
    FILTER(
        ADDCOLUMNS(
            CROSSJOIN(
                FILTER('leading_indicators_data', 
                       NOT(ISBLANK('leading_indicators_data'[m1b_yoy_month]))),
                FILTER('tw_stock_price_data', 
                       'tw_stock_price_data'[ticker] = "006208")
            ),
            "DateMatch", IF('leading_indicators_data'[date] = 'tw_stock_price_data'[date], 1, 0)
        ),
        [DateMatch] = 1
    )
RETURN
    IF(
        COUNTROWS(FilteredData) > 1,
        CORREL(
            SELECTCOLUMNS(FilteredData, "X", 'leading_indicators_data'[m1b_yoy_month]),
            SELECTCOLUMNS(FilteredData, "Y", 'tw_stock_price_data'[close])
        ),
        BLANK()
    )
```

### 3.2 相關係數解讀

- **0.7 到 1.0**：強正相關
- **0.3 到 0.7**：中等正相關
- **-0.3 到 0.3**：弱相關或無相關
- **-0.7 到 -0.3**：中等負相關
- **-1.0 到 -0.7**：強負相關

## 步驟四：建立時間序列對比圖

### 4.1 雙軸折線圖

1. 建立新的「折線圖」視覺化
2. X 軸：`date`（日期）
3. Y 軸（主要）：`tw_stock_price_data[close]`（006208 收盤價）
4. Y 軸（次要）：`leading_indicators_data[m1b_yoy_month]` 或 `m1b_yoy_rolling_12m`
5. 在「格式」中啟用「雙軸」

### 4.2 解讀時間序列圖

- **同步變化**：兩條線趨勢相似，表示有相關性
- **領先/滯後**：觀察 M1B 變化是否領先股價變化
- **背離**：兩條線反向變化，可能表示市場轉折點

## 步驟五：計算 M1B 動能指標

### 5.1 M1B 年增率變化率

建立新的計算欄位：

```dax
M1B_YoY_Month_Momentum = 
VAR CurrentYoY = 'leading_indicators_data'[m1b_yoy_month]
VAR PrevYoY = 
    CALCULATE(
        MAX('leading_indicators_data'[m1b_yoy_month]),
        FILTER(
            ALL('leading_indicators_data'),
            'leading_indicators_data'[date] < EARLIER('leading_indicators_data'[date])
        ),
        TOPN(1, ALL('leading_indicators_data'), 'leading_indicators_data'[date], DESC)
    )
RETURN
    CurrentYoY - PrevYoY
```

### 5.2 動能指標視覺化

建立折線圖顯示：
- X 軸：日期
- Y 軸：`M1B_YoY_Month_Momentum`
- 顏色：正值為綠色（上升），負值為紅色（下降）

## 步驟六：建立相關性矩陣

### 6.1 使用相關性矩陣視覺化

1. 安裝「相關性矩陣」自訂視覺化（如果尚未安裝）
2. 選擇多個變數：
   - `m1b_yoy_month`
   - `m1b_yoy_rolling_12m`
   - `close`（006208 收盤價）
   - `score`（景氣燈號分數）

### 6.2 解讀相關性矩陣

- 顏色深淺表示相關性強弱
- 紅色表示正相關，藍色表示負相關
- 可以同時比較多個指標之間的關係

## 步驟七：策略邏輯驗證

### 7.1 驗證「價量背離」邏輯

參考 `Quant_Strategy_Macro_Cycle_TW.md` 的策略邏輯：

1. 建立計算欄位判斷背離：

```dax
Price_Money_Divergence = 
VAR CurrentScore = RELATED('business_cycle_data'[score])
VAR CurrentM1B_Momentum = 'leading_indicators_data'[M1B_YoY_Month_Momentum]
RETURN
    IF(
        CurrentScore >= 32 && CurrentM1B_Momentum < 0,
        "危險背離",
        IF(
            CurrentScore <= 16 && CurrentM1B_Momentum > 0,
            "底部反轉",
            "正常"
        )
    )
```

2. 建立表格顯示背離時點和後續股價表現

### 7.2 回測驗證

建立視覺化顯示：
- 在背離時點標記
- 顯示後續 N 天（例如：30天）的股價變化
- 計算背離後的報酬率統計

## 常見問題

### Q: 相關性很低怎麼辦？

A: 
- 檢查資料期間是否足夠長（建議至少 2-3 年）
- 嘗試使用不同的時間區間（例如：只分析特定景氣階段）
- 考慮使用其他指標組合（例如：M1B 動能而非絕對值）

### Q: 如何判斷是否為偽相關？

A:
- 觀察散點圖是否呈現明顯的線性趨勢但缺乏經濟邏輯
- 檢查兩個變數是否都有明顯的時間趨勢
- 使用差分後再計算相關性（例如：股價變化率 vs M1B 變化率）

### Q: 為什麼要使用年增率而非絕對值？

A:
- 絕對值會隨著時間和通膨增長，無法進行跨時間比較
- 年增率是平穩的指標，更容易建立預測模型
- 年增率更能反映資金面的變化趨勢

## 下一步

完成相關性分析後：

1. **記錄分析結果**：相關性係數、散點圖特徵、時間序列特徵
2. **策略調整**：根據分析結果調整策略邏輯（參考 `Quant_Strategy_Macro_Cycle_TW.md`）
3. **回測驗證**：使用調整後的策略進行回測
4. **持續監控**：定期更新資料並重新分析

## 參考資源

- [Power BI 連接指引](POWER_BI_SETUP.md)
- [資料庫結構說明](DATABASE_SCHEMA.md)
- [策略邏輯文件](../Quant_Strategy_Macro_Cycle_TW.md)

