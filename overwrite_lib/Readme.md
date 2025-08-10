# JIRA/Gerrit 整合工具系統

## 📖 系統概述

本系統是一個模組化的 JIRA/Gerrit 整合工具，提供三大主要功能：

1. **功能一**：擴充晶片映射表 - 將 `all_chip_mapping_table.xlsx` 擴充並下載相關 JIRA 檔案
2. **功能二**：建立分支映射表 - 透過 manifest.xml 建立分支對應表並可選擇性建立分支
3. **功能三**：去除版本號 - 從 manifest.xml 去除版本資訊產生新的 manifest 檔案

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
- `JIRA_SITE`: jira.realtek.com
- `JIRA_USER`: vince_lin
- `JIRA_PASSWORD`: 
- `JIRA_TOKEN`: xxxxx

**Gerrit 設定：**
- `GERRIT_BASE`: https://mm2sd.rtkbf.com/
- `GERRIT_API_PREFIX`: /a
- `GERRIT_USER`: vince_lin
- `GERRIT_PW`: xxxx

如需修改設定，請編輯 `config.py` 檔案中的對應變數。

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

### 🔍 功能一：擴充晶片映射表

**目的**：將輸入的 `all_chip_mapping_table.xlsx` 擴充成 `all_chip_mapping_table_ext.xlsx`

**輸入**：
- `-i`: 輸入檔案 `all_chip_mapping_table.xlsx`
- `-o`: 輸出資料夾

**處理流程**：
1. 讀取 Excel 中的 `DB_Info`, `premp_DB_Info`, `mp_DB_Info`, `mpbackup_DB_Info` 欄位
2. 將 DB 資訊轉換成 JIRA 連結 (例：DB2302 → https://jira.realtek.com/browse/MMQCDB-2302)
3. 從 JIRA 描述中提取 `repo init` 指令和 manifest 資訊
4. 下載相關的 manifest 檔案到本地
5. 檢查檔案可用性（Gerrit 和本地）

**輸出**：
- 主要資料：擴充後的完整資料表
- 缺少_manifest：記錄無法取得的 manifest 檔案
- 共用：記錄可共用的 Source 來源

### 🌿 功能二：建立分支映射表

**目的**：透過 manifest.xml 建立分支對應表並可選擇性建立分支

**輸入參數**：
- `-i`: 輸入 manifest.xml 檔案
- `-type`: 轉換類型
  - `master_vs_premp`: master → premp
  - `premp_vs_mp`: premp → mp  
  - `mp_vs_mpbackup`: mp → mpbackup
- `-o`: 輸出檔案名稱
- `-r`: 是否去除重複資料 (true/false)
- `-cb`: 是否建立分支 (true/false)

**處理流程**：
1. 解析 manifest.xml 中的所有 project
2. 根據 `-type` 參數轉換分支名稱
3. 可選擇去除重複資料
4. 可選擇透過 Gerrit API 建立實際分支

**輸出**：
- 專案列表：包含轉換後的分支資訊
- 重覆：如有啟用去重功能，記錄重複的項目
- Branch 建立狀態：如有啟用建立分支，記錄建立結果

### 📄 功能三：去除版本號產生新 manifest

**目的**：從 manifest.xml 去除版本號相關資訊，產生乾淨的 manifest 檔案

**輸入參數**：
- `-i`: 輸入 manifest.xml 檔案或資料夾
- `-o`: 輸出資料夾
- `-type`: 處理類型 (master, premp, mp, mpbackup)
- `-f`: 自定義 Excel 檔名 (可選)

**處理流程**：
1. 解析 manifest.xml
2. 移除 `dest-branch`, `revision`, `upstream` 屬性
3. 根據 `-type` 決定輸出檔名
4. 與 Gerrit 上對應檔案進行比較

**輸出檔名對應**：
- `master` → `atv-google-refplus.xml`
- `premp` → `atv-google-refplus-premp.xml`
- `mp` → `atv-google-refplus-wave.xml`
- `mpbackup` → `atv-google-refplus-wave-backup.xml`

**輸出**：
- 產生結果：記錄檔案處理狀態
- 比較結果：與 Gerrit 檔案的比較結果

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

### 操作步驟

1. **選擇功能**：輸入對應數字選擇功能
2. **輸入參數**：依照提示輸入必要參數
3. **確認執行**：檢查參數無誤後確認執行
4. **查看結果**：執行完成後查看輸出檔案

### 快速存取

可直接輸入功能編號快速存取：
- `1-1` 或 `11`：直接執行功能一
- `2-1` 或 `21`：直接執行功能二  
- `3-1` 或 `31`：直接執行功能三

## 🔧 系統工具

### 連線測試

**JIRA 連線測試**：
- 測試與 JIRA 伺服器的連線狀態
- 驗證帳號權限
- 測試 API 存取功能

**Gerrit 連線測試**：
- 測試與 Gerrit 伺服器的連線狀態
- 驗證 API 存取權限
- 查詢測試專案的分支資訊

### 系統設定

- 檢視目前設定值
- 修改 JIRA/Gerrit 連線參數
- 重設為預設值

## 📁 輸出檔案說明

### Excel 檔案格式

所有輸出的 Excel 檔案都包含：
- 美化的標題列格式（藍色背景、白色字體）
- 自動調整的欄寬
- 多個工作表（依功能需求）

### 下載檔案組織

功能一會在輸出資料夾建立以下結構：
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

## ⚠️ 注意事項

1. **網路連線**：系統需要存取 JIRA 和 Gerrit 伺服器
2. **權限要求**：需要對應的帳號權限才能存取 API
3. **檔案路徑**：輸入檔案路徑必須存在且可讀取
4. **輸出覆蓋**：輸出檔案若已存在會被覆蓋

## 🐛 故障排除

### 常見問題

**1. 連線失敗**
- 檢查網路連線
- 確認帳號密碼正確
- 檢查伺服器是否可存取

**2. 檔案讀取失敗**
- 確認檔案路徑正確
- 檢查檔案是否被其他程式占用
- 確認有足夠的檔案讀取權限

**3. API 存取錯誤**
- 檢查帳號權限
- 確認 API Token 有效性
- 檢查伺服器 API 狀態

### 日誌資訊

系統會輸出詳細的執行日誌，包含：
- 處理進度資訊
- 錯誤訊息詳情
- API 呼叫狀態
- 檔案操作結果

## 📞 技術支援

如遇到問題，請提供：
1. 錯誤訊息截圖
2. 輸入檔案範例
3. 系統執行日誌
4. 網路和權限設定資訊

---

**版本**：1.0  
**更新日期**：2024/12  
**維護者**：系統開發團隊