# JIRA/Gerrit 整合工具系統

## 📖 系統概述

本系統是一個模組化的 JIRA/Gerrit 整合工具，提供三大主要功能模組：

1. **功能一（feature_one.py）**：擴充晶片映射表 - 將 `all_chip_mapping_table.xlsx` 擴充並下載相關 JIRA 檔案
2. **功能二（feature_two.py）**：建立分支映射表 - 透過 manifest.xml 建立分支對應表並可選擇性建立分支
3. **功能三（feature_three.py）**：去除版本號 - 從 manifest.xml 去除版本資訊產生新的 manifest 檔案

## 🎯 系統特色

- **🧩 模組化設計**：功能獨立運作，便於維護和擴展
- **🖥️ 互動式介面**：友善的選單系統，支援多種操作方式
- **📊 Excel 整合**：自動產生格式化的 Excel 報告
- **🔄 自動化處理**：批次處理大量資料，提高工作效率
- **🔗 API 整合**：整合 JIRA 和 Gerrit API，自動化資料擷取
- **📋 詳細報告**：提供完整的處理結果和比較分析

## 🗂️ 檔案結構

```
project/
├── config.py              # 系統設定檔 (包含 JIRA/Gerrit 環境變數)
├── excel_handler.py       # Excel 處理模組 (請勿修改)
├── start.py               # 系統啟動腳本 (含環境檢查)
├── start.bat              # Windows 批次啟動檔
└── overwrite_lib/         # 主要程式模組目錄
    ├── main.py            # 主程式互動式介面
    ├── utils.py           # 通用工具模組
    ├── jira_manager.py    # JIRA API 管理模組
    ├── gerrit_manager.py  # Gerrit API 管理模組
    ├── feature_one.py     # 功能一：擴充晶片映射表
    ├── feature_two.py     # 功能二：建立分支映射表
    ├── feature_three.py   # 功能三：去除版本號
    ├── requirements.txt   # Python 套件依賴
    └── README.md         # 本文件
```

## 🚀 快速開始

### 1. 環境準備

確保已安裝 Python 3.7 或更高版本，然後安裝依賴套件：

```bash
pip install -r overwrite_lib/requirements.txt
```

### 2. 系統設定

所有 JIRA/Gerrit 環境變數已統一在 `config.py` 中管理：

**JIRA 設定：**
```python
JIRA_SITE = 'jira.realtek.com'
JIRA_USER = 'your_username'
JIRA_PASSWORD = 'your_password'
JIRA_TOKEN = 'your_token'  # 可選，優先使用
```

**Gerrit 設定：**
```python
GERRIT_BASE = 'https://mm2sd.rtkbf.com/'
GERRIT_API_PREFIX = '/a'
GERRIT_USER = 'your_username'
GERRIT_PW = 'your_password'
```

### 3. 啟動系統

**方法一 (推薦)：使用啟動腳本**
```bash
python start.py
```

**方法二：Windows 用戶**
```
雙擊 start.bat
```

**方法三：直接啟動**
```bash
cd overwrite_lib
python main.py
```

## 📋 功能詳細說明

### 🔍 功能一：擴充晶片映射表 (feature_one.py)

#### 功能概述
將輸入的 `all_chip_mapping_table.xlsx` 擴充成 `all_chip_mapping_table_ext.xlsx`，並自動下載相關的 JIRA 檔案和 manifest 檔案。

#### 輸入參數
- **輸入檔案** (`-i`): `all_chip_mapping_table.xlsx` 檔案路徑
- **輸出資料夾** (`-o`): 輸出結果的資料夾路徑

#### 處理流程
1. **讀取 Excel**：解析 `DB_Info`, `premp_DB_Info`, `mp_DB_Info`, `mpbackup_DB_Info` 欄位
2. **JIRA 整合**：將 DB 資訊轉換成 JIRA 連結 (例：DB2302 → https://jira.realtek.com/browse/MMQCDB-2302)
3. **資料擷取**：從 JIRA 描述中提取 `repo init` 指令和 manifest 資訊
4. **檔案下載**：自動下載 manifest 檔案到本地資料夾
5. **可用性檢查**：檢查檔案在 Gerrit 和本地的可用性

#### 輸出結果

**主要輸出檔案：** `all_chip_mapping_table_ext.xlsx`

**Excel 頁籤結構：**
- **主要資料**：擴充後的完整資料表，包含原始欄位和新增欄位：
  - `Jira`: JIRA 連結
  - `Source`: repo init 指令
  - `Source_manifest`: manifest 檔案名稱
  - `Source_link`: Gerrit 檔案連結
  - 對應的 premp、mp、mpbackup 版本欄位

- **缺少_manifest**：記錄無法取得的 manifest 檔案
  - `SN`: 序號
  - `Module`: 模組名稱
  - `DB_Type`: DB 類型 (master/premp/mp/mpbackup)
  - `DB Info`: DB 資訊
  - `DB_Info_Jira`: JIRA 連結
  - `Source`: repo init 指令
  - `Source_manifest`: manifest 檔案名稱
  - `Source_link`: Gerrit 檔案連結

- **共用**：記錄可共用的 Source 來源
  - `SN`: 序號
  - `DB Info`: 共用的 DB 清單 (格式：DB2302(Merlin7, master),DB2857(Merlin8, premp))
  - `Source`: repo init 指令
  - `Source_manifest`: manifest 檔案名稱
  - `Source_link`: Gerrit 檔案連結

**檔案下載結構：**
```
output_folder/
├── all_chip_mapping_table_ext.xlsx
├── DB2302/
│   ├── atv-google-refplus.xml
│   └── ReadMe.txt
├── DB2857/
│   ├── another-manifest.xml
│   └── ReadMe.txt
└── ...
```

#### 使用範例

**互動式使用：**
1. 執行 `python main.py`
2. 選擇 `[1] 晶片映射表處理`
3. 選擇 `[1] 擴充晶片映射表 (功能一)`
4. 依照提示輸入檔案路徑和輸出資料夾

**直接呼叫：**
```python
from feature_one import FeatureOne

feature_one = FeatureOne()
success = feature_one.process(
    input_file="path/to/all_chip_mapping_table.xlsx",
    output_folder="./output"
)
```

---

### 🌿 功能二：建立分支映射表 (feature_two.py)

#### 功能概述
透過 manifest.xml 建立分支對應表，支援不同類型的分支轉換，並可選擇性建立實際的 Gerrit 分支。

#### 輸入參數
- **輸入檔案** (`-i`): manifest.xml 檔案路徑
- **處理類型** (`-type`): 轉換類型
  - `master_vs_premp`: master → premp
  - `premp_vs_mp`: premp → mp  
  - `mp_vs_mpbackup`: mp → mpbackup
- **輸出檔案** (`-o`): 輸出 Excel 檔案名稱
- **輸出資料夾**: 輸出資料夾路徑 (可選)
- **去除重複** (`-r`): 是否去除重複資料 (true/false)
- **建立分支** (`-cb`): 是否透過 Gerrit API 建立分支 (true/false)
- **檢查分支存在性**: 是否檢查目標分支是否已存在 (會比較慢)

#### 處理流程
1. **解析 Manifest**：讀取 manifest.xml 中的所有 project 元素
2. **分支轉換**：根據處理類型轉換分支名稱
   - 判斷來源分支類型 (master/premp/mp/mpbackup)
   - 套用對應的轉換規則
3. **分支檢查**：查詢目標分支是否已存在 (可選)
4. **去重處理**：移除重複的專案 (可選)
5. **分支建立**：透過 Gerrit API 建立實際分支 (可選)

#### 分支轉換規則

**master_vs_premp (master → premp):**
```
realtek/android-14/master → realtek/android-14/premp.google-refplus
```

**premp_vs_mp (premp → mp):**
```
realtek/android-14/premp.google-refplus → realtek/android-14/mp.google-refplus.wave
```

**mp_vs_mpbackup (mp → mpbackup):**
```
realtek/android-14/mp.google-refplus.wave → realtek/android-14/mp.google-refplus.wave.backup
```

#### 輸出結果

**主要輸出檔案：** `manifest_{process_type}.xlsx`

**Excel 頁籤結構：**
- **專案列表**：轉換後的專案清單
  - `SN`: 序號
  - `name`: 專案名稱
  - `revision`: 版本號
  - `upstream`: 上游分支
  - `dest-branch`: 目標分支
  - `target_branch`: 轉換後的目標分支 🆕
  - `target_branch_exists`: 分支是否存在 (Y/N/-) 🆕
  - `target_branch_revision`: 目標分支的 revision 🆕
  - `groups`: 專案群組 (如有)
  - `path`: 專案路徑 (如有)

- **重覆**：重複的專案資料 (如有啟用去重功能)
  - 欄位結構同專案列表

- **Branch 建立狀態**：分支建立結果 (如有啟用建立分支功能)
  - `SN`: 序號
  - `Project`: 專案名稱
  - `Target_Branch`: 目標分支
  - `Revision`: 基於的版本
  - `Status`: 建立狀態 (成功/失敗)
  - `Message`: 詳細訊息
  - `Already_Exists`: 是否已存在

#### 使用範例

**互動式使用：**
1. 執行 `python main.py`
2. 選擇 `[2] 分支管理工具`
3. 選擇 `[1] 建立分支映射表 (功能二)`
4. 依照提示選擇處理類型和相關選項

**直接呼叫：**
```python
from feature_two import FeatureTwo

feature_two = FeatureTwo()
success = feature_two.process(
    input_file="path/to/manifest.xml",
    process_type="master_vs_premp",
    output_file="manifest_premp.xlsx",
    remove_duplicates=True,
    create_branches=False,
    check_branch_exists=True,
    output_folder="./output"
)
```

---

### 📄 功能三：去除版本號產生新 manifest (feature_three.py)

#### 功能概述
從 manifest.xml 去除版本號相關資訊，產生乾淨的 manifest 檔案，並與 Gerrit 上對應檔案進行比較。

#### 輸入參數
- **輸入路徑** (`-i`): manifest.xml 檔案或包含多個 XML 檔案的資料夾
- **輸出資料夾** (`-o`): 輸出結果的資料夾
- **處理類型** (`-type`): 目標類型 (master, premp, mp, mpbackup)
- **Excel 檔名** (`-f`): 自定義 Excel 報告檔名 (可選)

#### 處理流程
1. **檔案掃描**：取得要處理的 manifest.xml 檔案清單
2. **XML 解析**：解析每個 manifest.xml 檔案
3. **屬性移除**：移除所有 project 元素的版本相關屬性：
   - `dest-branch`: 目標分支
   - `revision`: 版本號
   - `upstream`: 上游分支
4. **路徑更新**：根據處理類型更新 path 欄位 (如需要)
5. **檔案產生**：根據處理類型產生對應的檔案名稱
6. **Gerrit 比較**：下載 Gerrit 上對應檔案進行比較

#### 輸出檔名對應
根據處理類型自動決定輸出檔案名稱：

- `master` → `atv-google-refplus.xml`
- `premp` → `atv-google-refplus-premp.xml`
- `mp` → `atv-google-refplus-wave.xml`
- `mpbackup` → `atv-google-refplus-wave-backup.xml`

#### Gerrit 比較 URL
系統會自動與對應的 Gerrit 檔案進行比較：

```
基礎 URL: https://mm2sd.rtkbf.com/gerrit/plugins/gitiles/realtek/android/manifest/+/refs/heads/realtek/android-14/master/

完整比較 URL 範例:
- master: .../atv-google-refplus.xml
- premp: .../atv-google-refplus-premp.xml
- mp: .../atv-google-refplus-wave.xml
- mpbackup: .../atv-google-refplus-wave-backup.xml
```

#### 輸出結果

**產生的檔案：**
- 新的 manifest.xml 檔案 (根據處理類型命名)
- Excel 比較報告

**Excel 報告頁籤：**
- **產生結果**：檔案處理狀態
  - `SN`: 序號
  - `source_filename`: 來源檔案名稱
  - `output_filename`: 輸出檔案名稱
  - `output_file`: 輸出檔案完整路徑
  - `success`: 是否成功
  - `message`: 處理訊息

- **比較結果**：與 Gerrit 檔案的比較
  - `SN`: 序號
  - `source_filename`: 來源檔案名稱
  - `output_filename`: 輸出檔案名稱
  - `output_file`: 輸出檔案路徑
  - `gerrit_link`: Gerrit 檔案連結
  - `comparison_status`: 比較狀態 🎨
    - **相同** (綠色): 檔案內容完全相同
    - **不同** (紅色): 檔案內容有差異
    - **Gerrit檔案無法存取** (黃色): Gerrit 檔案不存在或無權限
    - **比較錯誤** (紅色): 比較過程發生錯誤
  - `comparison_message`: 比較詳細訊息

#### 使用範例

**互動式使用：**
1. 執行 `python main.py`
2. 選擇 `[3] Manifest 處理工具`
3. 選擇 `[1] 去除版本號產生新 manifest (功能三)`
4. 輸入檔案路徑、輸出資料夾和處理類型

**直接呼叫：**
```python
from feature_three import FeatureThree

feature_three = FeatureThree()
success = feature_three.process(
    input_path="path/to/manifest.xml",
    output_folder="./output",
    process_type="mp",
    excel_filename="mp_manifest_report.xlsx"
)
```

**批次處理資料夾：**
```python
# 處理資料夾中的所有 XML 檔案
success = feature_three.process(
    input_path="./manifests/",  # 包含多個 XML 的資料夾
    output_folder="./output",
    process_type="master"
)
```

## 🎛️ 互動式操作指南

### 主選單導覽

系統啟動後會顯示主選單，包含四大功能群組：

```
📋 主要功能群組:

🔍 [1] 晶片映射表處理
    ├─ 1-1. 擴充晶片映射表 (功能一)
    └─ 1-2. 檢視晶片映射表資訊

🌿 [2] 分支管理工具
    ├─ 2-1. 建立分支映射表 (功能二)
    ├─ 2-2. 批次建立分支
    └─ 2-3. 查詢分支狀態

📄 [3] Manifest 處理工具
    ├─ 3-1. 去除版本號產生新 manifest (功能三)
    ├─ 3-2. 比較 manifest 差異
    └─ 3-3. 下載 Gerrit manifest

⚙️ [4] 系統工具
    ├─ 4-1. 測試 JIRA 連線
    ├─ 4-2. 測試 Gerrit 連線
    └─ 4-3. 系統設定
```

### 快速存取

可直接輸入功能編號快速存取：
- `1-1` 或 `11`：直接執行功能一
- `2-1` 或 `21`：直接執行功能二  
- `3-1` 或 `31`：直接執行功能三

### 操作步驟

1. **選擇功能**：輸入對應數字選擇功能
2. **輸入參數**：依照提示輸入必要參數
3. **確認執行**：檢查參數無誤後確認執行
4. **查看結果**：執行完成後查看輸出檔案

## 🔧 系統工具

### 連線測試

**JIRA 連線測試**：
- 測試與 JIRA 伺服器的連線狀態
- 驗證帳號權限和 API Token
- 測試 REST API 存取功能
- 診斷常見連線問題

**Gerrit 連線測試**：
- 測試與 Gerrit 伺服器的連線狀態
- 驗證 API 存取權限
- 測試檔案下載功能
- 查詢測試專案的分支資訊

### 診斷工具

系統提供詳細的診斷功能：
- 檢查設定完整性
- 測試多種認證方式
- 網路連線診斷
- 提供解決方案建議

### 系統設定

- 檢視目前設定值
- 修改 JIRA/Gerrit 連線參數
- 重設為預設值
- 環境變數檢查

## 📁 輸出檔案說明

### Excel 檔案格式

所有輸出的 Excel 檔案都包含：
- 🎨 美化的標題列格式（藍色背景、白色字體）
- 📏 自動調整的欄寬
- 📊 多個工作表（依功能需求）
- 🎯 狀態欄位的顏色標示

### 特殊格式標示

**功能二分支檢查欄位：**
- 標頭：綠色底白字
- 內容：Y (綠色)、N (紅色)、- (黑色)

**功能三比較狀態欄位：**
- 相同：綠色背景
- 不同：紅色背景
- Gerrit檔案無法存取：黃色背景
- 比較錯誤：紅色背景

## ⚠️ 注意事項

1. **網路連線**：系統需要存取 JIRA 和 Gerrit 伺服器
2. **權限要求**：需要對應的帳號權限才能存取 API
3. **檔案路徑**：輸入檔案路徑必須存在且可讀取
4. **輸出覆蓋**：輸出檔案若已存在會被覆蓋
5. **效能考量**：分支存在性檢查會較慢，建議大量資料時謹慎使用

## 🐛 故障排除

### 常見問題

**1. JIRA 連線失敗 (HTTP 403)**
- 檢查帳號密碼正確性
- 確認帳號沒有被鎖定
- 嘗試使用 API Token 替代密碼
- 確認帳號有對應專案的存取權限

**2. Gerrit 認證問題 (HTTP 401)**
- 確認 `config.py` 中的 `GERRIT_USER` 和 `GERRIT_PW`
- 檢查帳號是否為 Gerrit 註冊用戶
- 確認網路連線和 VPN 設定

**3. 檔案處理錯誤**
- 確認檔案格式正確 (Excel/XML)
- 檢查檔案是否被其他程式占用
- 確認有足夠的磁碟空間

**4. XML 解析失敗**
- 檢查 XML 檔案格式是否正確
- 確認檔案編碼為 UTF-8
- 檢查是否有語法錯誤

### 診斷步驟

1. **檢查設定**：執行系統診斷功能
2. **測試連線**：分別測試 JIRA 和 Gerrit 連線
3. **查看日誌**：檢查詳細的錯誤訊息
4. **驗證檔案**：確認輸入檔案格式正確

### 日誌資訊

系統會輸出詳細的執行日誌，包含：
- 📈 處理進度資訊
- ❌ 錯誤訊息詳情
- 🔗 API 呼叫狀態
- 📁 檔案操作結果

## 🔄 更新記錄

### v1.0 特色
- ✅ 模組化架構設計
- ✅ 互動式操作介面
- ✅ 完整的錯誤處理
- ✅ 自動化 Excel 報告
- ✅ JIRA/Gerrit API 整合
- ✅ 分支存在性檢查
- ✅ Gerrit 檔案比較功能
- ✅ 彩色狀態標示

### 改進項目
- 📈 提升 XML 處理效能
- 🔧 增強錯誤診斷功能
- 🎨 改進 Excel 格式化
- 🚀 優化大檔案處理

## 📞 技術支援

如遇到問題，請提供：
1. 🖼️ 錯誤訊息截圖
2. 📄 輸入檔案範例 (去敏感化)
3. 📋 系統執行日誌
4. ⚙️ 網路和權限設定資訊

---

**版本**：1.0  
**更新日期**：2024/12  
**維護者**：系統開發團隊

**🎯 開發原則**：模組化、自動化、使用者友善