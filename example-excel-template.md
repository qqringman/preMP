# 範例 Excel 模板

## 功能一的輸入 Excel 格式範例

建立一個 Excel 檔案（例如：`ftp_paths.xlsx`），內容如下：

| SN | 模組 | ftp path | 備註 |
|----|------|----------|------|
| 1 | bootcode | /DailyBuild/PrebuildFW/bootcode/RDDB-320_realtek_mac8q_master/20250728_1111_5330ddb | 主要版本 |
| 2 | emcu | /DailyBuild/PrebuildFW/emcu/RDDB-321_realtek_mac8q_master/20250728_2222_5330ddb | 測試版本 |
| 3 | dolby_ta | /DailyBuild/PrebuildFW/dolby_ta/RDDB-1031_merlin7_3.16_android14_mp.google-refplus.backup/2025_07_03-10_53_618e9e1 | Wave backup 版本 |
| 4 | ufsd_ko | /DailyBuild/PrebuildFW/ufsd_ko/RDDB-508_merlin7_android11_mp.google-refplus.wave/2025_07_03-10_53_618e9e1 | Wave 版本 |
| 5 | bootcode | /DailyBuild/PrebuildFW/bootcode/RDDB-320_realtek_mac8q_premp.google-refplus/20250729_3333_4440eec | PreMP 版本 |
| 6 | Merlin7 | /DailyBuild/Merlin7/DB2302_Merlin7_32Bit_FW_Android14_Ref_Plus_GoogleGMS/533_all_202507282300 | 特殊格式 |

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
3. 檢查本地是否已存在檔案，如果存在則跳過下載
4. 在 FTP 路徑及其子目錄中搜尋目標檔案（F_Version.txt, manifest.xml, Version.txt）
5. 下載找到的檔案到對應的本地目錄
6. 產生下載報表

**注意**：
- 如果檔案不在 FTP 路徑的根目錄，系統會自動搜尋子目錄（最多 3 層）
- 如果本地已存在檔案，系統會跳過下載（可在 config.py 中設定 SKIP_EXISTING_FILES = False 來強制重新下載）
- 可以多次執行下載命令，系統只會下載缺少的檔案

執行後的目錄結構：
```
downloads/
├── bootcode/
│   ├── RDDB-320/
│   │   ├── F_Version.txt
│   │   ├── manifest.xml
│   │   └── Version.txt
│   ├── RDDB-320-premp/
│   │   ├── F_Version.txt
│   │   ├── manifest.xml
│   │   └── Version.txt
│   └── RDDB-322-wave/
│       ├── F_Version.txt
│       ├── manifest.xml
│       └── Version.txt
├── emcu/
│   ├── RDDB-321/
│   │   ├── F_Version.txt
│   │   ├── manifest.xml
│   │   └── Version.txt
│   └── RDDB-324-wave.backup/
│       ├── F_Version.txt
│       ├── manifest.xml
│       └── Version.txt
├── dolby_ta/
│   └── RDDB-1031-wave.backup/
│       ├── F_Version.txt
│       ├── manifest.xml
│       └── Version.txt
├── ufsd_ko/
│   └── RDDB-508-wave/
│       ├── F_Version.txt
│       ├── manifest.xml
│       └── Version.txt
├── Merlin7/
│   └── DB2302/
│       ├── F_Version.txt
│       ├── manifest.xml
│       └── Version.txt
└── ftp_paths_report.xlsx
```

### 步驟 3：比較檔案
```bash
# 使用預設選擇（自動選擇第一個資料夾作為 base）
python main.py compare --source-dir ./downloads

# 指定使用 wave 版本作為基準
python main.py compare --source-dir ./downloads --base-folder wave
```

互動模式範例：
```
--- 比較模組檔案差異 ---
請輸入來源目錄路徑: ./downloads
輸出目錄 (預設: 與來源目錄相同): 

選擇要作為基準(base)的資料夾類型：
1. 預設 (RDDB-XXX)
2. premp (RDDB-XXX-premp)
3. wave (RDDB-XXX-wave)
4. wave.backup (RDDB-XXX-wave.backup)
5. 自動選擇 (使用第一個資料夾)

請選擇 (1-5，預設: 5): 3

比較完成！產生了 4 個比較報表
整合報表已儲存至: ./downloads/all_compare.xlsx
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
  <remote name="rtk" fetch="ssh://git@example.com/" />
  <default revision="master" remote="rtk-prebuilt" />
  
  <!-- 一般專案 -->
  <project clone-depth="16" 
           dest-branch="realtek/android-14/master" 
           groups="trigger_no,aosp_rel_none" 
           name="realtek/mac7p/aalter/audio_prebuilt" 
           path="kernel/fw_rtd2841a/current/audio_fw/2K/aalter" 
           remote="rtk-prebuilt" 
           revision="599b8a397b2e270b93582ff30f0e97b4fc90d551" 
           upstream="realtek/android-14/master"/>
           
  <!-- preMP 專案 -->
  <project name="realtek/mac7p/bootcode"
           path="bootcode/src"
           revision="abc123def456"
           upstream="realtek/android-14/premp"
           dest-branch="realtek/android-14/premp"/>
           
  <!-- Wave 特殊案例 -->
  <project name="realtek/frameworks/base"
           path="frameworks/base"
           revision="xyz789abc123"
           upstream="realtek/wave-14/master"
           dest-branch="realtek/wave-14/master"/>
</manifest>
```

### 比較邏輯說明

1. **revision_diff**：比較所有相同 project（name + path）的 revision 差異
   - 不再排除 wave 項目，所有差異都會顯示
   - 新增 has_wave 欄位標示是否包含 'wave' 關鍵字
   - 顯示縮短的 hash code（前 7 個字元）

2. **branch_error**：根據比較對象動態檢查分支命名規則
   - RDDB-XXX vs RDDB-XXX-premp：檢查 compare 中不包含 'premp' 的項目
   - RDDB-XXX-premp vs RDDB-XXX-wave：檢查 compare 中不包含 'wave' 的項目
   - RDDB-XXX-wave vs RDDB-XXX-wave.backup：檢查 compare 中不包含 'wave.backup' 的項目
   - 系統會自動判斷比較類型並套用對應規則

3. **lost_project**：新增或刪除的專案
   - 狀態為「新增」：只在 compare 檔案中存在
   - 狀態為「刪除」：只在 base 檔案中存在

### 基準選擇邏輯

當選擇不同的基準時，比較方向會改變：

- 選擇 `default`：RDDB-XXX 作為 base，其他版本作為 compare
- 選擇 `wave`：RDDB-XXX-wave 作為 base，其他版本作為 compare
- 選擇 `premp`：RDDB-XXX-premp 作為 base，其他版本作為 compare

這會影響：
- revision 差異的顯示（base_revision vs compare_revision）
- 新增/刪除的判斷（相對於 base 的變化）
- branch_error 的檢查規則（根據 compare 資料夾類型）

## 資料夾命名規則

系統會根據 FTP 路徑中的關鍵字自動為資料夾加上後綴：

| FTP 路徑包含 | 資料夾後綴 | 範例 |
|-------------|-----------|------|
| premp.google-refplus | -premp | RDDB-983-premp |
| mp.google-refplus.wave | -wave | RDDB-983-wave |
| mp.google-refplus.wave.backup | -wave.backup | RDDB-983-wave.backup |
| 無特殊關鍵字 | 無後綴 | RDDB-983 |

## 比較功能說明

### 選擇基準資料夾

比較時可以選擇以哪個資料夾作為基準（base）：

```
模組資料夾結構：
bootcode/
├── RDDB-983/          # 預設版本
├── RDDB-983-premp/    # premp 版本
└── RDDB-983-wave/     # wave 版本

選擇選項：
1. 預設 → 使用 RDDB-983 作為 base
2. premp → 使用 RDDB-983-premp 作為 base
3. wave → 使用 RDDB-983-wave 作為 base
```

### branch_error 檢查規則

系統會根據比較對象自動調整檢查規則：

| Base 資料夾 | Compare 資料夾 | 檢查規則 |
|------------|---------------|----------|
| RDDB-983 | RDDB-983-premp | 檢查 compare 中不符合 premp 命名規則的分支 |
| RDDB-983-premp | RDDB-983-wave | 檢查 compare 中不符合 wave 命名規則的分支 |
| RDDB-983-wave | RDDB-983-wave.backup | 檢查 compare 中不符合 wave.backup 命名規則的分支 |

## 比較報表輸出範例

### all_compare.xlsx

**頁籤 1: revision_diff（包含所有 revision 差異）**

| SN | module | name | path | base_short | base_revision | compare_short | compare_revision | has_wave | base_link | compare_link |
|----|--------|------|------|------------|---------------|---------------|------------------|----------|-----------|--------------|
| 1 | bootcode | realtek/mac7p/bootcode | bootcode/src | abc123d | abc123def456... | def456g | def456ghi789... | N | https://... | https://... |
| 2 | bootcode | realtek/frameworks | frameworks/ | aaa111b | aaa111bbb222... | ccc333d | ccc333ddd444... | Y | https://... | https://... |

註：has_wave 欄位標示該項目是否包含 'wave' 關鍵字

**頁籤 2: branch_error**

| SN | module | name | path | revision_short | revision | upstream | dest-branch | check_keyword | compare_link |
|----|--------|------|------|----------------|----------|----------|-------------|---------------|--------------|
| 1 | emcu | realtek/emcu | emcu/src | abc123d | abc123def456... | realtek/master | realtek/master | premp | https://... |
| 2 | bootcode | realtek/boot | boot/src | def456g | def456ghi789... | realtek/android-14 | realtek/android-14 | wave | https://... |

註：check_keyword 顯示檢查的命名規則類型（premp/wave/wave.backup）

**頁籤 3: lost_project (新增/刪除)**

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
   - 查看日誌了解詳細錯誤資訊

5. **想要重新下載已存在的檔案**
   - 設定 `config.py` 中的 `SKIP_EXISTING_FILES = False`
   - 或手動刪除本地檔案後重新執行

6. **比較結果為空**
   - 檢查兩個 manifest.xml 是否真的有差異
   - 確認檔案格式正確（有效的 XML）
   - 確認選擇的基準資料夾存在

7. **找不到指定的基準資料夾**
   - 檢查模組下是否有符合後綴的資料夾
   - 如果選擇 "wave"，確認有 RDDB-XXX-wave 資料夾
   - 如果都找不到，系統會自動使用第一個資料夾

8. **資料夾命名不符預期**
   - 檢查 FTP 路徑是否包含正確的關鍵字
   - premp.google-refplus → -premp
   - mp.google-refplus.wave → -wave
   - mp.google-refplus.wave.backup → -wave.backup

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