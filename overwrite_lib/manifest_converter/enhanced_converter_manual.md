# 增強版 Manifest 轉換工具操作手冊 - 支援 XML 和 TXT

## 工具概述

`enhanced_manifest_converter.py` 是一個增強版的 Android Manifest 轉換工具，**同時支援 XML 和 TXT 檔案**的轉換。該工具可以在不同的 code line 之間轉換 manifest 檔案和版本詳細資訊檔案。

### 主要特色

- ✅ **雙格式支援**: 自動偵測並處理 XML 和 TXT 檔案
- ✅ **智能轉換**: 對 XML 的 revision/upstream/dest-branch 和 TXT 的 Branch 資訊套用相同轉換規則
- ✅ **自動偵測**: 自動識別檔案類型無需手動指定
- ✅ **統一邏輯**: XML 和 TXT 使用相同的分支轉換邏輯
- ✅ **詳細統計**: 提供轉換前後的詳細變更統計

### 支援的轉換類型

1. **Master → PreMP** (`master_to_premp`)
2. **PreMP → MP** (`premp_to_mp`)
3. **MP → MP Backup** (`mp_to_mpbackup`)

### 支援的檔案格式

#### XML 檔案
- Android Manifest 檔案 (如 `atv-google-refplus.xml`)
- 包含 `<project>` 元素的 XML 檔案
- 轉換 `revision`、`upstream`、`dest-branch` 屬性

#### TXT 檔案
- 版本詳細資訊檔案 (如 `Version_Detail_144.txt`)
- 包含 `Branch:` 行的文字檔案
- 轉換 `Branch:` 後的分支資訊

## 環境需求

### Python 版本
- Python 3.6 或以上版本

### 相依套件
```bash
# 標準庫，無需額外安裝
import os
import sys
import argparse
import xml.etree.ElementTree as ET
import re
import logging
```

### 檔案結構
```
project_directory/
├── enhanced_manifest_converter.py    # 增強版轉換工具
├── atv-google-refplus.xml           # XML 輸入檔案
├── Version_Detail_144.txt           # TXT 輸入檔案
├── manifest_xxx_manifest.xml        # XML 轉換結果
├── Version_Detail_144_xxx_converted.txt  # TXT 轉換結果
└── workspace/                       # 工作空間目錄
```

## 使用方法

### 1. 命令列模式

#### 基本語法
```bash
python enhanced_manifest_converter.py [input_file] -t [conversion_type] -o [output_file]
```

#### 參數說明
- `input_file`: 輸入檔案路徑 (XML 或 TXT)
- `-t, --type`: 轉換類型
  - `master_to_premp`: Master → PreMP
  - `premp_to_mp`: PreMP → MP
  - `mp_to_mpbackup`: MP → MP Backup
- `-o, --output`: 輸出檔案路徑 (可選)
- `-i, --interactive`: 啟用互動模式

#### XML 檔案轉換範例

**Master to PreMP 轉換**
```bash
python enhanced_manifest_converter.py atv-google-refplus.xml -t master_to_premp -o manifest_738_master_to_premp_manifest.xml
```

**PreMP to MP 轉換**
```bash
python enhanced_manifest_converter.py atv-google-refplus-premp.xml -t premp_to_mp -o manifest_845_premp_to_mp_manifest.xml
```

**MP to MP Backup 轉換**
```bash
python enhanced_manifest_converter.py atv-google-refplus-wave.xml -t mp_to_mpbackup -o manifest_901_mp_to_mpbackup_manifest.xml
```

#### TXT 檔案轉換範例

**Master to PreMP 轉換**
```bash
python enhanced_manifest_converter.py Version_Detail_144.txt -t master_to_premp -o Version_Detail_144_master_to_premp_converted.txt
```

**PreMP to MP 轉換**
```bash
python enhanced_manifest_converter.py Version_Detail_144.txt -t premp_to_mp -o Version_Detail_144_premp_to_mp_converted.txt
```

**自動生成輸出檔名**
```bash
python enhanced_manifest_converter.py Version_Detail_144.txt -t master_to_premp
# 輸出: Version_Detail_144_master_to_premp_converted.txt
```

### 2. 互動模式

#### 啟動互動模式
```bash
python enhanced_manifest_converter.py -i
```

#### 互動流程
1. 輸入檔案路徑 (XML 或 TXT)
2. 選擇轉換類型 (1-3)
3. 輸入輸出檔案路徑 (可選)
4. 確認並執行轉換

#### 互動模式範例
```bash
$ python enhanced_manifest_converter.py -i
============================================================
🔧 增強版 Manifest 轉換工具 - 互動模式
支援 XML 和 TXT 檔案
============================================================

請輸入檔案路徑 (支援 XML 或 TXT): Version_Detail_144.txt

請選擇轉換類型:
1. Master → PreMP
2. PreMP → MP
3. MP → MP Backup

請選擇 (1-3): 1

請輸入輸出檔案名稱（留空使用預設名稱）: 

開始轉換: Master → PreMP
INFO: 偵測到檔案類型: TXT
INFO: 開始轉換: Master → PreMP
INFO: 輸入檔案: Version_Detail_144.txt
INFO: 輸出檔案: Version_Detail_144_master_to_premp_converted.txt
INFO: TXT 轉換完成！
INFO: 總 Branch 數: 2
INFO: 已轉換: 2
INFO: 未轉換: 0

✅ 轉換成功完成！
```

## TXT 檔案轉換詳解

### TXT 檔案格式

工具支援的 TXT 檔案格式範例：
```
GIT Project: realtek/dailybuild/android_cert_key
Local Path : android_cert_key
commit 65f6661449e8d98805cd8b7d0bf8b83e8483d8d4
Branch: rtk/realtek/android-14/premp.google-refplus
Tag info: submissions/6
Title: [ML7QC-1126][Build][Fix]: Fixed issues with wellknown sign key

GIT Project: realtek/repo_hooks
Local Path : hooks
commit 4ded49603e19bed4a23273987bb44a47e7df3281
Branch: rtk/realtek/android-14/premp.google-refplus
Tag info: submissions/8
```

### TXT 轉換邏輯

1. **自動偵測**: 尋找包含 `Branch:` 的行
2. **前綴處理**: 自動處理 `rtk/` 前綴
3. **轉換應用**: 對分支名稱套用與 XML 相同的轉換規則
4. **前綴還原**: 轉換後重新加上原有前綴

### TXT 轉換範例

#### 輸入檔案 (Version_Detail_144.txt)
```
GIT Project: realtek/dailybuild/android_cert_key
Local Path : android_cert_key
commit 65f6661449e8d98805cd8b7d0bf8b83e8483d8d4
Branch: rtk/realtek/android-14/premp.google-refplus
Tag info: submissions/6
Title: [ML7QC-1126][Build][Fix]: Fixed issues with wellknown sign key

GIT Project: realtek/repo_hooks
Local Path : hooks
commit 4ded49603e19bed4a23273987bb44a47e7df3281
Branch: rtk/realtek/android-14/premp.google-refplus
Tag info: submissions/8
```

#### PreMP to MP 轉換後輸出
```
GIT Project: realtek/dailybuild/android_cert_key
Local Path : android_cert_key
commit 65f6661449e8d98805cd8b7d0bf8b83e8483d8d4
Branch: rtk/realtek/android-14/mp.google-refplus.wave
Tag info: submissions/6
Title: [ML7QC-1126][Build][Fix]: Fixed issues with wellknown sign key

GIT Project: realtek/repo_hooks
Local Path : hooks
commit 4ded49603e19bed4a23273987bb44a47e7df3281
Branch: rtk/realtek/android-14/mp.google-refplus.wave
Tag info: submissions/8
```

#### 轉換統計輸出
```
INFO: TXT 轉換完成！
INFO: 總 Branch 數: 2
INFO: 已轉換: 2
INFO: 未轉換: 0
```

## 轉換規則說明

### 統一轉換邏輯

無論是 XML 還是 TXT 檔案，都使用相同的分支轉換規則：

#### Master to PreMP 轉換
- `realtek/android-14/master` → `realtek/android-14/premp.google-refplus`
- `realtek/android-14/mp.google-refplus` → `realtek/android-14/premp.google-refplus`
- `realtek/linux-5.15/android-14/master` → `realtek/linux-5.15/android-14/premp.google-refplus`

#### PreMP to MP 轉換
- `realtek/android-14/premp.google-refplus` → `realtek/android-14/mp.google-refplus.wave`
- `realtek/linux-5.15/android-14/premp.google-refplus` → `realtek/linux-5.15/android-14/mp.google-refplus.wave`

#### MP to MP Backup 轉換
- `realtek/android-14/mp.google-refplus.wave` → `realtek/android-14/mp.google-refplus.wave.backup`
- `realtek/linux-5.15/android-14/mp.google-refplus.wave` → `realtek/linux-5.15/android-14/mp.google-refplus.wave.backup`

### 特殊處理

#### 前綴保留
TXT 檔案中的 `rtk/` 前綴會被自動保留：
- 輸入: `rtk/realtek/android-14/premp.google-refplus`
- 轉換: `rtk/realtek/android-14/mp.google-refplus.wave`

#### Hash 跳過
XML 檔案中的 commit hash 會被自動跳過，不進行轉換

#### 特殊分支
Google 分支和 refs/tags/ 分支會被自動跳過

## 使用情境與範例

### 情境 1: XML Manifest 轉換並建立工作空間

```bash
# 步驟 1: 轉換 XML manifest
$ python enhanced_manifest_converter.py atv-google-refplus.xml -t master_to_premp -o manifest_738_master_to_premp_manifest.xml

INFO: 偵測到檔案類型: XML
INFO: 開始轉換: Master → PreMP
INFO: 輸入檔案: atv-google-refplus.xml
INFO: 輸出檔案: manifest_738_master_to_premp_manifest.xml
INFO: XML 轉換完成！
INFO: 總專案數: 145
INFO: 有變化的專案: 52
INFO:   - revision 轉換: 28 個
INFO:   - upstream 轉換: 15 個
INFO:   - dest-branch 轉換: 9 個
INFO: 未轉換: 93

============================================================
🎉 轉換完成！以下是使用轉換後檔案的說明：
============================================================

📋 Master to PreMP 轉換完成

[1] mkdir -p manifest_738_master_to_premp_manifest_workspace && cd manifest_738_master_to_premp_manifest_workspace
[2] repo init -u ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -b realtek/android-14/master -m atv-google-refplus-premp.xml
[3] cp -a ../manifest_738_master_to_premp_manifest.xml .repo/manifests/
[4] repo init -m manifest_738_master_to_premp_manifest.xml
[5] repo sync

============================================================
提示：請確保轉換後的檔案 manifest_738_master_to_premp_manifest.xml 在當前目錄中
============================================================

# 步驟 2: 執行建議的指令建立工作空間
$ mkdir -p manifest_738_master_to_premp_manifest_workspace && cd manifest_738_master_to_premp_manifest_workspace
$ repo init -u ssh://mm2sd.rtkbf.com:29418/realtek/android/manifest -b realtek/android-14/master -m atv-google-refplus-premp.xml
$ cp -a ../manifest_738_master_to_premp_manifest.xml .repo/manifests/
$ repo init -m manifest_738_master_to_premp_manifest.xml
$ repo sync
```

### 情境 2: TXT 版本檔案轉換

```bash
# 步驟 1: 準備版本詳細檔案
$ cat Version_Detail_144.txt
GIT Project: realtek/dailybuild/android_cert_key
Local Path : android_cert_key
commit 65f6661449e8d98805cd8b7d0bf8b83e8483d8d4
Branch: rtk/realtek/android-14/premp.google-refplus
Tag info: submissions/6
Title: [ML7QC-1126][Build][Fix]: Fixed issues with wellknown sign key

GIT Project: realtek/repo_hooks
Local Path : hooks
commit 4ded49603e19bed4a23273987bb44a47e7df3281
Branch: rtk/realtek/android-14/premp.google-refplus
Tag info: submissions/8

# 步驟 2: 轉換為 MP 版本
$ python enhanced_manifest_converter.py Version_Detail_144.txt -t premp_to_mp -o Version_Detail_144_premp_to_mp_converted.txt

INFO: 偵測到檔案類型: TXT
INFO: 開始轉換: PreMP → MP
INFO: 輸入檔案: Version_Detail_144.txt
INFO: 輸出檔案: Version_Detail_144_premp_to_mp_converted.txt
INFO: TXT 轉換完成！
INFO: 總 Branch 數: 2
INFO: 已轉換: 2
INFO: 未轉換: 0

============================================================
🎉 轉換完成！以下是使用轉換後檔案的說明：
============================================================

📋 TXT Branch 轉換完成

轉換後的檔案已產生：Version_Detail_144_premp_to_mp_converted.txt

使用方式：
1. 檢查轉換結果是否正確
2. 可以直接使用轉換後的檔案進行後續操作
3. 或根據 Branch 資訊進行相應的 git 操作

檔案差異比較：
diff -u Version_Detail_144.txt Version_Detail_144_premp_to_mp_converted.txt

============================================================
提示：TXT 檔案已完成 Branch 資訊轉換
============================================================

# 步驟 3: 檢查轉換結果
$ cat Version_Detail_144_premp_to_mp_converted.txt
GIT Project: realtek/dailybuild/android_cert_key
Local Path : android_cert_key
commit 65f6661449e8d98805cd8b7d0bf8b83e8483d8d4
Branch: rtk/realtek/android-14/mp.google-refplus.wave
Tag info: submissions/6
Title: [ML7QC-1126][Build][Fix]: Fixed issues with wellknown sign key

GIT Project: realtek/repo_hooks
Local Path : hooks
commit 4ded49603e19bed4a23273987bb44a47e7df3281
Branch: rtk/realtek/android-14/mp.google-refplus.wave
Tag info: submissions/8

# 步驟 4: 比較差異
$ diff -u Version_Detail_144.txt Version_Detail_144_premp_to_mp_converted.txt
--- Version_Detail_144.txt      2024-09-11 14:30:00.000000000 +0800
+++ Version_Detail_144_premp_to_mp_converted.txt        2024-09-11 14:35:00.000000000 +0800
@@ -1,7 +1,7 @@
 GIT Project: realtek/dailybuild/android_cert_key
 Local Path : android_cert_key
 commit 65f6661449e8d98805cd8b7d0bf8b83e8483d8d4
-Branch: rtk/realtek/android-14/premp.google-refplus
+Branch: rtk/realtek/android-14/mp.google-refplus.wave
 Tag info: submissions/6
 Title: [ML7QC-1126][Build][Fix]: Fixed issues with wellknown sign key
 
@@ -9,5 +9,5 @@
 GIT Project: realtek/repo_hooks
 Local Path : hooks
 commit 4ded49603e19bed4a23273987bb44a47e7df3281
-Branch: rtk/realtek/android-14/premp.google-refplus
+Branch: rtk/realtek/android-14/mp.google-refplus.wave
 Tag info: submissions/8
```

### 情境 3: 批次轉換

```bash
# 準備批次轉換腳本
$ cat > batch_convert_enhanced.sh << 'EOF'
#!/bin/bash

CONVERSION_TYPE="master_to_premp"

echo "開始批次轉換 - 支援 XML 和 TXT 檔案"
echo "轉換類型: $CONVERSION_TYPE"
echo ""

for file in *.xml *.txt; do
    if [[ -f "$file" && "$file" != *"_manifest.xml" && "$file" != *"_converted.txt" ]]; then
        echo "處理檔案: $file"
        
        # 偵測檔案類型並設定輸出名稱
        if [[ "$file" == *.xml ]]; then
            base_name=$(basename "$file" .xml)
            output_name="manifest_${base_name}_${CONVERSION_TYPE}_manifest.xml"
        elif [[ "$file" == *.txt ]]; then
            base_name=$(basename "$file" .txt)
            output_name="${base_name}_${CONVERSION_TYPE}_converted.txt"
        fi
        
        echo "輸出檔案: $output_name"
        
        # 執行轉換
        python enhanced_manifest_converter.py "$file" -t "$CONVERSION_TYPE" -o "$output_name"
        
        if [[ $? -eq 0 ]]; then
            echo "✓ $file 轉換成功"
        else
            echo "✗ $file 轉換失敗"
        fi
        
        echo "----------------------------------------"
    fi
done

echo "批次轉換完成"
EOF

$ chmod +x batch_convert_enhanced.sh

# 執行批次轉換
$ ./batch_convert_enhanced.sh
開始批次轉換 - 支援 XML 和 TXT 檔案
轉換類型: master_to_premp

處理檔案: atv-google-refplus.xml
輸出檔案: manifest_atv-google-refplus_master_to_premp_manifest.xml
INFO: 偵測到檔案類型: XML
...
✓ atv-google-refplus.xml 轉換成功
----------------------------------------
處理檔案: Version_Detail_144.txt
輸出檔案: Version_Detail_144_master_to_premp_converted.txt
INFO: 偵測到檔案類型: TXT
...
✓ Version_Detail_144.txt 轉換成功
----------------------------------------
批次轉換完成
```

### 情境 4: 混合檔案驗證

```bash
# 驗證轉換結果腳本
$ cat > verify_conversion.sh << 'EOF'
#!/bin/bash

echo "驗證增強版轉換工具結果"
echo "========================"

# 檢查 XML 轉換結果
for xml_file in *_manifest.xml; do
    if [[ -f "$xml_file" ]]; then
        echo "檢查 XML 檔案: $xml_file"
        
        # 檢查 XML 格式
        if xmllint --format "$xml_file" > /dev/null 2>&1; then
            echo "  ✓ XML 格式正確"
        else
            echo "  ✗ XML 格式錯誤"
        fi
        
        # 統計專案數量
        project_count=$(grep -c '<project ' "$xml_file")
        echo "  專案數量: $project_count"
        
        echo ""
    fi
done

# 檢查 TXT 轉換結果
for txt_file in *_converted.txt; do
    if [[ -f "$txt_file" ]]; then
        echo "檢查 TXT 檔案: $txt_file"
        
        # 統計 Branch 數量
        branch_count=$(grep -c '^Branch:' "$txt_file")
        echo "  Branch 數量: $branch_count"
        
        # 檢查轉換格式
        if grep -q 'mp.google-refplus.wave' "$txt_file"; then
            echo "  ✓ 包含 MP 格式分支"
        elif grep -q 'premp.google-refplus' "$txt_file"; then
            echo "  ✓ 包含 PreMP 格式分支"
        else
            echo "  ? 未知格式分支"
        fi
        
        echo ""
    fi
done

echo "驗證完成"
EOF

$ chmod +x verify_conversion.sh
$ ./verify_conversion.sh
驗證增強版轉換工具結果
========================
檢查 XML 檔案: manifest_atv-google-refplus_master_to_premp_manifest.xml
  ✓ XML 格式正確
  專案數量: 145

檢查 TXT 檔案: Version_Detail_144_master_to_premp_converted.txt
  Branch 數量: 2
  ✓ 包含 PreMP 格式分支

驗證完成
```

## 故障排除

### 常見錯誤及解決方法

#### 1. 檔案偵測錯誤
```
WARNING: 無法偵測檔案類型: [Error details]
```
**解決方法**: 
- 檢查檔案是否存在
- 確認檔案編碼為 UTF-8
- 檢查檔案內容格式

```bash
$ file input.txt
$ file input.xml
$ head -10 input.txt
```

#### 2. TXT 檔案無 Branch 資訊
```
INFO: TXT 轉換完成！
INFO: 總 Branch 數: 0
```
**解決方法**: 
- 檢查檔案是否包含 `Branch:` 行
- 確認格式正確 (`Branch: [分支名稱]`)

```bash
$ grep -n "Branch:" input.txt
$ grep -n "GIT Project:" input.txt
```

#### 3. XML 解析失敗
```
ERROR: revision 轉換失敗: XML parsing error
```
**解決方法**: 
- 檢查 XML 檔案格式
- 驗證 XML 語法正確性

```bash
$ xmllint --format input.xml
$ xmllint --valid input.xml
```

#### 4. 轉換規則未匹配
```
DEBUG: 智能轉換備案: [分支名稱]
```
**解決方法**: 
- 檢查分支名稱格式
- 確認轉換類型正確
- 查看詳細日誌輸出

```bash
# 啟用詳細日誌
$ python enhanced_manifest_converter.py input.txt -t master_to_premp 2>&1 | grep DEBUG
```

### 除錯步驟

#### 1. 檔案偵測測試
```bash
# 測試檔案偵測功能
$ python -c "
from enhanced_manifest_converter import EnhancedManifestConverter
converter = EnhancedManifestConverter()
file_type = converter.detect_file_type('input.txt')
print(f'偵測結果: {file_type}')
"
```

#### 2. 轉換邏輯測試
```bash
# 測試單一分支轉換
$ python -c "
from enhanced_manifest_converter import EnhancedManifestConverter
converter = EnhancedManifestConverter()
result = converter._convert_single_revision('realtek/android-14/premp.google-refplus', 'premp_to_mp')
print(f'轉換結果: {result}')
"
```

#### 3. 分步驟驗證
```bash
# 步驟 1: 檢查輸入檔案
$ ls -la input.txt
$ head -5 input.txt

# 步驟 2: 測試偵測
$ python enhanced_manifest_converter.py input.txt -t master_to_premp

# 步驟 3: 檢查輸出
$ ls -la *_converted.txt
$ head -5 output.txt
```

## 最佳實踐

### 1. 檔案命名規範

#### XML 檔案
```
建議格式: manifest_[identifier]_[conversion_type]_manifest.xml

範例:
- manifest_738_master_to_premp_manifest.xml
- manifest_845_premp_to_mp_manifest.xml
- manifest_901_mp_to_mpbackup_manifest.xml
```

#### TXT 檔案
```
建議格式: [original_name]_[conversion_type]_converted.txt

範例:
- Version_Detail_144_master_to_premp_converted.txt
- Version_Detail_144_premp_to_mp_converted.txt
- Version_Detail_144_mp_to_mpbackup_converted.txt
```

### 2. 工作流程建議

#### 單一檔案轉換
```bash
# 1. 備份原檔案
$ cp original.xml original.xml.backup.$(date +%Y%m%d_%H%M%S)

# 2. 執行轉換
$ python enhanced_manifest_converter.py original.xml -t master_to_premp

# 3. 驗證結果
$ diff -u original.xml output.xml
$ ./verify_conversion.sh

# 4. 建立工作空間（XML）或使用轉換結果（TXT）
```

#### 批次轉換工作流程
```bash
# 1. 準備工作目錄
$ mkdir -p conversions/$(date +%Y%m%d)/
$ cd conversions/$(date +%Y%m%d)/

# 2. 複製需要轉換的檔案
$ cp ../../*.xml .
$ cp ../../*.txt .

# 3. 執行批次轉換
$ ../../batch_convert_enhanced.sh

# 4. 驗證所有結果
$ ../../verify_conversion.sh
```

### 3. 版本控制整合

```bash
# Git 整合範例
$ git add *_manifest.xml *_converted.txt
$ git commit -m "Add converted manifests and version details - $(date +%Y%m%d)"
$ git tag conversion-$(date +%Y%m%d)
```

### 4. 自動化腳本範例

```bash
# 完整自動化轉換腳本
$ cat > auto_convert.sh << 'EOF'
#!/bin/bash

# 設定
CONVERSION_TYPE="${1:-master_to_premp}"
DATE=$(date +%Y%m%d_%H%M%S)

echo "自動化轉換腳本"
echo "轉換類型: $CONVERSION_TYPE"
echo "時間戳記: $DATE"
echo ""

# 建立工作目錄
WORK_DIR="conversion_$DATE"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# 複製源檔案
cp ../*.xml . 2>/dev/null || true
cp ../*.txt . 2>/dev/null || true

# 執行轉換
for file in *.xml *.txt; do
    if [[ -f "$file" ]]; then
        echo "轉換檔案: $file"
        python ../enhanced_manifest_converter.py "$file" -t "$CONVERSION_TYPE"
        
        if [[ $? -eq 0 ]]; then
            echo "✓ 轉換成功"
        else
            echo "✗ 轉換失敗"
        fi
    fi
done

# 產生報告
echo "" > conversion_report.txt
echo "轉換報告 - $DATE" >> conversion_report.txt
echo "===================" >> conversion_report.txt
echo "轉換類型: $CONVERSION_TYPE" >> conversion_report.txt
echo "源檔案:" >> conversion_report.txt
ls -la *.xml *.txt | grep -v '_manifest.xml\|_converted.txt' >> conversion_report.txt
echo "" >> conversion_report.txt
echo "轉換結果:" >> conversion_report.txt
ls -la *_manifest.xml *_converted.txt >> conversion_report.txt

echo ""
echo "轉換完成，工作目錄: $WORK_DIR"
echo "檢查報告: $WORK_DIR/conversion_report.txt"
EOF

$ chmod +x auto_convert.sh

# 使用範例
$ ./auto_convert.sh master_to_premp
$ ./auto_convert.sh premp_to_mp
```

## 進階功能

### 自定義轉換規則

可以在工具中修改配置來添加專案特定的轉換規則：

```python
# 在 enhanced_manifest_converter.py 中修改
FEATURE_THREE_CUSTOM_CONVERSIONS = {
    'master_to_premp': {
        '.*special_project': 'custom/branch/path'
    },
    'premp_to_mp': {
        '.*another_project': 'another/custom/branch'
    }
}
```

### 整合到 CI/CD

```bash
# Jenkins/GitLab CI 整合範例
#!/bin/bash

# 檢查是否需要轉換
if [[ "$BUILD_TYPE" == "conversion" ]]; then
    echo "執行自動轉換流程"
    
    # 下載源檔案
    wget "$MANIFEST_URL" -O source_manifest.xml
    
    # 執行轉換
    python enhanced_manifest_converter.py source_manifest.xml -t "$CONVERSION_TYPE" -o converted_manifest.xml
    
    if [[ $? -eq 0 ]]; then
        echo "轉換成功"
        # 上傳結果
        curl -X POST -F "file=@converted_manifest.xml" "$UPLOAD_URL"
    else
        echo "轉換失敗"
        exit 1
    fi
fi
```

## 快速參考

### 常用指令
```bash
# XML 檔案轉換
python enhanced_manifest_converter.py manifest.xml -t master_to_premp -o output.xml

# TXT 檔案轉換
python enhanced_manifest_converter.py version.txt -t premp_to_mp -o output.txt

# 互動模式
python enhanced_manifest_converter.py -i

# 自動檔名
python enhanced_manifest_converter.py input.xml -t master_to_premp
python enhanced_manifest_converter.py input.txt -t premp_to_mp

# 檢查檔案格式
xmllint --format file.xml
grep "Branch:" file.txt

# 比較差異
diff -u original.xml converted.xml
diff -u original.txt converted.txt
```

### 檔案類型對應表

| 輸入格式 | 輸出格式 | 轉換目標 | 使用場景 |
|----------|----------|----------|----------|
| XML | XML | revision/upstream/dest-branch 屬性 | Android Manifest 檔案 |
| TXT | TXT | Branch: 行的分支資訊 | 版本詳細資訊檔案 |

### 轉換類型對應表

| 轉換類型 | 來源 | 目標 | XML 範例 | TXT 範例 |
|----------|------|------|----------|----------|
| master_to_premp | Master | PreMP | `realtek/android-14/master` → `realtek/android-14/premp.google-refplus` | `rtk/realtek/android-14/master` → `rtk/realtek/android-14/premp.google-refplus` |
| premp_to_mp | PreMP | MP | `realtek/android-14/premp.google-refplus` → `realtek/android-14/mp.google-refplus.wave` | `rtk/realtek/android-14/premp.google-refplus` → `rtk/realtek/android-14/mp.google-refplus.wave` |
| mp_to_mpbackup | MP | MP Backup | `realtek/android-14/mp.google-refplus.wave` → `realtek/android-14/mp.google-refplus.wave.backup` | `rtk/realtek/android-14/mp.google-refplus.wave` → `rtk/realtek/android-14/mp.google-refplus.wave.backup` |

### 故障排除清單

| 問題 | 檢查指令 | 解決方法 |
|------|----------|----------|
| 檔案不存在 | `ls -la input.*` | 檢查檔案路徑 |
| 格式偵測失敗 | `file input.*` | 檢查檔案內容 |
| XML 解析錯誤 | `xmllint input.xml` | 修正 XML 語法 |
| TXT 無 Branch | `grep "Branch:" input.txt` | 檢查檔案格式 |
| 轉換規則無匹配 | 檢查日誌輸出 | 確認分支名稱格式 |

---

**本文件版本**: v2.0 - 增強版支援 XML 和 TXT  
**最後更新**: 2024-09-11  
**工具版本**: enhanced_manifest_converter.py v2.0