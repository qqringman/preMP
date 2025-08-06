# Gen Mapping Excel 操作說明 v2.0

## 系統概述

Gen Mapping Excel 是一個模組化的映射 Excel 檔案產生系統，提供兩大核心功能：

1. **功能1 (chip-mapping)**: 處理晶片映射表，從 SFTP 自動獲取版本資訊
2. **功能2 (prebuild-mapping)**: 處理 Prebuild 來源檔案，進行資料比對與映射

### 主要特點
- 模組化設計，各功能獨立運作
- 支援命令列操作
- 支援 Excel (.xlsx, .xls) 和 CSV (.csv) 檔案格式
- 自動 SFTP 版本擷取
- 靈活的過濾條件設定
- 動態檔案命名

## 安裝需求

### Python 版本
- Python 3.8 或以上版本（建議使用 Python 3.12）

### 必要套件
```bash
pip install pandas openpyxl paramiko
```

### 系統檔案結構
```
project/
├── config.py                  # 系統設定檔
├── utils.py                   # 工具函數
├── excel_handler.py           # Excel 處理模組
├── sftp_downloader.py         # SFTP 下載器
├── gen_mapping_excel.py       # 主程式
├── cli_interface.py           # 命令列介面
├── operation_manual.md        # 操作說明
└── vp_libs/                   # 功能模組目錄
    ├── __init__.py
    ├── sftp_manager.py        # SFTP 管理器
    ├── data_models.py         # 資料模型
    ├── feature1_processor.py  # 功能1處理器
    └── feature2_processor.py  # 功能2處理器
```

### 必要資料檔案
- `all_chip_mapping_table.xlsx` 或 `.csv`：晶片映射表（功能1）
- Prebuild 來源檔案（功能2）：
  - `master_prebuild_source.xlsx` 或 `.csv`
  - `premp_prebuild_source.xlsx` 或 `.csv`
  - `mp_prebuild_source.xlsx` 或 `.csv`
  - `mpbackup_prebuild_source.xlsx` 或 `.csv`

## 功能1: 晶片映射表處理 (chip-mapping)

### 功能說明
處理 `all_chip_mapping_table` 檔案，從 SFTP 伺服器自動獲取最新或指定版本資訊，產生比對映射表。

### 基本用法
```bash
# 使用預設參數（處理所有資料，獲取最新版本）
python3.12 cli_interface.py chip-mapping

# 指定輸入檔案
python3.12 cli_interface.py chip-mapping -i mapping_table.csv
```

### 完整參數說明

| 參數 | 簡寫 | 說明 | 預設值 | 範例 |
|------|------|------|--------|------|
| `--input` | `-i` | 輸入檔案路徑 | all_chip_mapping_table.xlsx | `-i data.csv` |
| `--database` | `-db` | 指定 DB 版本 | all (最新版本) | `-db DB2302#196` |
| `--filter` | `-filter` | 過濾條件 | all | `-filter master_vs_premp` |
| `--output` | `-o` | 輸出目錄 | ./output | `-o ./results` |

### Filter 參數詳細說明

#### 比較類型過濾（忽略大小寫）
- `master_vs_premp`：只產生 master 與 premp 的比對
- `premp_vs_mp`：只產生 premp 與 mp 的比對
- `mp_vs_mpbackup`：只產生 mp 與 mpbackup 的比對
- `all`：產生所有可能的比對組合（預設）

#### 模組過濾（忽略大小寫）
- `mac7p`：只處理 Mac7p 模組
- `mac8p`：只處理 Mac8p 模組
- `merlin7`：只處理 Merlin7 模組
- `merlin8`：只處理 Merlin8 模組

#### 組合使用
可同時使用多個過濾條件，用逗號分隔：
- `mac7p,master_vs_premp`：只處理 Mac7p 模組的 master vs premp 比對
- `merlin7,merlin8`：處理 Merlin7 和 Merlin8 模組

### DB 參數說明

用於指定特定版本，格式為 `DB編號#版本前綴`：
- 單一指定：`-db DB2302#196`
- 多個指定：`-db DB2302#196,DB2686#168`
- 不指定（預設）：自動獲取 SFTP 上版號最大的最新版本

範例：
- `196_all_202508060105` → 版號 196
- `536_all_202507312300` → 版號 536
- 系統會選擇 536（版號較大）

### 輸入檔案格式

#### 必要欄位
```
SN, Module, DB_Type, DB_Info, DB_Folder, SftpPath, 
premp_DB_Type, premp_DB_Info, premp_DB_Folder, premp_SftpPath,
mp_DB_Type, mp_DB_Info, mp_DB_Folder, mp_SftpPath,
mpbackup_DB_Type, mpbackup_DB_Info, mpbackup_DB_Folder, mpbackup_SftpPath
```

#### 範例資料
```csv
1, Merlin7, master, DB2302, DB2302_xxx, /DailyBuild/Merlin7/DB2302_xxx, premp, DB2303, ...
2, Mac7p, master, DB2305, DB2305_xxx, /DailyBuild/Mac7p/DB2305_xxx, premp, DB2306, ...
```

### 輸出檔案
- 檔名：`DailyBuild_mapping.xlsx`
- 位置：指定的輸出目錄（預設 `./output`）

#### 輸出欄位
- SN：序號
- RootFolder：根目錄
- Module：模組名稱
- DB_Type：資料庫類型
- DB_Info：資料庫資訊
- DB_Folder：資料庫資料夾
- DB_Version：版本號（從 SFTP 獲取）
- SftpPath：完整 SFTP 路徑
- compare_DB_Type：比較資料庫類型
- compare_DB_Info：比較資料庫資訊
- compare_DB_Folder：比較資料庫資料夾
- compare_DB_Version：比較版本號
- compare_SftpPath：比較 SFTP 路徑

### 使用範例

```bash
# 範例1：處理所有資料，使用最新版本
python3.12 cli_interface.py chip-mapping

# 範例2：只處理 master vs premp 比對
python3.12 cli_interface.py chip-mapping -filter master_vs_premp

# 範例3：只處理 Mac7p 模組
python3.12 cli_interface.py chip-mapping -filter mac7p

# 範例4：Mac7p 模組的 master vs premp 比對
python3.12 cli_interface.py chip-mapping -filter mac7p,master_vs_premp

# 範例5：指定特定 DB 版本
python3.12 cli_interface.py chip-mapping -db DB2302#196,DB2686#168

# 範例6：使用 CSV 輸入檔案
python3.12 cli_interface.py chip-mapping -i mapping.csv -filter master_vs_premp

# 範例7：完整參數範例
python3.12 cli_interface.py chip-mapping \
    -i all_chip_mapping_table.csv \
    -db DB2302#196 \
    -filter merlin7,master_vs_premp \
    -o ./results
```

## 功能2: Prebuild 映射處理 (prebuild-mapping)

### 功能說明
處理兩個 Prebuild 來源檔案，使用 Inner Join 進行資料比對，產生映射關係表。

### 基本用法
```bash
# 基本用法（需要提供兩個輸入檔案）
python3.12 cli_interface.py prebuild-mapping -i file1.xlsx,file2.xlsx

# 使用 CSV 檔案
python3.12 cli_interface.py prebuild-mapping -i master.csv,premp.csv
```

### 完整參數說明

| 參數 | 簡寫 | 說明 | 預設值 | 範例 |
|------|------|------|--------|------|
| `--input` | `-i` | 輸入檔案（2個） | 必要參數 | `-i file1.csv,file2.csv` |
| `--filter` | `-filter` | 過濾條件 | all | `-filter master_vs_premp` |
| `--output` | `-o` | 輸出目錄 | ./output | `-o ./results` |

### Filter 參數說明

#### 比較類型（決定 DB_Type 欄位值）
- `master_vs_premp`：Master 對 Pre-MP 比較
- `premp_vs_mp`：Pre-MP 對 MP 比較
- `mp_vs_mpbackup`：MP 對 MP Backup 比較

#### 模組過濾
- `mac7p`：只處理 Mac7p 相關資料
- `mac8p`：只處理 Mac8p 相關資料
- `merlin7`：只處理 Merlin7 相關資料
- `merlin8`：只處理 Merlin8 相關資料

### Inner Join 邏輯
系統使用以下四個欄位作為 Join Key：
1. **Category**：類別
2. **Project**：專案
3. **LocalPath**：本地路徑
4. **Master_JIRA**：JIRA 編號

只有當兩個檔案中這四個欄位完全相符時，才會產生映射關係。

### Module 欄位解析規則
根據 SftpPath 路徑結構判斷：
- `/DailyBuild/PrebuildFW/dolby_ko/...` → Module = `dolby_ko`
- `/DailyBuild/Merlin7/...` → Module = `Merlin7`
- `/DailyBuild/Mac7p/...` → Module = `Mac7p`

### 特殊處理規則

#### NotFound 處理
當 SftpPath 為以下值時：
- `NotFound_SFTP_SRC_PATH`
- `sftpNotFound`
- `NotFound`
- 空值或 NaN

處理方式：
1. 使用 Master_JIRA 的值作為 DB_Info
2. 清理 JIRA ID（移除 ">" 符號並 trim）

#### JIRA ID 清理
Master_JIRA 可能包含 ">" 符號，例如：
```
>RDDB-1014
RDDB-428
>MMQCDB-2821
```
系統會自動移除 ">" 並執行 trim 操作。

### 輸入檔案格式

#### 必要欄位
```
ModuleOwner, Remote, Category, Project, Branch, LocalPath, 
Revision, Master_JIRA, PrebuildSRC, SftpURL, Comment
```

#### 範例資料
```csv
changhsiangyu, rtk-prebuilt, dolby_vision_ta, realtek/merlin7/v3.12, 
realtek/android-14/premp, kernel/android/U/vendor, 5e5dc702, 
>RDDB-1000, repo init..., /DailyBuild/PrebuildFW/dolby_ta/RDDB-1000_xxx, ...
```

### 輸出檔案命名規則

根據 `-filter` 參數動態命名：
- 不指定 filter：`PrebuildFW_mapping.xlsx`
- `-filter master_vs_premp`：`PrebuildFW_master_vs_premp_mapping.xlsx`
- `-filter mac7p`：`PrebuildFW_mac7p_mapping.xlsx`
- `-filter premp_vs_mp`：`PrebuildFW_premp_vs_mp_mapping.xlsx`

### 使用範例

```bash
# 範例1：基本用法（輸出 PrebuildFW_mapping.xlsx）
python3.12 cli_interface.py prebuild-mapping -i ret.csv,ret.csv

# 範例2：指定 master vs premp 比較
python3.12 cli_interface.py prebuild-mapping \
    -i master_prebuild_source.csv,premp_prebuild_source.csv \
    -filter master_vs_premp

# 範例3：只處理 Mac7p 模組資料
python3.12 cli_interface.py prebuild-mapping \
    -i file1.xlsx,file2.xlsx \
    -filter mac7p

# 範例4：premp vs mp 比較
python3.12 cli_interface.py prebuild-mapping \
    -i premp_prebuild_source.xlsx,mp_prebuild_source.xlsx \
    -filter premp_vs_mp

# 範例5：指定輸出目錄
python3.12 cli_interface.py prebuild-mapping \
    -i input1.csv,input2.csv \
    -filter mp_vs_mpbackup \
    -o ./prebuild_results

# 範例6：相同檔案自我比對（測試用）
python3.12 cli_interface.py prebuild-mapping -i ret.csv,ret.csv
```

## 測試功能

### SFTP 連線測試
```bash
python3.12 cli_interface.py test
```

測試結果：
- ✓ SFTP 連線成功
- ✗ SFTP 連線失敗：[錯誤訊息]

建議在首次使用前執行測試，確認 SFTP 設定正確。

## 設定檔說明 (config.py)

### SFTP 連線設定
```python
SFTP_HOST = 'mmsftpx.realtek.com'
SFTP_PORT = 22
SFTP_USERNAME = 'lgwar_user'
SFTP_PASSWORD = 'Ab!123456'
SFTP_TIMEOUT = 30
```

### 檔案設定
```python
# 預設檔案名稱
ALL_CHIP_MAPPING_TABLE = 'all_chip_mapping_table.xlsx'
DEFAULT_DAILYBUILD_OUTPUT = 'DailyBuild_mapping.xlsx'
DEFAULT_PREBUILD_OUTPUT = 'PrebuildFW_mapping.xlsx'

# 目標檔案
TARGET_FILES = ['F_Version.txt', 'manifest.xml', 'Version.txt']
```

### 路徑設定
```python
# 路徑替換規則
PATH_REPLACEMENTS = {
    '/mnt/cq488': '/DailyBuild'
}

# 輸出目錄
DEFAULT_OUTPUT_DIR = './downloads'
```

### 版本排序設定
```python
VERSION_SORT_REVERSE = True  # True = 版號大的優先（最新）
```

## 常見問題與解決方法

### Q1: ModuleNotFoundError: No module named 'utils'
**解決方法**：確保檔案結構正確，vp_libs 資料夾內的檔案已正確設定路徑。

### Q2: SFTP 連線失敗
**解決方法**：
1. 執行 `python3.12 cli_interface.py test` 測試連線
2. 檢查網路連線
3. 確認 config.py 中的 SFTP 設定
4. 確認防火牆設定

### Q3: 找不到版本資料夾
**原因**：SFTP 路徑下沒有符合格式的版本資料夾
**解決方法**：
1. 確認 SFTP 路徑正確
2. 檢查路徑下是否有版本資料夾（格式：數字開頭）

### Q4: Inner Join 沒有結果
**原因**：兩個檔案的 Key 欄位不匹配
**解決方法**：
1. 檢查 Category、Project、LocalPath、Master_JIRA 欄位值
2. 確認兩個檔案有相同的記錄
3. 注意大小寫和空格

### Q5: CSV 檔案編碼問題
**解決方法**：系統自動嘗試多種編碼（UTF-8、Big5、GBK 等），通常可自動處理。

### Q6: 過濾條件沒有效果
**解決方法**：
1. 確認拼寫正確（忽略大小寫）
2. 使用逗號分隔多個條件
3. 檢查資料中是否有符合條件的記錄

## 錯誤訊息說明

| 錯誤訊息 | 可能原因 | 解決方法 |
|---------|---------|---------|
| 找不到輸入檔案 | 檔案路徑錯誤或檔案不存在 | 檢查檔案路徑和名稱 |
| 必須提供恰好 2 個輸入檔案 | prebuild-mapping 需要兩個檔案 | 使用逗號分隔兩個檔案路徑 |
| 過濾條件沒有匹配到任何資料 | Filter 設定不當或資料不符合 | 檢查 filter 參數和資料內容 |
| SFTP 連線失敗 | 網路或認證問題 | 檢查網路和 SFTP 設定 |
| 無法讀取 CSV 檔案 | 編碼問題 | 系統會自動嘗試，如仍失敗請轉換編碼 |

## 日誌與除錯

### 日誌等級
在 config.py 中設定：
```python
LOG_LEVEL = 'INFO'  # 可選：DEBUG, INFO, WARNING, ERROR
```

### 查看詳細日誌
設定 `LOG_LEVEL = 'DEBUG'` 可查看更詳細的執行過程。

## 效能優化建議

1. **批次處理**：一次處理多個檔案時，可撰寫批次腳本
2. **SFTP 連線**：大量查詢時保持連線，避免重複連線
3. **快取機制**：相同版本查詢可考慮加入快取

## 系統限制

1. **檔案大小**：建議單檔不超過 100MB
2. **SFTP 逾時**：預設 30 秒，可在 config.py 調整
3. **版本號格式**：必須為數字開頭（如 196_xxx, 536_xxx）

## 版本歷程

### v2.0.0 (2024)
- 新增 CSV 檔案支援
- 統一使用 -filter 參數
- 改進 Module 欄位解析邏輯
- 優化 NotFound 處理
- 動態檔案命名機制
- 版號大小排序（取最大版號）

### v1.0.0 (初始版本)
- 基本功能1和功能2實作
- Excel 檔案處理
- SFTP 自動版本擷取
- 命令列介面

## 聯絡資訊

如有問題或需要技術支援，請聯絡系統管理員。

---
文件更新日期：2024年8月
版本：2.0.0