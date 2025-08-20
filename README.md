# JIRA/Gerrit 整合工具系統

> 專業的 Android manifest 檔案管理、分支映射和版本轉換工具

## 🚀 快速開始

### 1. 安裝依賴
```bash
pip install -r requirements.txt
```

### 2. 配置系統
編輯 `config.py` 設定連線資訊：
```python
# JIRA 連線設定
JIRA_SITE = 'jira.realtek.com'
JIRA_USER = 'your_username'
JIRA_PASSWORD = 'your_password'
JIRA_TOKEN = ''  # 可選，API Token (優先於密碼)

# Gerrit 連線設定  
GERRIT_BASE = 'https://mm2sd.rtkbf.com/'
GERRIT_API_PREFIX = '/a'
GERRIT_USER = 'your_username'
GERRIT_PW = 'your_password'
```

**⚠️ 重要說明：**
- `JIRA_TOKEN`：建議使用 API Token 替代密碼，安全性更高
- `GERRIT_API_PREFIX`：Gerrit API 路徑前綴，通常為 `/a`
- 所有連線資訊請依據您的實際環境設定

### 3. 啟動程式
```bash
cd overwrite_lib
python main.py
```

### 4. 驗證設定
```bash
# 首次使用建議先測試連線
python main.py
# 選擇 [4] → [1] 測試 JIRA 連線
# 選擇 [4] → [2] 測試 Gerrit 連線
# 選擇 [4] → [3] → [1] 檢視目前設定
```

## 📋 main.py 操作指南

### 🎮 主選單

```
📊 [1] 晶片映射表處理
🌿 [2] 分支管理工具  
📄 [3] Manifest 處理工具
⚙️  [4] 系統工具
❌ [0] 離開程式
```

---

## 🔍 功能一：擴充晶片映射表

**📝 操作步驟**
```
[1] → [1] → 輸入檔案路徑 → 選擇輸出資料夾 → 確認執行
```

**📂 輸入檔案**  
`all_chip_mapping_table.xlsx`

**📊 輸出結果**
- `all_chip_mapping_table_ext.xlsx` - 擴充後完整資料表
- `DB{number}/` - 各 DB 對應的 manifest 檔案

---

## 🌿 功能二：建立分支映射表

**📝 操作步驟**
```
[2] → [1] → 選擇 manifest.xml → 選擇轉換類型 → 設定選項 → 確認執行
```

**🔄 轉換類型**
- `[1]` **master → premp** 
- `[2]` **premp → mp**
- `[3]` **mp → mpbackup**

**⚙️ 可選功能**
- ✅ 去除重複資料
- 🌿 建立實際分支 (支援強制更新)
- 🔍 檢查分支存在性

**📊 輸出結果**
- `manifest_{type}.xlsx` - 分支映射表
- 包含專案列表和建立狀態頁籤

---

## 📄 功能三：Manifest 轉換工具

**📝 操作步驟**
```
[3] → [1] → 選擇轉換類型 → 設定輸出路徑 → 選擇推送選項 → 確認執行
```

**🔄 轉換類型**
- `[1]` **Master → PreMP** (`atv-google-refplus.xml` → `atv-google-refplus-premp.xml`)
- `[2]` **PreMP → MP** (`atv-google-refplus-premp.xml` → `atv-google-refplus-wave.xml`)  
- `[3]` **MP → MP Backup** (`atv-google-refplus-wave.xml` → `atv-google-refplus-wave-backup.xml`)

**🚀 進階功能**
- ⬇️ 自動從 Gerrit 下載源檔案
- 🔍 智能差異分析和比較
- 📤 推送到 Gerrit (Code Review)

---

## 🔍 比較工具

### 📄 比較 manifest 差異 `[3] → [2]`

**🎯 比較模式**
- `[1-4]` 本地檔案 vs Gerrit (Master/PreMP/MP/MP Backup)
- `[5]` 本地檔案間比較

### ⬇️ 下載 Gerrit manifest `[3] → [3]`

**📥 下載選項**
- `[1-4]` 標準檔案 (Master/PreMP/MP/MP Backup)
- `[5]` 自定義 URL 下載
- `[6]` 瀏覽 Gerrit 查看檔案

---

## ⚙️ 系統工具

```
[4] → [1]  🔗 測試 JIRA 連線
[4] → [2]  🔗 測試 Gerrit 連線  
[4] → [3]  ⚙️ 系統設定管理
    → [1] 檢視目前設定 (檢查所有配置值)
    → [2] 重設所有設定
[4] → [4]  🔍 診斷連線問題
```

**💡 建議：首次使用前先執行連線測試確認設定正確**

---

## 📊 輸出格式

### 🎨 Excel 報告特色
- 🔵 **美化標題列** - 藍色背景白字
- 📏 **自動調整欄寬** - 內容適應寬度
- 🔗 **超連結支援** - 直接連結 Gerrit
- 📋 **多頁籤設計** - 功能分類清楚

### 🎯 狀態顏色
- 🟢 **成功/相同** - 綠色標示
- 🔴 **失敗/不同** - 紅色標示
- 🟡 **警告/未知** - 黃色標示
- 🔵 **Tag 類型** - 藍字顯示
- 🟣 **Branch 類型** - 紫字顯示

---

## 🛠️ 故障排除

### ❌ JIRA 連線問題
```
症狀: HTTP 403 認證失敗
解決: 檢查帳號密碼 → 確認專案權限 → 使用 API Token

配置建議:
• 優先使用 JIRA_TOKEN (Personal Access Token)
• JIRA_TOKEN 有值時會優先於 JIRA_PASSWORD  
• 確認帳號有對應專案的存取權限
```

### ❌ Gerrit 認證問題
```
症狀: HTTP 401 下載失敗  
解決: 檢查設定 → 確認 VPN 連線 → 驗證 SSH 金鑰
```

### ❌ Git 推送問題
```
症狀: 推送失敗
解決: 確認 Git 安裝 → 檢查 SSH 認證 → 驗證推送權限
```

---

## 💡 使用技巧

**⚡ 快速操作**
- 數字組合：`11` (功能一) `21` (功能二) `31` (功能三)
- 預設值：大部分選項可直接按 Enter

**📁 檔案管理**  
- 所有輸出保存在指定資料夾
- Excel 包含完整處理記錄

---

## 📁 專案結構

```
project/
├── config.py                # ⚙️ 系統配置檔 (JIRA/Gerrit 設定)
├── requirements.txt         # 📦 依賴套件清單
└── overwrite_lib/           # 📂 核心模組目錄
    ├── main.py              # 🎮 互動式主程式
    ├── feature_one.py       # 🔍 晶片映射表
    ├── feature_two.py       # 🌿 分支映射表  
    ├── feature_three.py     # 📄 轉換工具
    ├── jira_manager.py      # 📡 JIRA API
    ├── gerrit_manager.py    # 📡 Gerrit API
    ├── excel_handler.py     # 📊 Excel 處理
    ├── utils.py             # 🛠️ 通用工具
    └── manifest_compare/    # 🔍 比較工具
        └── manifest_conversion.py
```

---

**🚀 開始使用**：`cd overwrite_lib && python main.py`