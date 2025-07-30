# SFTP 下載與比較系統 - 完整使用說明

## 系統概述

本系統提供兩種操作方式：
1. **命令列介面**：適合自動化腳本和批次處理
2. **Web 介面**：提供友善的圖形化操作和互動式資料分析

## 快速開始

### 安裝系統

```bash
# 1. 克隆或下載專案
cd sftp_compare_system

# 2. 安裝基礎套件
pip install -r requirements.txt

# 3. 安裝 Web 介面額外套件（選用）
pip install flask flask-socketio eventlet
```

### 設定系統

編輯 `config.py` 設定您的環境：
```python
# SFTP 連線設定
SFTP_HOST = 'your.sftp.server.com'
SFTP_USERNAME = 'your_username'
SFTP_PASSWORD = 'your_password'
```

## 命令列介面使用

### 1. 互動式模式

```bash
python main.py
```

系統會顯示選單：
```
==================================================
SFTP 下載與比較系統
==================================================
1. 下載 SFTP 檔案並產生報表
2. 比較模組檔案差異
3. 打包比對結果成 ZIP
4. 測試 SFTP 連線
5. 清除暫存檔案
6. 【全部比對】執行所有比對情境
7. 【一步到位】下載→比較→打包
8. 退出
==================================================
```

### 2. 命令列模式

#### 一步到位處理
```bash
# 使用預設 SFTP 設定
python main.py all --excel ftp_paths.xlsx

# 使用自訂 SFTP 設定
python main.py all --excel ftp_paths.xlsx \
    --host sftp.example.com \
    --username myuser \
    --password mypass
```

#### 單獨執行各功能
```bash
# 下載檔案
python main.py download --excel ftp_paths.xlsx

# 執行所有比對情境
python main.py compare --source-dir ./downloads --all-scenarios

# 執行特定比對
python main.py compare --source-dir ./downloads --mode master_vs_premp

# 打包結果
python main.py package --source-dir ./downloads --zip-name results.zip
```

## Web 介面使用

### 啟動 Web 伺服器

```bash
# 開發模式
python web_app.py

# 生產模式
gunicorn -k eventlet -w 1 --bind 0.0.0.0:5000 web_app:app
```

瀏覽器訪問：http://localhost:5000

### Web 功能說明

#### 1. 一步到位處理
- 路徑：`/one-step`
- 功能：自動執行下載→比對→打包全流程
- 特色：
  - 拖放上傳 Excel
  - 即時進度追蹤
  - WebSocket 即時更新
  - 詳細處理日誌

#### 2. 比較功能
- 路徑：`/compare`
- 功能：執行各種比對情境
- 支援情境：
  - 執行所有比對
  - Master vs PreMP
  - PreMP vs Wave
  - Wave vs Wave.backup
- 特色：
  - 自動偵測可用目錄
  - 視覺化結果圖表
  - 快速匯出功能

#### 3. 結果報表（樞紐分析）
- 路徑：`/results/<task_id>`
- 功能：互動式資料分析
- 特色：
  - 類似 Excel 的樞紐分析表
  - 拖放式操作介面
  - 多種彙總函數
  - 即時篩選功能
  - 多格式匯出

## 輸入檔案格式

### Excel 檔案格式
必須包含 "ftp path" 欄位：

| SN | 模組 | ftp path | 備註 |
|----|------|----------|------|
| 1 | bootcode | /DailyBuild/PrebuildFW/bootcode/RDDB-320_realtek_mac8q_master/20250728_1111 | 主版本 |
| 2 | bootcode | /DailyBuild/PrebuildFW/bootcode/RDDB-320_realtek_mac8q_premp.google-refplus/20250729_3333 | PreMP 版本 |
| 3 | Merlin7 | /DailyBuild/Merlin7/DB2302_Merlin7_32Bit_FW_Android14/533_all_202507282300 | 特殊格式 |

## 輸出說明

### 1. 下載結果
```
downloads/
├── PrebuildFW/
│   ├── bootcode/
│   │   ├── RDDB-320/         # 預設版本
│   │   ├── RDDB-320-premp/   # PreMP 版本
│   │   └── RDDB-320-wave/    # Wave 版本
│   └── emcu/
│       └── RDDB-321/
└── DailyBuild/
    └── Merlin7/
        └── DB2302/
```

### 2. 比對報表
- **all_scenarios_compare.xlsx**：所有情境的整合報表
  - 摘要：統計各情境的成功/失敗數
  - revision_diff：所有 revision 差異
  - branch_error：分支命名錯誤
  - lost_project：新增/刪除的專案
  - version_diff：版本檔案差異
  - 無法比對：缺少必要資料夾的模組

### 3. 重要欄位標記
- **深紅底白字標題**：
  - revision 相關欄位（base_short、base_revision、compare_short、compare_revision）
  - problem（問題描述）
  - 狀態（新增/刪除）
  - is_different（版本差異）
- **紅字內容**：revision 差異值
- **自動篩選**：branch_error 預設只顯示需修正的項目

## 比對邏輯說明

### 1. 自動偵測比對類型
系統會根據資料夾名稱自動判斷比對類型：
- RDDB-XXX vs RDDB-XXX-premp → 檢查 premp 命名規則
- RDDB-XXX-premp vs RDDB-XXX-wave → 檢查 wave 命名規則
- RDDB-XXX-wave vs RDDB-XXX-wave.backup → 檢查 wave.backup 命名規則

### 2. 分支錯誤檢查
- 只檢查 compare 資料夾中的項目
- 根據資料夾類型動態調整檢查規則
- 包含 'wave' 的項目不會被標記為錯誤

### 3. 版本檔案比較
- 自動比較 Version.txt 和 F_Version.txt
- 顯示內容差異（最多 100 字元）
- 只顯示有差異的檔案

## 進階功能

### 1. 樞紐分析使用方式
1. 進入結果頁面
2. 點擊「切換樞紐分析」
3. 拖曳欄位到不同區域：
   - **行**：垂直分組
   - **列**：水平分組
   - **值**：要彙總的數據
4. 選擇彙總函數（總和、平均、計數等）
5. 可匯出分析結果

### 2. 資料篩選
1. 點擊右下角篩選按鈕
2. 選擇要篩選的欄位和值
3. 點擊「套用篩選」
4. 可同時篩選多個欄位

### 3. 批次處理腳本
```python
# batch_process.py
import subprocess
import glob

# 處理所有 Excel 檔案
for excel_file in glob.glob("*.xlsx"):
    if not excel_file.endswith("_report.xlsx"):
        print(f"處理 {excel_file}...")
        subprocess.run([
            "python", "main.py", "all",
            "--excel", excel_file
        ])
```

## 故障排除

### 常見問題

1. **SFTP 連線失敗**
   ```bash
   # 測試連線
   python main.py
   # 選擇 4 測試 SFTP 連線
   ```

2. **找不到檔案**
   - 檢查 FTP 路徑是否正確
   - 調整 `MAX_SEARCH_DEPTH` 增加搜尋深度
   - 查看下載報表了解實際路徑

3. **Web 介面無法啟動**
   ```bash
   # 檢查埠是否被占用
   netstat -an | grep 5000
   
   # 使用不同埠
   python web_app.py --port 8080
   ```

4. **記憶體不足**
   - 分批處理大量檔案
   - 調整 pandas 讀取參數
   - 使用串流處理

### 除錯模式
```python
# 在 config.py 設定
LOG_LEVEL = 'DEBUG'
```

## 效能優化建議

1. **並行下載**
   - 修改 `sftp_downloader.py` 使用 ThreadPoolExecutor
   - 建議最多 5 個並行連線

2. **大檔案處理**
   - 使用分塊讀取
   - 實作進度回調

3. **資料庫快取**
   - 儲存比對結果
   - 避免重複計算

## 安全建議

1. **密碼管理**
   - 使用環境變數儲存密碼
   - 不要將密碼提交到版本控制

2. **權限控制**
   - Web 介面加入認證機制
   - 限制檔案上傳大小和類型

3. **日誌記錄**
   - 記錄所有操作
   - 定期清理舊日誌

## API 參考

### Python API
```python
from sftp_downloader import SFTPDownloader
from file_comparator import FileComparator
from zip_packager import ZipPackager

# 下載
downloader = SFTPDownloader(host, port, username, password)
report = downloader.download_from_excel('input.xlsx', './output')

# 比較
comparator = FileComparator()
results = comparator.compare_all_scenarios('./downloads', './results')

# 打包
packager = ZipPackager()
zip_path = packager.create_zip('./results', 'output.zip')
```

### REST API
```bash
# 上傳檔案
curl -X POST -F "file=@input.xlsx" http://localhost:5000/api/upload

# 執行一步到位
curl -X POST http://localhost:5000/api/one-step \
  -H "Content-Type: application/json" \
  -d '{"excel_file": "path/to/file.xlsx"}'

# 取得狀態
curl http://localhost:5000/api/status/task_id

# 匯出結果
curl -O http://localhost:5000/api/export-excel/task_id
```

## 版本更新說明

### v2.0.0 (2024-01)
- ✨ 新增 Web 介面
- ✨ 支援一步到位處理
- ✨ 支援所有比對情境自動執行
- ✨ 新增互動式樞紐分析功能
- 🎨 採用北歐藍設計風格
- 🔧 改進比對邏輯和錯誤處理

### v1.0.0 (2023-12)
- 🚀 初始版本發布
- 📥 支援 SFTP 下載
- 🔄 支援檔案比對
- 📦 支援結果打包

## 聯絡與支援

如有問題或建議，請：
1. 查看本說明文件
2. 檢查 logs 目錄的錯誤日誌
3. 聯絡系統管理員

---

本系統由 Claude AI Assistant 協助開發
