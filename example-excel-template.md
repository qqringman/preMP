# 範例 Excel 模板

## 功能一的輸入 Excel 格式範例

建立一個 Excel 檔案（例如：`ftp_paths.xlsx`），內容如下：

| SN | 模組 | ftp path | 備註 |
|----|------|----------|------|
| 1 | bootcode | /DailyBuild/PrebuildFW/bootcode/RDDB-320_realtek_mac8q_master/20250728_1111_5330ddb | 主要版本 |
| 2 | emcu | /DailyBuild/PrebuildFW/emcu/RDDB-321_realtek_mac8q_master/20250728_2222_5330ddb | 測試版本 |
| 3 | dolby_ta | /DailyBuild/PrebuildFW/dolby_ta/RDDB-1031_merlin7_3.16_android14_mp.google-refplus.backup/2025_07_03-10_53_618e9e1 | Dolby 模組 |
| 4 | ufsd_ko | /DailyBuild/PrebuildFW/ufsd_ko/RDDB-508_merlin7_android11_mp.google-refplus/2025_07_03-10_53_618e9e1 | 檔案系統模組 |

**注意事項：**
- "ftp path" 欄位名稱必須完全相同（注意空格）
- 路徑必須包含模組名稱和 JIRA ID（格式：RDDB-XXX）
- SN 和備註欄位為選用

## 建議的工作流程

### 步驟 1：準備 Excel 檔案
1. 建立包含 FTP 路徑的 Excel 檔案
2. 確保路徑格式正確且包含必要資訊

### 步驟 2：下載檔案
```bash
python main.py download --excel ftp_paths.xlsx
```

系統會：
1. 連接到 SFTP 伺服器
2. 解析每個 FTP 路徑中的模組名稱和 JIRA ID
3. 在 FTP 路徑及其子目錄中搜尋目標檔案（F_Version.txt, manifest.xml, Version.txt）
4. 下載找到的檔案到對應的本地目錄
5. 產生下載報表

**注意**：如果檔案不在 FTP 路徑的根目錄，系統會自動搜尋子目錄（最多 3 層）。例如：
- 路徑：`/DailyBuild/PrebuildFW/emcu/RDDB-1193_merlin8_android-14_premp.google-refplus/`
- 檔案可能在：`/DailyBuild/PrebuildFW/emcu/RDDB-1193_merlin8_android-14_premp.google-refplus/2025_06_24-17_41_e54f7a5/F_Version.txt`

執行後的目錄結構：
```
downloads/
├── bootcode/
│   └── RDDB-320/
│       ├── F_Version.txt
│       ├── manifest.xml
│       └── Version.txt
├── emcu/
│   └── RDDB-321/
│       ├── F_Version.txt
│       ├── manifest.xml
│       └── Version.txt
├── dolby_ta/
│   └── RDDB-1031/
│       ├── F_Version.txt
│       ├── manifest.xml
│       └── Version.txt
├── ufsd_ko/
│   └── RDDB-508/
│       ├── F_Version.txt
│       ├── manifest.xml
│       └── Version.txt
└── ftp_paths_report.xlsx
```

### 步驟 3：比較檔案
```bash
python main.py compare --source-dir ./downloads
```

產生的比較報表：
- `downloads/bootcode/bootcode_compare.xlsx`
- `downloads/emcu/emcu_compare.xlsx`
- `downloads/all_compare.xlsx`

### 步驟 4：打包結果
```bash
python main.py package --source-dir ./downloads
```

## manifest.xml 範例結構

```xml
<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <remote name="rtk-prebuilt" fetch="ssh://git@example.com/prebuilt/" />
  <default revision="master" remote="rtk-prebuilt" />
  
  <project clone-depth="16" 
           dest-branch="realtek/android-14/master" 
           groups="trigger_no,aosp_rel_none" 
           name="realtek/mac7p/aalter/audio_prebuilt" 
           path="kernel/fw_rtd2841a/current/audio_fw/2K/aalter" 
           remote="rtk-prebuilt" 
           revision="599b8a397b2e270b93582ff30f0e97b4fc90d551" 
           upstream="realtek/android-14/master"/>
           
  <project name="realtek/mac7p/bootcode"
           path="bootcode/src"
           revision="abc123def456"
           upstream="realtek/android-14/master"
           dest-branch="realtek/android-14/master"/>
</manifest>
```

## 比較報表輸出範例

### bootcode_compare.xlsx

**頁籤 1: 不同的專案**

| SN | module | name | path | upstream | dest-branch | revision |
|----|--------|------|------|----------|-------------|----------|
| 1 | bootcode | realtek/mac7p/bootcode | bootcode/src | realtek/android-14/master | realtek/android-14/master | abc123def456 |

**頁籤 2: 新增刪除項目**

| SN | 狀態 | module | name | path | upstream | dest-branch | revision |
|----|------|--------|------|------|----------|-------------|----------|
| 1 | 新增 | bootcode | realtek/mac7p/new_module | new/path | realtek/android-14/master | realtek/android-14/master | new123rev456 |
| 2 | 刪除 | bootcode | realtek/mac7p/old_module | old/path | realtek/android-13/master | realtek/android-13/master | old789rev012 |

## 故障排除

### 常見問題

1. **SFTP 連線失敗**
   - 檢查網路連線
   - 確認 SFTP 伺服器位址和連接埠正確
   - 驗證使用者名稱和密碼

2. **找不到檔案**
   - 確認 FTP 路徑正確
   - 檢查檔案名稱（系統不區分大小寫）
   - 確認有讀取權限
   - 檢查檔案是否在子目錄中（系統會自動搜尋最多 3 層子目錄）
   - 如需搜尋更深層的目錄，可調整 `config.py` 中的 `MAX_SEARCH_DEPTH`

3. **Excel 讀取錯誤**
   - 確認 Excel 檔案格式正確（.xlsx）
   - 檢查欄位名稱是否完全相符
   - 確保沒有合併的儲存格

4. **比較功能無法執行**
   - 確認每個模組下至少有兩個資料夾
   - 檢查資料夾中是否包含必要的檔案

### 遞迴搜尋功能說明

系統會智能地搜尋目標檔案：

1. **首先**在 FTP 路徑根目錄尋找
2. **如果找不到**，會自動搜尋子目錄（預設最多 3 層）
3. **顯示結果**時會標註檔案的實際位置

例如，對於路徑：
```
/DailyBuild/PrebuildFW/emcu/RDDB-1193_merlin8_android-14_premp.google-refplus/
```

系統可能會在以下位置找到檔案：
```
根目錄/
├── 2025_06_24-17_41_e54f7a5/
│   ├── F_Version.txt     ← 系統會自動找到這裡的檔案
│   ├── manifest.xml      ← 並下載到本地對應目錄
│   └── Version.txt       ← 報表會顯示檔案的相對路徑
└── 其他資料夾/
```

### 日誌檢查

系統會輸出詳細的日誌資訊，可透過設定 `config.py` 中的 `LOG_LEVEL` 來調整詳細程度：
- `DEBUG`: 最詳細的資訊
- `INFO`: 一般操作資訊（預設）
- `WARNING`: 警告資訊
- `ERROR`: 錯誤資訊