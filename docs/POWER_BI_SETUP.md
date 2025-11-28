# Power BI 連接 SQLite 資料庫指引

本文件說明如何在 Power BI Desktop 中直接連接 SQLite 資料庫檔案（`.db`），無需另外匯出 CSV 或 Excel 檔案。

## 前置準備

### 1. 安裝 Power BI Desktop

如果還沒有安裝，請從 [Microsoft Power BI Desktop](https://powerbi.microsoft.com/desktop/) 下載並安裝。

### 2. 安裝 SQLite ODBC 驅動程式

Power BI 透過 ODBC（Open Database Connectivity）連接 SQLite，需要先安裝 SQLite ODBC 驅動程式。

#### Windows 64-bit 版本

**推薦：SQLite ODBC Driver (64-bit)**

1. 下載驅動程式：
   - 官方網站：http://www.ch-werner.de/sqliteodbc/
   - 或搜尋 "SQLite ODBC Driver" 下載最新版本

2. 安裝步驟：
   - 執行下載的安裝程式（例如：`sqliteodbc.exe`）
   - 按照安裝精靈的指示完成安裝
   - 選擇安裝 64-bit 版本（與 Power BI Desktop 版本對應）

3. 驗證安裝：
   - 開啟「控制台」→「系統管理工具」→「ODBC 資料來源管理員（64 位元）」
   - 切換到「驅動程式」標籤
   - 應該可以看到「SQLite3 ODBC Driver」或類似的驅動程式名稱

#### 替代方案：其他 SQLite ODBC 驅動程式

如果上述驅動程式有問題，可以嘗試：

- **Devart ODBC Driver for SQLite**（付費，但有試用版）
- **Easysoft ODBC Driver for SQLite**（付費，但有試用版）

## 步驟一：開啟 Power BI Desktop

1. 開啟 Power BI Desktop
2. 如果是第一次使用，可能會看到歡迎畫面，點擊「取得資料」

## 步驟二：連接 SQLite 資料庫

### 方法一：透過 ODBC 連接（推薦）

1. 點擊「取得資料」→「其他」→「ODBC」

   ![Power BI Get Data ODBC](https://learn.microsoft.com/en-us/power-bi/connect-data/media/desktop-connect-using-odbc/connect-using-odbc-01.png)

2. 在「從 ODBC」對話框中，設定連接字串：

   ```
   Driver=SQLite3 ODBC Driver;Database=D:\all_data\taiwan_stock_all_data.db;
   ```

   **重要**：將 `D:\all_data\taiwan_stock_all_data.db` 替換為您的實際資料庫路徑。

3. 點擊「確定」

4. 如果出現「選取驅動程式」對話框，選擇「SQLite3 ODBC Driver」或您安裝的 SQLite 驅動程式

5. 點擊「確定」

### 方法二：使用連接字串生成器

如果您不確定連接字串格式，可以使用 Power BI 的連接字串生成器：

1. 點擊「取得資料」→「其他」→「ODBC」

2. 點擊「進階選項」

3. 在「連接字串」欄位中輸入：

   ```
   Driver=SQLite3 ODBC Driver;Database=D:\all_data\taiwan_stock_all_data.db;
   ```

4. 點擊「確定」

## 步驟三：選擇資料表

1. 連接成功後，Power BI 會顯示「導覽器」對話框

2. 您應該可以看到資料庫中的所有資料表：
   - `tw_stock_price_data`
   - `tw_otc_stock_price_data`
   - `tw_price_indices_data`
   - `tw_return_indices_data`
   - `business_cycle_data`

3. 勾選您需要的資料表：
   - **建議至少選擇**：
     - `tw_stock_price_data`（上市股票資料）
     - `business_cycle_data`（景氣燈號資料）

4. 點擊「載入」或「轉換資料」

   - **載入**：直接將資料載入 Power BI，之後可以在「資料」視圖中查看
   - **轉換資料**：開啟 Power Query 編輯器，可以在載入前進行資料清理和轉換

## 步驟四：資料轉換（可選）

如果選擇「轉換資料」，您可以在 Power Query 編輯器中：

### 轉換日期格式

SQLite 中的日期是字串格式（YYYYMMDD），建議轉換為日期類型：

1. 選擇日期欄位（例如：`date`）
2. 點擊「轉換」標籤 →「資料類型」→「日期」
3. 如果出現轉換錯誤，可能需要先轉換為文字，再轉換為日期

**或使用公式**：

1. 選擇「新增欄」→「自訂欄」
2. 輸入公式：
   ```m
   Date.From(Text.Range([date], 0, 4) & "-" & Text.Range([date], 4, 2) & "-" & Text.Range([date], 6, 2))
   ```

### 重新命名欄位

將欄位名稱改為中文或更易讀的名稱：

1. 右鍵點擊欄位名稱
2. 選擇「重新命名」
3. 輸入新名稱

### 篩選資料

在載入前先篩選資料，減少資料量：

1. 點擊欄位名稱旁邊的篩選圖示
2. 選擇篩選條件
3. 例如：只載入 2020 年以後的資料

完成轉換後，點擊「關閉並套用」。

## 步驟五：建立資料表關聯

如果載入了多個資料表，建議建立它們之間的關聯：

1. 切換到「模型」視圖（左側圖示）

2. 拖曳建立關聯：
   - 將 `tw_stock_price_data.date` 拖曳到 `business_cycle_data.date`
   - 將 `tw_otc_stock_price_data.date` 拖曳到 `business_cycle_data.date`

3. 確認關聯設定：
   - 關聯類型：通常選擇「多對一」（Many to One）
   - 交叉篩選方向：選擇「單向」或「雙向」（視需求而定）

## 步驟六：建立視覺化

現在您可以開始建立報表和視覺化：

### 範例：股價與景氣燈號趨勢圖

1. 切換到「報表」視圖
2. 從「欄位」面板拖曳欄位到畫布：
   - `tw_stock_price_data.date`（X 軸）
   - `tw_stock_price_data.close`（Y 軸，值）
   - `business_cycle_data.score`（Y 軸，值）
3. 選擇圖表類型（例如：折線圖）

### 範例：景氣燈號分布圓餅圖

1. 拖曳 `business_cycle_data.signal`（圖例）
2. 選擇圓餅圖
3. 調整格式和顏色

## 常見問題排除

### Q1: 找不到 ODBC 驅動程式

**問題**：Power BI 顯示找不到 SQLite ODBC 驅動程式

**解決方案**：
1. 確認已安裝 SQLite ODBC 驅動程式
2. 確認安裝的是 64-bit 版本（Power BI Desktop 使用 64-bit）
3. 重啟 Power BI Desktop
4. 在連接字串中明確指定驅動程式名稱

### Q2: 連接字串錯誤

**問題**：顯示連接錯誤或找不到資料庫

**解決方案**：
1. 確認資料庫路徑正確
2. 確認路徑使用反斜線 `\`（Windows）或雙反斜線 `\\`
3. 確認資料庫檔案存在
4. 確認有讀取權限

**正確格式範例**：
```
Driver=SQLite3 ODBC Driver;Database=D:\all_data\taiwan_stock_all_data.db;
```

### Q3: 日期格式問題

**問題**：日期欄位顯示為文字或無法排序

**解決方案**：
1. 使用 Power Query 編輯器轉換日期格式
2. 參考上述「資料轉換」章節的日期轉換方法

### Q4: 資料量太大載入緩慢

**問題**：資料表太大，載入時間很長

**解決方案**：
1. 在 Power Query 編輯器中先篩選資料（例如：只載入最近 3 年的資料）
2. 使用「選取資料行」只載入需要的欄位
3. 考慮使用「增量重新整理」功能（Power BI Pro/Premium）

### Q5: 中文顯示亂碼

**問題**：中文字段顯示為亂碼

**解決方案**：
1. 確認 SQLite 資料庫使用 UTF-8 編碼
2. 在 Power Query 編輯器中調整編碼設定
3. 重新載入資料

## 進階技巧

### 建立參數化查詢

如果您想動態改變資料庫路徑或查詢條件：

1. 在 Power Query 編輯器中，選擇「管理參數」→「新增參數」
2. 建立參數（例如：`DBPath`）
3. 在連接字串中使用參數：
   ```
   Driver=SQLite3 ODBC Driver;Database=" & DBPath & ";
   ```

### 使用 SQL 查詢

如果您想直接使用 SQL 查詢：

1. 在「取得資料」→「其他」→「ODBC」中，點擊「進階選項」
2. 在「SQL 陳述式」欄位中輸入 SQL：
   ```sql
   SELECT 
       s.date,
       s.ticker,
       s.close,
       c.score,
       c.signal
   FROM tw_stock_price_data s
   LEFT JOIN business_cycle_data c ON s.date = c.date
   WHERE s.ticker = '006208'
   ORDER BY s.date DESC
   ```

### 設定資料重新整理排程

如果您使用 Power BI 服務（Power BI Pro/Premium），可以設定自動重新整理：

1. 在 Power BI 服務中開啟資料集
2. 選擇「設定」→「排程的重新整理」
3. 設定重新整理頻率和時間

## 參考資源

- [Power BI Desktop 文件](https://learn.microsoft.com/power-bi/fundamentals/desktop-get-the-desktop)
- [ODBC 資料來源連接](https://learn.microsoft.com/power-bi/connect-data/desktop-connect-odbc)
- SQLite ODBC Driver 官方網站：http://www.ch-werner.de/sqliteodbc/
- [Power Query 文件](https://learn.microsoft.com/power-query/)

## 下一步

連接成功後，您可以：

1. 參考 [資料庫結構說明](DATABASE_SCHEMA.md) 了解各資料表的詳細結構
2. 建立各種視覺化和報表
3. 探索資料間的關聯性和趨勢
4. 使用 [Orange 預測指引](ORANGE_PREDICTION_GUIDE.md) 進行進階分析

