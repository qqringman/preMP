# JIRA/Gerrit 整合工具系統

## 📖 系統概述

本系統是一個專業的 **JIRA/Gerrit 整合工具**，提供三大核心功能模組，專門處理 Android manifest 檔案管理、分支映射和版本轉換。系統採用模組化設計，支援互動式操作和命令行調用，並整合 JIRA 和 Gerrit API 提供自動化的工作流程。

### 🎯 核心功能

1. **🔍 功能一：擴充晶片映射表**
   - 將 `all_chip_mapping_table.xlsx` 擴充並下載相關 JIRA 檔案
   - 自動從 JIRA 提取 manifest 資訊並下載檔案
   - 產生完整的映射表和分析報告

2. **🌿 功能二：建立分支映射表**
   - 透過 manifest.xml 建立分支對應表
   - 支援 Tag 和 Branch 的存在性檢查
   - 可選擇性建立實際的 Gerrit 分支

3. **📄 功能三：Manifest 轉換工具 (全新版本)**
   - 從 Gerrit 自動下載源檔案進行 revision 轉換
   - 支援 master→premp、premp→mp、mp→mpbackup 轉換
   - 智能差異分析和詳細報告

## 🗂️ 專案結構

```
project/
├── README.md                  # 本文件
├── config.py                  # 系統設定檔
├── excel_handler.py           # Excel 處理模組
├── start.py                   # 系統啟動腳本
├── start.bat                  # Windows 批次啟動檔
├── requirements.txt           # Python 套件依賴
└── overwrite_lib/             # 主要程式模組目錄
    ├── main.py                # 主程式互動式介面
    ├── utils.py               # 通用工具模組
    ├── jira_manager.py        # JIRA API 管理模組
    ├── gerrit_manager.py      # Gerrit API 管理模組 (已修復下載問題)
    ├── feature_one.py         # 功能一：擴充晶片映射表
    ├── feature_two.py         # 功能二：建立分支映射表
    ├── feature_three.py       # 功能三：Manifest 轉換工具
    └── download_diagnostic_tool.py # Gerrit 下載診斷工具
```

## 🚀 快速開始

### 系統需求

- **Python**: 3.7 或更高版本
- **作業系統**: Windows, Linux, macOS
- **網路**: 需要存取 JIRA 和 Gerrit 伺服器

### 安裝步驟

1. **安裝 Python 依賴套件**
   ```bash
   pip install -r requirements.txt
   ```

2. **設定系統配置**
   
   編輯 `config.py` 檔案，設定您的 JIRA 和 Gerrit 連線資訊：

   ```python
   # JIRA 設定
   JIRA_SITE = 'jira.realtek.com'
   JIRA_USER = 'your_username'
   JIRA_PASSWORD = 'your_password'
   JIRA_TOKEN = 'your_token'  # 可選，優先使用

   # Gerrit 設定
   GERRIT_BASE = 'https://mm2sd.rtkbf.com/'
   GERRIT_USER = 'your_username'
   GERRIT_PW = 'your_password'
   ```

3. **驗證設定**
   ```bash
   python start.py
   # 選擇 [4] 系統工具 → [1] 測試 JIRA 連線
   # 選擇 [4] 系統工具 → [2] 測試 Gerrit 連線
   ```

## 🎮 使用方式

### 方法一：互動式操作 (推薦)

```bash
# 方法 1: 使用啟動腳本
python start.py

# 方法 2: Windows 用戶
start.bat

# 方法 3: 直接啟動
cd overwrite_lib
python main.py
```

### 方法二：命令行調用

#### 功能一：擴充晶片映射表

```bash
cd overwrite_lib
python -c "
from feature_one import FeatureOne
feature_one = FeatureOne()
success = feature_one.process(
    input_file='path/to/all_chip_mapping_table.xlsx',
    output_folder='./output'
)
print('✅ 成功' if success else '❌ 失敗')
"
```

#### 功能二：建立分支映射表

```bash
cd overwrite_lib
python -c "
from feature_two import FeatureTwo
feature_two = FeatureTwo()
success = feature_two.process(
    input_file='path/to/manifest.xml',
    process_type='master_vs_premp',  # 或 'premp_vs_mp', 'mp_vs_mpbackup'
    output_file='manifest_premp.xlsx',
    remove_duplicates=True,
    create_branches=False,
    check_branch_exists=True,
    output_folder='./output'
)
print('✅ 成功' if success else '❌ 失敗')
"
```

#### 功能三：Manifest 轉換工具

```bash
cd overwrite_lib
python -c "
from feature_three import FeatureThree
feature_three = FeatureThree()
success = feature_three.process(
    overwrite_type='master_to_premp',  # 或 'premp_to_mp', 'mp_to_mpbackup'
    output_folder='./output',
    excel_filename='conversion_report.xlsx'
)
print('✅ 成功' if success else '❌ 失敗')
"
```

## 📋 功能詳細說明

### 🔍 功能一：擴充晶片映射表

**目的**：將 `all_chip_mapping_table.xlsx` 擴充成包含完整 JIRA 資訊的映射表

**輸入**：
- `all_chip_mapping_table.xlsx` 檔案

**處理流程**：
1. 讀取 Excel 中的 `DB_Info`, `premp_DB_Info`, `mp_DB_Info`, `mpbackup_DB_Info` 欄位
2. 將 DB 資訊轉換成 JIRA 連結 (例：DB2302 → MMQCDB-2302)
3. 從 JIRA 描述中提取 `repo init` 指令和 manifest 資訊
4. 自動下載 manifest 檔案到本地資料夾
5. 檢查檔案在 Gerrit 和本地的可用性

**輸出**：
- `all_chip_mapping_table_ext.xlsx`：擴充後的完整資料表
- `DB{number}/`：各 DB 對應的 manifest 檔案資料夾
- **Excel 頁籤**：
  - `主要資料`：擴充後的完整資料表
  - `缺少_manifest`：無法取得的 manifest 檔案記錄
  - `共用`：可共用的 Source 來源記錄

**命令行範例**：
```bash
python -c "
from feature_one import FeatureOne
feature_one = FeatureOne()
feature_one.process(
    input_file='all_chip_mapping_table.xlsx',
    output_folder='./output'
)
"
```

### 🌿 功能二：建立分支映射表

**目的**：透過 manifest.xml 建立分支對應表，支援分支轉換和批次建立

**輸入**：
- `manifest.xml` 檔案
- 處理類型：`master_vs_premp`, `premp_vs_mp`, `mp_vs_mpbackup`

**處理流程**：
1. 解析 manifest.xml 中的所有 project 元素
2. 根據處理類型轉換分支名稱
3. 檢查目標分支/Tag 是否已存在 (可選)
4. 去除重複資料 (可選)
5. 透過 Gerrit API 建立實際分支 (可選)

**分支轉換規則**：
- `master_vs_premp`: `realtek/android-14/master` → `realtek/android-14/premp.google-refplus`
- `premp_vs_mp`: `premp.google-refplus` → `mp.google-refplus.wave`
- `mp_vs_mpbackup`: `mp.google-refplus.wave` → `mp.google-refplus.wave.backup`

**輸出**：
- `manifest_{process_type}.xlsx`：分支映射表
- **Excel 頁籤**：
  - `專案列表`：轉換後的專案清單 (包含 target_type, target_branch_exists 等新欄位)
  - `重覆`：重複的專案資料 (如有)
  - `Branch 建立狀態`：分支建立結果 (如有執行建立)

**命令行範例**：
```bash
python -c "
from feature_two import FeatureTwo
feature_two = FeatureTwo()
feature_two.process(
    input_file='manifest.xml',
    process_type='master_vs_premp',
    output_file='output.xlsx',
    remove_duplicates=True,
    create_branches=False,
    check_branch_exists=True,
    output_folder='./output'
)
"
```

### 📄 功能三：Manifest 轉換工具 (全新版本)

**目的**：從 Gerrit 自動下載源檔案，進行 revision 轉換，並與目標檔案比較差異

**輸入**：
- 轉換類型：`master_to_premp`, `premp_to_mp`, `mp_to_mpbackup`

**處理流程**：
1. 根據轉換類型從 Gerrit 自動下載對應的源檔案
2. 進行智能 revision 轉換
3. 保存轉換後的檔案
4. 從 Gerrit 下載目標檔案進行比較
5. 進行逐行差異分析
6. 產生詳細的 Excel 報告

**檔案映射表**：
| 轉換類型 | 源檔案 | 輸出檔案 | 比較目標 |
|---------|-------|---------|----------|
| `master_to_premp` | `atv-google-refplus.xml` | `atv-google-refplus-premp.xml` | Gerrit: `atv-google-refplus-premp.xml` |
| `premp_to_mp` | `atv-google-refplus-premp.xml` | `atv-google-refplus-wave.xml` | Gerrit: `atv-google-refplus-wave.xml` |
| `mp_to_mpbackup` | `atv-google-refplus-wave.xml` | `atv-google-refplus-wave-backup.xml` | Gerrit: `atv-google-refplus-wave-backup.xml` |

**Revision 轉換規則**：

*master_to_premp*：
- `realtek/android-14/master` → `realtek/android-14/premp.google-refplus`
- `realtek/linux-5.15/android-14/master` → `realtek/linux-5.15/android-14/premp.google-refplus`
- `realtek/master` → `realtek/android-14/premp.google-refplus`
- `realtek/gaia` → `realtek/android-14/premp.google-refplus`
- 其他未匹配 → `realtek/android-14/premp.google-refplus`

*premp_to_mp*：
- 所有 `premp.google-refplus` → `mp.google-refplus.wave`

*mp_to_mpbackup*：
- 所有 `mp.google-refplus.wave` → `mp.google-refplus.wave.backup`

**輸出**：
- 轉換後的 XML 檔案
- 從 Gerrit 下載的目標檔案 (前綴 `gerrit_`)
- **Excel 報告頁籤**：
  - `轉換摘要`：整體轉換統計
  - `轉換後專案`：所有轉換後的專案清單
  - `{type}_差異部份`：逐筆差異分析 (🟢綠底白字 vs 🔵藍底白字)

**命令行範例**：
```bash
python -c "
from feature_three import FeatureThree
feature_three = FeatureThree()
feature_three.process(
    overwrite_type='master_to_premp',
    output_folder='./output',
    excel_filename='conversion_report.xlsx'
)
"
```

## ⚙️ 系統配置

### config.py 設定檔

```python
# SFTP/Gerrit 連線設定
GERRIT_BASE = 'https://mm2sd.rtkbf.com/'
GERRIT_API_PREFIX = '/a'
GERRIT_USER = 'your_username'
GERRIT_PW = 'your_password'

# JIRA 連線設定
JIRA_SITE = 'jira.realtek.com'
JIRA_USER = 'your_username'
JIRA_PASSWORD = 'your_password'
JIRA_TOKEN = 'your_api_token'  # 可選，優先使用

# 檔案設定
TARGET_FILES = ['F_Version.txt', 'manifest.xml', 'Version.txt']
DEFAULT_OUTPUT_DIR = './downloads'
DEFAULT_COMPARE_DIR = './compare_results'

# Excel 設定
FTP_PATH_COLUMN = 'ftp path'
FTP_PATH_COLUMN_ALTERNATIVE = 'SftpURL'

# Gerrit URL 設定
GERRIT_BASE_URL_PREBUILT = "https://mm2sd-git2.rtkbf.com/gerrit/plugins/gitiles/"
GERRIT_BASE_URL_NORMAL = "https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/"
```

### 環境變數設定

系統會自動設定以下環境變數：
```bash
JIRA_SITE=jira.realtek.com
JIRA_USER=your_username
JIRA_PASSWORD=your_password
JIRA_TOKEN=your_token

GERRIT_BASE=https://mm2sd.rtkbf.com/
GERRIT_API_PREFIX=/a
GERRIT_USER=your_username
GERRIT_PW=your_password
```

## 🔧 系統工具

### 連線測試

**測試 JIRA 連線**：
```bash
python start.py
# 選擇 [4] 系統工具 → [1] 測試 JIRA 連線
```

**測試 Gerrit 連線**：
```bash
python start.py
# 選擇 [4] 系統工具 → [2] 測試 Gerrit 連線
```

### 診斷工具

**Gerrit 下載診斷**：
```bash
cd overwrite_lib
python download_diagnostic_tool.py
```

**連線問題診斷**：
```bash
python start.py
# 選擇 [4] 系統工具 → [4] 診斷連線問題
```

## 📊 輸出檔案格式

### Excel 檔案特色

所有輸出的 Excel 檔案都包含：
- 🎨 **美化的標題列**：藍色背景、白色字體
- 📏 **自動調整欄寬**：根據內容長度調整
- 📊 **多個工作表**：依功能需求分類
- 🎯 **狀態欄位的顏色標示**：
  - 功能二：Y (🟢綠色)、N (🔴紅色)、- (⚫黑色)
  - 功能三：相同 (🟢綠色)、不同 (🔴紅色)、無法存取 (🟡黃色)

### 特殊格式標示

**功能二分支檢查欄位**：
- `target_type`：Tag (🔵藍字)、Branch (🟣紫字)
- `target_branch_exists`：Y (🟢綠字)、N (🔴紅字)、- (⚫黑字)

**功能三差異分析欄位**：
- 🟢 **綠底白字**：轉換後的資料欄位
- 🔵 **藍底白字**：Gerrit 的資料欄位

## 🐛 故障排除

### 常見問題

**1. JIRA 連線失敗 (HTTP 403)**
```bash
❌ 症狀：認證失敗、權限被拒
💡 解決方案：
  1. 檢查 config.py 中的帳號密碼
  2. 確認帳號沒有被鎖定
  3. 嘗試使用 API Token 替代密碼
  4. 確認帳號有對應專案的存取權限
```

**2. Gerrit 認證問題 (HTTP 401)**
```bash
❌ 症狀：下載檔案失敗、API 存取被拒
💡 解決方案：
  1. 確認 config.py 中的 GERRIT_USER 和 GERRIT_PW
  2. 檢查帳號是否為 Gerrit 註冊用戶
  3. 確認網路連線和 VPN 設定
```

**3. 檔案處理錯誤**
```bash
❌ 症狀：Excel 讀取失敗、XML 解析錯誤
💡 解決方案：
  1. 確認檔案格式正確 (Excel/XML)
  2. 檢查檔案是否被其他程式占用
  3. 確認有足夠的磁碟空間
```

**4. Gerrit 下載問題**
```bash
❌ 症狀：下載的檔案內容不正確、格式異常
💡 解決方案：
  1. 執行 Gerrit 下載診斷工具
  2. 檢查網路連線穩定性
  3. 確認 Gerrit API 可用性
```

### 診斷步驟

1. **執行系統診斷**：
   ```bash
   python start.py
   # 選擇 [4] 系統工具 → [4] 診斷連線問題
   ```

2. **測試各項連線**：
   ```bash
   # 測試 JIRA
   python start.py → [4] → [1]
   
   # 測試 Gerrit  
   python start.py → [4] → [2]
   ```

3. **檢查日誌資訊**：
   系統會輸出詳細的執行日誌，包含錯誤訊息和處理狀態

4. **執行特定診斷**：
   ```bash
   cd overwrite_lib
   python download_diagnostic_tool.py  # Gerrit 下載診斷
   ```

## 🏗️ 技術架構

### 模組架構圖

```
┌─────────────────────────────────────────┐
│                main.py                  │
│            (互動式介面)                   │
└─────────────┬───────────────────────────┘
              │
┌─────────────┼───────────────────────────┐
│             ▼                           │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │feature_one  │  │  feature_two    │   │
│  │(晶片映射表)  │  │  (分支映射表)    │   │
│  └─────────────┘  └─────────────────┘   │
│              ┌─────────────────┐        │
│              │  feature_three  │        │
│              │  (轉換工具)      │        │
│              └─────────────────┘        │
└─────────────┬───────────────────────────┘
              │
┌─────────────┼───────────────────────────┐
│             ▼                           │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │jira_manager  │  │ gerrit_manager  │  │
│  │(JIRA API)    │  │ (Gerrit API)    │  │
│  └──────────────┘  └─────────────────┘  │
│                                         │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │excel_handler │  │     utils       │  │
│  │(Excel處理)   │  │   (通用工具)     │  │
│  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────┘
```

### 核心類別

**GerritManager**：
- Gerrit API 連線管理
- 檔案下載 (支援 API 風格 URL)
- 分支/Tag 查詢和建立
- 修復了下載檔案格式問題

**JiraManager**：
- JIRA API 連線管理  
- Issue 資訊提取
- 支援 Token 和基本認證

**ExcelHandler**：
- Excel/CSV 檔案讀寫
- 格式化和樣式設定
- 多頁籤報告產生

### 資料流程

```
輸入檔案/參數
    ↓
特定功能模組處理
    ↓
API 管理模組 (JIRA/Gerrit)
    ↓
Excel 處理模組
    ↓
格式化輸出檔案
```

## 📦 依賴套件

```
pandas>=1.5.0
openpyxl>=3.0.0
requests>=2.28.0
xml>=0.4.0
```

安裝方式：
```bash
pip install -r requirements.txt
```

## 🔐 安全注意事項

1. **認證資訊保護**：
   - 不要將 `config.py` 提交到版本控制
   - 考慮使用環境變數儲存敏感資訊
   - 定期更新 API Token

2. **網路安全**：
   - 確認 HTTPS 連線
   - 檢查 VPN 和防火牆設定
   - 避免在公共網路使用

3. **檔案權限**：
   - 確保輸出目錄有寫入權限
   - 檢查檔案是否被其他程式占用

## 📞 技術支援

### 回報問題時請提供

1. **🖼️ 錯誤訊息截圖**
2. **📄 輸入檔案範例** (去敏感化)
3. **📋 系統執行日誌**
4. **⚙️ 網路和權限設定資訊**
5. **💻 作業系統和 Python 版本**

### 日誌位置

系統會在終端機輸出詳細日誌，包含：
- 📈 處理進度資訊
- ❌ 錯誤訊息詳情  
- 🔗 API 呼叫狀態
- 📁 檔案操作結果

## 📝 更新記錄

### v2.0 (最新)
- ✅ 完全重寫功能三：支援 Gerrit 自動下載和智能轉換
- ✅ 修復 Gerrit 下載問題：使用 API 風格 URL
- ✅ 增強功能二：支援 Tag 類型檢查和彩色格式化
- ✅ 改進差異分析：逐行比較和詳細報告
- ✅ 優化 Excel 格式：彩色標示和自動調整

### v1.0
- ✅ 模組化架構設計
- ✅ 互動式操作介面
- ✅ 完整的錯誤處理
- ✅ 自動化 Excel 報告
- ✅ JIRA/Gerrit API 整合

## 🎯 開發原則

- **🧩 模組化**：功能獨立，便於維護
- **🤖 自動化**：減少手動操作，提高效率  
- **👥 使用者友善**：直觀的介面和詳細的說明
- **🔒 穩定可靠**：完整的錯誤處理和診斷功能
- **📊 詳細報告**：提供完整的處理結果和分析

---

**版本**：2.0  
**更新日期**：2024/12  
**維護者**：系統開發團隊

**🚀 立即開始**：執行 `python start.py` 開始使用系統！