# SFTP 下載與比較系統 - 操作說明

## 系統概述
本系統提供三個主要功能：
1. 從 SFTP 下載檔案並產生報表
2. 比較模組下的 manifest.xml/F_Version.txt/Version.txt 差異
3. 打包比對結果成 ZIP 檔案

## 安裝需求
```bash
pip install paramiko pandas openpyxl lxml argparse
```

## 專案結構
```
sftp_compare_system/
├── main.py              # 主程式與互動介面
├── config.py            # 系統設定
├── sftp_downloader.py   # SFTP 下載模組
├── file_comparator.py   # 檔案比較模組
├── zip_packager.py      # ZIP 打包模組
├── excel_handler.py     # Excel 處理模組
└── utils.py            # 共用工具函數
```

## 使用方式

### 1. 互動式介面
```bash
python main.py
```
系統會顯示選單讓您選擇功能。

### 2. 命令列模式

#### 功能一：下載 SFTP 檔案
```bash
# 基本用法
python main.py --function download --excel input.xlsx

# 完整參數
python main.py --function download \
    --excel input.xlsx \
    --host sftp.example.com \
    --port 22 \
    --username user \
    --password pass \
    --output-dir ./downloads
```

參數說明：
- `--excel`: 包含 FTP 路徑的 Excel 檔案
- `--host`: SFTP 伺服器位址（預設：從 config.py 讀取）
- `--port`: SFTP 連接埠（預設：22）
- `--username`: SFTP 使用者名稱
- `--password`: SFTP 密碼
- `--output-dir`: 下載檔案的輸出目錄（預設：./downloads）

#### 功能二：比較檔案差異
```bash
# 基本用法
python main.py --function compare --source-dir /vince/home/all_folder

# 指定輸出目錄
python main.py --function compare \
    --source-dir /vince/home/all_folder \
    --output-dir ./compare_results
```

參數說明：
- `--source-dir`: 包含模組資料夾的根目錄
- `--output-dir`: 比較結果的輸出目錄（預設：source-dir）

#### 功能三：打包 ZIP
```bash
# 基本用法
python main.py --function package --source-dir /vince/home/all_folder

# 指定 ZIP 檔名
python main.py --function package \
    --source-dir /vince/home/all_folder \
    --zip-name compare_results.zip
```

參數說明：
- `--source-dir`: 要打包的資料夾路徑
- `--zip-name`: ZIP 檔案名稱（預設：compare_results_{timestamp}.zip）

### 3. 模組獨立使用

#### 下載模組
```python
from sftp_downloader import SFTPDownloader

downloader = SFTPDownloader(host='sftp.example.com', username='user', password='pass')
downloader.download_from_excel('input.xlsx', output_dir='./downloads')
```

#### 比較模組
```python
from file_comparator import FileComparator

comparator = FileComparator()
comparator.compare_all_modules('/vince/home/all_folder')
```

#### 打包模組
```python
from zip_packager import ZipPackager

packager = ZipPackager()
packager.create_zip('/vince/home/all_folder', 'output.zip')
```

## 設定檔說明 (config.py)

```python
# SFTP 連線設定
SFTP_HOST = 'your.sftp.server.com'
SFTP_PORT = 22
SFTP_USERNAME = 'your_username'
SFTP_PASSWORD = 'your_password'

# 檔案設定
TARGET_FILES = ['F_Version.txt', 'manifest.xml', 'Version.txt']
CASE_INSENSITIVE = True
MAX_SEARCH_DEPTH = 3  # 遞迴搜尋的最大深度（可根據需要調整）

# 輸出設定
DEFAULT_OUTPUT_DIR = './downloads'
DEFAULT_COMPARE_DIR = './compare_results'
```

## Excel 輸入格式

### 功能一的輸入 Excel
需要包含 "ftp path" 欄位，範例：
| SN | 模組 | ftp path |
|----|------|----------|
| 1 | bootcode | /DailyBuild/PrebuildFW/bootcode/RDDB-320_realtek_mac8q_master/20250728_1111_5330ddb |
| 2 | emcu | /DailyBuild/PrebuildFW/emcu/RDDB-321_realtek_mac8q_master/20250728_2222_5330ddb |
| 3 | dolby_ta | /DailyBuild/PrebuildFW/dolby_ta/RDDB-1031_merlin7_3.16_android14_mp.google-refplus.backup/2025_07_03-10_53_618e9e1 |
| 4 | ufsd_ko | /DailyBuild/PrebuildFW/ufsd_ko/RDDB-508_merlin7_android11_mp.google-refplus/2025_07_03-10_53_618e9e1 |

**注意**：系統會自動從路徑中解析模組名稱（如 bootcode、emcu、dolby_ta、ufsd_ko 等）和 JIRA ID（RDDB-XXX）。

## 輸出說明

### 功能一輸出
1. 資料夾結構：
   ```
   downloads/
   ├── bootcode/
   │   └── RDDB-320/
   │       ├── F_Version.txt
   │       ├── manifest.xml
   │       └── Version.txt
   └── emcu/
       └── RDDB-321/
           ├── F_Version.txt
           ├── manifest.xml
           └── Version.txt
   ```

2. Excel 報表：`{原檔名}_report.xlsx`
   | SN | 模組 | sftp 路徑 | 版本資訊檔案 |
   |----|------|-----------|--------------|
   | 1 | bootcode | /DailyBuild/... | F_Version.txt, manifest.xml, Version.txt |
   | 2 | emcu | /DailyBuild/... | F_Version.txt (2025_06_24-17_41_e54f7a5/F_Version.txt), manifest.xml (2025_06_24-17_41_e54f7a5/manifest.xml), Version.txt (2025_06_24-17_41_e54f7a5/Version.txt) |
   
   註：括號內顯示檔案在 FTP 路徑下的相對位置（如果檔案在子目錄中）

### 功能二輸出
1. 各模組比較結果：`{模組名稱}_compare.xlsx`
   - 第一個頁籤：不同的 project
   - 第二個頁籤：新增/刪除的項目

2. 整合報表：`all_compare.xlsx`

### 功能三輸出
- ZIP 檔案包含所有比較結果和下載的檔案

## 注意事項
1. 確保 SFTP 伺服器連線資訊正確
2. Excel 檔案路徑必須包含 "ftp path" 欄位
3. 比較功能需要每個模組下有兩個資料夾才能進行比較
4. 檔案名稱比對不區分大小寫
5. 系統會自動在 FTP 路徑及其子目錄中遞迴搜尋目標檔案（最多搜尋 3 層深度）

## 錯誤處理
- 連線失敗：檢查 SFTP 設定和網路連線
- 檔案不存在：確認 FTP 路徑正確且檔案存在
- 權限問題：確認有足夠的讀寫權限

## 完整使用範例

### 範例 1：完整工作流程
```bash
# 1. 從 Excel 下載 SFTP 檔案
python main.py download --excel ftp_paths.xlsx --output-dir ./downloads

# 2. 比較下載的檔案
python main.py compare --source-dir ./downloads

# 3. 打包結果
python main.py package --source-dir ./downloads --zip-name results.zip
```

### 範例 2：使用自訂 SFTP 設定
```bash
python main.py download \
    --excel input.xlsx \
    --host 192.168.1.100 \
    --port 2222 \
    --username myuser \
    --password mypass \
    --output-dir ./my_downloads
```

### 範例 3：互動式模式使用
```
$ python main.py

==================================================
SFTP 下載與比較系統
==================================================
1. 下載 SFTP 檔案並產生報表
2. 比較模組檔案差異
3. 打包比對結果成 ZIP
4. 測試 SFTP 連線
5. 退出
==================================================
請選擇功能 (1-5): 1

--- 下載 SFTP 檔案 ---
請輸入 Excel 檔案路徑: ftp_paths.xlsx
使用預設 SFTP 設定？(Y/n): Y
輸出目錄 (預設: ./downloads): 

下載完成！報表已儲存至: ./downloads/ftp_paths_report.xlsx
```