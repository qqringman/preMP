# Gen Mapping Excel 操作說明

## 系統概述

Gen Mapping Excel 是一個用於產生映射 Excel 檔案的系統，包含兩大功能：
1. **功能1**: 處理晶片映射表 (chip-mapping)
2. **功能2**: 處理 Prebuild 映射 (prebuild-mapping)

## 安裝需求

### Python 套件
```bash
pip install pandas openpyxl paramiko
```

### 必要檔案
- `config.py`: 系統設定檔
- `all_chip_mapping_table.xlsx`: 晶片映射表（功能1使用）
- Prebuild 來源檔案（功能2使用）
  - `master_prebuild_source.xlsx`
  - `premp_prebuild_source.xlsx`
  - `mp_prebuild_source.xlsx`
  - `mpbackup_prebuild_source.xlsx`

## 功能1: 晶片映射表處理

### 基本用法
```bash
python cli_interface.py chip-mapping
```

### 完整參數
```bash
python cli_interface.py chip-mapping \
    -i all_chip_mapping_table.xlsx \
    -db DB2302#196,DB2686#168 \
    -filter master_vs_premp \
    -o ./output
```

### 參數說明

| 參數 | 說明 | 預設值 | 範例 |
|------|------|--------|------|
| `-i` | 輸入的映射表檔案 | all_chip_mapping_table.xlsx | `-i mapping.xlsx` |
| `-db` | 指定 DB 版本 | all (最新版本) | `-db DB2302#196` |
| `-filter` | 過濾條件 | all | `-filter master_vs_premp` |
| `-o` | 輸出目錄 | ./output | `-o ./results` |

### Filter 參數選項
- `all`: 產生所有比對組合
- `master_vs_premp`: 只比對 master 和 premp
- `premp_vs_mp`: 只比對 premp 和 mp
- `mp_vs_mpbackup`: 只比對 mp 和 mpbackup
- `mac7p`: 只處理 Mac7p 模組
- `mac8p`: 只處理 Mac8p 模組
- `merlin7`: 只處理 Merlin7 模組
- `merlin8`: 只處理 Merlin8 模組
- 可組合使用: `mac7p,merlin7`

### DB 參數格式
- 單一指定: `-db DB2302#196`
- 多個指定: `-db DB2302#196,DB2686#168`
- `#` 前為 DB 編號，後為版本號前綴

### 輸出檔案
預設輸出檔名: `DailyBuild_mapping.xlsx`

輸出欄位：
- SN: 序號
- RootFolder: 根目錄 (DailyBuild)
- Module: 模組名稱
- DB_Type: DB 類型
- DB_Info: DB 資訊
- DB_Folder: DB 資料夾
- DB_Version: DB 版本
- SftpPath: SFTP 完整路徑
- compare_DB_Type: 比較 DB 類型
- compare_DB_Info: 比較 DB 資訊
- compare_DB_Folder: 比較 DB 資料夾
- compare_DB_Version: 比較 DB 版本
- compare_SftpPath: 比較 SFTP 完整路徑

## 功能2: Prebuild 映射處理

### 基本用法
```bash
python cli_interface.py prebuild-mapping \
    -i master_prebuild_source.xlsx,premp_prebuild_source.xlsx
```

### 完整參數
```bash
python cli_interface.py prebuild-mapping \
    -i master_prebuild_source.xlsx,premp_prebuild_source.xlsx \
    -type master_vs_premp \
    -o ./output
```

### 參數說明

| 參數 | 說明 | 預設值 | 範例 |
|------|------|--------|------|
| `-i` | 輸入檔案（2個） | 必要參數 | `-i file1.xlsx,file2.xlsx` |
| `-type` | 比較類型 | master_vs_premp | `-type premp_vs_mp` |
| `-o` | 輸出目錄 | ./output | `-o ./results` |

### Type 參數選項
- `master_vs_premp`: Master 對 Pre-MP 比較
- `premp_vs_mp`: Pre-MP 對 MP 比較
- `mp_vs_mpbackup`: MP 對 MP Backup 比較

### Inner Join 邏輯
系統使用以下四個欄位作為 key 進行 inner join：
1. Category
2. Project
3. LocalPath
4. Master_JIRA

只有當兩個檔案中的這四個欄位完全相符時，才會產生映射關係。

### 輸出檔案
根據 type 參數命名：
- `PrebuildFW_master_vs_premp_mapping.xlsx`
- `PrebuildFW_premp_vs_mp_mapping.xlsx`
- `PrebuildFW_mp_vs_mpbackup_mapping.xlsx`

預設名稱（未指定 type）：`PrebuildFW_mapping.xlsx`

## 測試功能

### 測試 SFTP 連線
```bash
python cli_interface.py test
```

測試結果：
- ✓ SFTP 連線成功
- ✗ SFTP 連線失敗

## 使用範例

### 範例1: 處理所有晶片映射，使用最新版本
```bash
python cli_interface.py chip-mapping
```

### 範例2: 只處理 Mac7p 的 master vs premp 比較
```bash
python cli_interface.py chip-mapping \
    -filter mac7p \
    -filter master_vs_premp
```

### 範例3: 指定特定 DB 版本
```bash
python cli_interface.py chip-mapping \
    -db DB2302#196,DB2686#168 \
    -filter master_vs_premp
```

### 範例4: 處理多個模組
```bash
python cli_interface.py chip-mapping \
    -filter mac7p,merlin7
```

### 範例5: 處理 Prebuild 映射（master vs premp）
```bash
python cli_interface.py prebuild-mapping \
    -i master_prebuild_source.xlsx,premp_prebuild_source.xlsx \
    -type master_vs_premp \
    -o ./prebuild_output
```

### 範例6: 處理 Prebuild 映射（premp vs mp）
```bash
python cli_interface.py prebuild-mapping \
    -i premp_prebuild_source.xlsx,mp_prebuild_source.xlsx \
    -type premp_vs_mp
```

## SFTP 版本邏輯

### 功能1 版本處理
1. **預設行為**：從 SFTP 伺服器抓取最新版本
   - 連線到 SFTP 路徑
   - 列出所有版本資料夾
   - 排序後選擇最新版本

2. **指定版本**：透過 `-db` 參數指定
   - 格式：`DB編號#版本前綴`
   - 範例：`DB2302#196` 會尋找 `196_*` 開頭的版本

### 功能2 版本處理
- 從 SftpURL 欄位直接解析版本資訊
- 路徑範例：`/DailyBuild/PrebuildFW/dolby_ta/RDDB-1000_xxx/20250804_1313_e05abe4`
- 自動提取模組、RDDB 編號、版本等資訊

## 注意事項

### 1. SFTP 連線
- 確保 `config.py` 中的 SFTP 設定正確
- 連線資訊包含：主機、埠號、使用者名稱、密碼
- 使用 `test` 命令驗證連線

### 2. 檔案格式要求

#### all_chip_mapping_table.xlsx 格式
必要欄位：
- SN: 序號
- Module: 模組名稱
- DB_Type, DB_Info, DB_Folder, SftpPath: Master 資訊
- premp_DB_Type, premp_DB_Info, premp_DB_Folder, premp_SftpPath: Pre-MP 資訊
- mp_DB_Type, mp_DB_Info, mp_DB_Folder, mp_SftpPath: MP 資訊
- mpbackup_DB_Type, mpbackup_DB_Info, mpbackup_DB_Folder, mpbackup_SftpPath: MP Backup 資訊

#### Prebuild Source Excel 格式
必要欄位：
- ModuleOwner: 模組擁有者
- Remote: 遠端資訊
- Category: 類別（Join Key 1）
- Project: 專案（Join Key 2）
- Branch: 分支
- LocalPath: 本地路徑（Join Key 3）
- Revision: 版本
- Master_JIRA: JIRA 編號（Join Key 4）
- PrebuildSRC: Prebuild 來源
- SftpURL: SFTP 網址
- Comment: 註解

### 3. 路徑替換
系統會自動進行以下路徑替換：
- `/mnt/cq488` → `/DailyBuild`

### 4. 版本排序
- 預設按版本號降序排列（最新優先）
- 可在 `config.py` 中調整 `VERSION_SORT_REVERSE` 設定

### 5. 輸出目錄
- 系統會自動建立輸出目錄（如果不存在）
- 確保有寫入權限

## 錯誤處理

### 常見錯誤及解決方法

| 錯誤訊息 | 可能原因 | 解決方法 |
|---------|---------|---------|
| 找不到輸入檔案 | 檔案路徑錯誤 | 檢查檔案是否存在，路徑是否正確 |
| SFTP 連線失敗 | 網路或認證問題 | 檢查網路連線，確認 SFTP 設定 |
| 無法列出目錄 | SFTP 路徑不存在 | 確認 SFTP 路徑正確 |
| 找不到版本資料夾 | 路徑下無版本資料 | 檢查 SFTP 路徑是否包含版本資料夾 |
| Inner Join 無結果 | Key 欄位不匹配 | 檢查兩個檔案的 key 欄位值 |

### 日誌檔案
- 系統會產生詳細的日誌訊息
- 日誌等級可在 `config.py` 中設定
- 預設等級：INFO

## 設定檔說明 (config.py)

### 主要設定項目

```python
# SFTP 連線設定
SFTP_HOST = 'mmsftpx.realtek.com'
SFTP_PORT = 22
SFTP_USERNAME = 'lgwar_user'
SFTP_PASSWORD = 'Ab!123456'

# 檔案設定
ALL_CHIP_MAPPING_TABLE = 'all_chip_mapping_table.xlsx'
DEFAULT_DAILYBUILD_OUTPUT = 'DailyBuild_mapping.xlsx'
DEFAULT_PREBUILD_OUTPUT = 'PrebuildFW_mapping.xlsx'

# 路徑替換規則
PATH_REPLACEMENTS = {
    '/mnt/cq488': '/DailyBuild'
}

# 版本排序設定
VERSION_SORT_REVERSE = True  # True = 最新版本優先
```

## 系統架構

### 模組說明
1. **data_models.py**: 資料模型定義
2. **sftp_manager.py**: SFTP 連線管理
3. **feature1_processor.py**: 功能1處理邏輯
4. **feature2_processor.py**: 功能2處理邏輯
5. **gen_mapping_excel.py**: 主程式類別
6. **cli_interface.py**: 命令列介面
7. **config.py**: 系統設定
8. **utils.py**: 工具函數

### 資料流程
1. 讀取輸入檔案（Excel）
2. 解析並驗證資料
3. 連線 SFTP（如需要）
4. 取得版本資訊
5. 產生映射關係
6. 輸出結果檔案

## 更新歷程

### v1.0.0 (初始版本)
- 實作功能1：晶片映射表處理
- 實作功能2：Prebuild 映射處理
- 支援命令列操作
- SFTP 自動版本擷取
- 模組化架構設計

## 聯絡資訊

如有問題或建議，請聯絡系統管理員。

---
文件更新日期：2024