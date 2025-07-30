# SFTP 下載與比較系統

一個模組化的 Python 系統，用於從 SFTP 下載檔案、比較 manifest.xml 差異，並產生詳細的 Excel 報表。

## 功能特點

- 📥 **智能下載**：自動從 SFTP 路徑及子目錄搜尋並下載檔案
- 🔄 **斷點續傳**：支援多次執行，自動跳過已下載的檔案
- 📊 **進階比較**：實現完整的 manifest.xml 比較邏輯（revision 差異、動態分支檢查等）
- 🏷️ **自動分類**：根據路徑關鍵字自動為資料夾加上後綴（-premp、-wave、-wave.backup）
- 🎯 **彈性比較**：可選擇不同資料夾作為基準進行比較，動態調整檢查規則
- 📁 **多格式支援**：支援標準格式和特殊格式的 FTP 路徑
- 📦 **彈性打包**：可選擇性打包比較結果
- 📋 **美觀報表**：自動格式化的 Excel 報表，包含彩色標題和自動調整欄寬
  - 黃底標題：標記重要欄位
  - 紅字內容：快速識別版本差異
- 📝 **版本檔案比較**：比較 Version.txt 和 F_Version.txt 的內容差異

## 快速開始

### 安裝

```bash
# 克隆或下載專案後
cd sftp_compare_system

# 執行安裝腳本
python setup.py

# 或手動安裝依賴
pip install -r requirements.txt
```

### 基本使用

```bash
# 互動式模式
python main.py

# 命令列模式 - 下載檔案
python main.py download --excel ftp_paths.xlsx

# 命令列模式 - 比較檔案（使用 wave 版本作為基準）
python main.py compare --source-dir ./downloads --base-folder wave

# 命令列模式 - 打包結果
python main.py package --source-dir ./downloads
```

## 專案結構

```
sftp_compare_system/
├── main.py              # 主程式
├── config.py            # 系統設定
├── sftp_downloader.py   # SFTP 下載模組
├── file_comparator.py   # 檔案比較模組
├── zip_packager.py      # ZIP 打包模組
├── excel_handler.py     # Excel 處理模組
├── utils.py            # 共用工具函數
├── requirements.txt     # Python 套件需求
├── setup.py            # 安裝設定腳本
└── README.md           # 本檔案
```

## 設定說明

編輯 `config.py` 設定您的環境：

```python
# SFTP 連線設定
SFTP_HOST = 'your.sftp.server.com'
SFTP_USERNAME = 'your_username'
SFTP_PASSWORD = 'your_password'

# 其他設定...
```

## 輸入格式

Excel 檔案需包含 "ftp path" 欄位，支援兩種格式：

### 標準格式
`/DailyBuild/PrebuildFW/{模組}/{RDDB-XXX}_...`

### 特殊格式
`/DailyBuild/{Merlin7}/{DB2302}_...` → 資料夾為 `Merlin7/DB2302`

## 輸出說明

### 下載功能
- 自動根據路徑關鍵字為資料夾加上後綴
  - `premp.google-refplus` → `-premp`
  - `mp.google-refplus.wave` → `-wave`
  - `mp.google-refplus.wave.backup` → `-wave.backup`
- 產生下載報表顯示每個路徑的下載結果

### 比較功能
- 可選擇不同資料夾作為基準（base）進行比較
- 產生 `all_compare.xlsx` 包含五個頁籤：
  - **revision_diff**：所有 revision 差異（包含 wave 標記）
    - base_short、base_revision、compare_short、compare_revision 標題為黃底，內容為紅字
  - **branch_error**：分支命名錯誤（根據比較對象動態檢查）
    - "problem" 欄位標題為黃底，顯示具體問題
  - **lost_project**：新增/刪除的專案
    - "狀態" 欄位標題為黃底
  - **version_diff**：Version.txt 和 F_Version.txt 的內容差異
    - "is_different" 欄位標題為黃底
  - **無法比對**：無法進行比對的模組清單（如資料夾不足）

## 進階功能

- **遞迴搜尋**：自動在子目錄搜尋檔案（可調整搜尋深度）
- **強制重新下載**：使用 `--force` 參數忽略已存在的檔案
- **自訂 SFTP 設定**：支援命令列參數覆蓋預設設定
- **選擇基準資料夾**：比較時可指定使用哪個版本作為基準
- **動態分支檢查**：根據比較對象自動調整 branch_error 檢查規則
- **版本檔案比較**：自動比較 Version.txt 和 F_Version.txt 的內容差異

## 故障排除

如遇到問題，請：
1. 檢查 SFTP 連線設定
2. 確認 Excel 格式正確
3. 查看控制台的錯誤訊息
4. 調整 `config.py` 中的 `LOG_LEVEL` 為 'DEBUG' 取得更多資訊

## 授權

本專案採用 MIT 授權。

## 作者

由 Claude AI Assistant 協助開發。