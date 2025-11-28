# GitHub 上傳指引

本文件將引導您將此專案上傳到 GitHub 倉庫。

## 前置準備

### 1. 安裝 Git

如果您的電腦還沒有安裝 Git，請先下載並安裝：

- **Windows**: 從 [Git for Windows](https://git-scm.com/download/win) 下載
- **Mac**: 使用 Homebrew 安裝：`brew install git`
- **Linux**: 使用套件管理器安裝，例如：`sudo apt-get install git`

安裝完成後，開啟終端機（命令提示字元或 PowerShell），輸入以下命令驗證：

```bash
git --version
```

如果顯示版本號碼，表示安裝成功。

### 2. 建立 GitHub 帳號（如果還沒有）

1. 前往 [GitHub](https://github.com/)
2. 點擊右上角 "Sign up" 註冊新帳號
3. 完成註冊流程

### 3. 設定 Git 使用者資訊

首次使用 Git 需要設定您的姓名和電子郵件：

```bash
git config --global user.name "您的姓名"
git config --global user.email "your.email@example.com"
```

## 步驟一：初始化 Git 倉庫

在專案根目錄（`Business_Cycle_stratgy`）開啟終端機，執行：

```bash
cd D:\Business_Cycle_stratgy
git init
```

這會建立一個隱藏的 `.git` 資料夾，Git 會開始追蹤您的專案。

## 步驟二：檢查 .gitignore 檔案

確認專案根目錄有 `.gitignore` 檔案（應該已經存在）。此檔案會告訴 Git 哪些檔案不需要上傳。

`.gitignore` 已經設定排除：
- 資料庫檔案（`*.db`）
- Python 快取檔案（`__pycache__/`）
- 虛擬環境（`venv/`）
- IDE 設定檔
- 暫存 JSON 檔案

## 步驟三：將檔案加入 Git 追蹤

將所有檔案加入 Git（`.gitignore` 指定的檔案會被自動排除）：

```bash
git add .
```

查看哪些檔案會被加入（可選，用於確認）：

```bash
git status
```

您應該會看到所有被加入的檔案列表，但不應該看到 `.db` 檔案。

## 步驟四：建立第一個提交（Commit）

將檔案提交到本地倉庫：

```bash
git commit -m "Initial commit: 景氣週期投資策略系統"
```

`-m` 後面是提交訊息，描述這次提交的內容。

## 步驟五：在 GitHub 建立新倉庫

1. 登入 GitHub
2. 點擊右上角 "+" 圖示，選擇 "New repository"
3. 填寫倉庫資訊：
   - **Repository name**: 例如 `Business_Cycle_Strategy` 或 `taiwan-stock-strategy`
   - **Description**: 例如 "基於景氣燈號的台灣股市投資策略系統"
   - **Visibility**: 選擇 Public（公開）或 Private（私人）
   - **不要**勾選 "Initialize this repository with a README"（因為我們已經有 README 了）
4. 點擊 "Create repository"

## 步驟六：連接本地倉庫與 GitHub

GitHub 會顯示一個頁面，裡面有連接指令。複製並執行以下命令（將 `YOUR_USERNAME` 和 `YOUR_REPO_NAME` 替換成您的實際值）：

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
```

例如，如果您的使用者名稱是 `john`，倉庫名稱是 `Business_Cycle_Strategy`，則命令是：

```bash
git remote add origin https://github.com/john/Business_Cycle_Strategy.git
```

## 步驟七：上傳到 GitHub

將本地倉庫推送到 GitHub：

```bash
git branch -M main
git push -u origin main
```

系統可能會要求您輸入 GitHub 的使用者名稱和密碼（或 Personal Access Token）。

### 如果遇到認證問題

GitHub 已經不支援使用密碼認證，您需要使用 **Personal Access Token**：

1. 前往 GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 點擊 "Generate new token (classic)"
3. 勾選 `repo` 權限
4. 產生 Token 後，複製下來
5. 當 Git 要求輸入密碼時，使用這個 Token 代替密碼

## 步驟八：驗證上傳

回到 GitHub 網頁，重新整理您的倉庫頁面，應該可以看到所有檔案已經上傳成功。

確認以下幾點：
- ✅ 所有程式碼檔案都在
- ✅ README.md 顯示正常
- ✅ **沒有** `.db` 資料庫檔案（應該被排除）

## 後續更新流程

當您修改了程式碼，想要更新到 GitHub 時：

```bash
# 1. 查看修改的檔案
git status

# 2. 將修改的檔案加入
git add .

# 3. 提交修改（加上描述訊息）
git commit -m "描述這次修改的內容，例如：新增資料驗證功能"

# 4. 推送到 GitHub
git push
```

## 常見問題

### Q: 我忘記排除某些檔案就上傳了，怎麼辦？

如果已經上傳了不想上傳的檔案（例如資料庫檔案），可以：

1. 將檔案加入 `.gitignore`
2. 從 Git 追蹤中移除（但保留本地檔案）：
   ```bash
   git rm --cached *.db
   ```
3. 提交並推送：
   ```bash
   git commit -m "Remove database files from tracking"
   git push
   ```

### Q: 如何查看 Git 歷史記錄？

```bash
git log
```

按 `q` 退出。

### Q: 如何取消一個未提交的修改？

如果修改了檔案但還沒 `commit`，想恢復到原本的狀態：

```bash
git checkout -- 檔案名稱
```

或者恢復所有檔案：

```bash
git checkout -- .
```

### Q: 如何建立新的分支？

```bash
git checkout -b 分支名稱
```

例如：`git checkout -b feature-new-strategy`

## 進階技巧

### 使用 SSH 金鑰（避免每次輸入密碼）

1. 產生 SSH 金鑰：
   ```bash
   ssh-keygen -t ed25519 -C "your.email@example.com"
   ```
2. 將公開金鑰加入 GitHub（Settings → SSH and GPG keys）
3. 將 remote URL 改為 SSH：
   ```bash
   git remote set-url origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git
   ```

### 使用 GitHub Desktop（圖形介面工具）

如果您不喜歡使用命令列，可以使用 [GitHub Desktop](https://desktop.github.com/)：
- 下載並安裝 GitHub Desktop
- 登入您的 GitHub 帳號
- 開啟專案資料夾
- 使用圖形介面進行提交和推送

## 需要幫助？

- Git 官方文件：https://git-scm.com/doc
- GitHub 說明文件：https://docs.github.com/
- Git 教學：https://learngitbranching.js.org/

## 複製命令快速參考

如果您想快速執行所有步驟，以下是一次性命令（記得替換 `YOUR_USERNAME` 和 `YOUR_REPO_NAME`）：

```bash
cd D:\Business_Cycle_stratgy
git init
git add .
git commit -m "Initial commit: 景氣週期投資策略系統"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

