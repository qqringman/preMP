# 📋 Manifest 分支映射規則手冊（Feature Three 專用版）

## 🎯 轉換鏈總覽

```
Master → PreMP → Wave → Wave Backup
```

| 階段 | 轉換類型 | 關鍵字轉換 |
|------|----------|------------|
| 🔵 **第一階段** | `master_to_premp` | `master` → `premp.google-refplus` |
| 🟢 **第二階段** | `premp_to_mp` | `premp.google-refplus` → `mp.google-refplus.wave` |
| 🟠 **第三階段** | `mp_to_mpbackup` | `mp.google-refplus.wave` → `mp.google-refplus.wave.backup` |

---

## ⚡ 特殊處理規則（Feature Three 專用）

### 🚫 跳過專案設定 (`FEATURE_THREE_SKIP_PROJECTS`)

允許指定特定專案跳過轉換，保持原始 revision 不變。

#### 📝 配置結構

```python
FEATURE_THREE_SKIP_PROJECTS = {
    'master_to_premp': [
        # 'project_name_pattern_1',
        # 'project_name_pattern_2'
    ],
    
    'premp_to_mp': [
        # 'project_name_pattern_1'
    ],
    
    'mp_to_mpbackup': [
        # 'project_name_pattern_1'
    ]
}
```

#### 🔧 使用方式

- **匹配邏輯**: 專案名稱包含指定模式的專案將跳過轉換
- **處理結果**: 保持原始 revision 值不變
- **Excel標記**: 在報告中標記為 `skipped: true`，原因為 `in_skip_list`
- **優先級**: 低於自定義轉換規則，高於標準轉換規則

#### 💡 範例

```python
FEATURE_THREE_SKIP_PROJECTS = {
    'master_to_premp': [
        'external/googletest',     # 跳過外部測試專案
        'platform/system/core',   # 跳過系統核心專案
        'test_'                    # 跳過所有測試相關專案
    ],
    
    'premp_to_mp': [
        'special_project'          # 跳過特殊專案
    ],
    
    'mp_to_mpbackup': []           # 此階段不跳過任何專案
}
```

### 🎯 自定義轉換規則 (`FEATURE_THREE_CUSTOM_CONVERSIONS`)

提供靈活的自定義轉換規則，支援複雜的條件匹配和多重條件。

#### 📝 配置結構

```python
FEATURE_THREE_CUSTOM_CONVERSIONS = {
    'master_to_premp': {
        # 自定義規則
    },
    
    'premp_to_mp': {
        # 自定義規則
    },
    
    'mp_to_mpbackup': {
        # 自定義規則
    }
}
```

#### 🔧 支援的三種格式

##### 1️⃣ **簡單格式**（直接字串映射）
```python
'.*project_pattern': 'target_branch_name'
```

**特點**:
- 最簡潔的配置方式
- 適用於簡單的一對一映射
- 不支援路徑條件

**範例**:
```python
'.*tvconfigs_prebuilt': 'realtek/android-14/mp.google-refplus.wave.backup'
```

##### 2️⃣ **字典格式**（單一條件物件）
```python
'.*project_pattern': {
    'target': 'target_branch_name',
    'path_pattern': '.*path_pattern.*'  # 可選的路徑條件
}
```

**特點**:
- 支援額外的路徑條件限制
- 適用於需要同時匹配專案名稱和路徑的情況
- 結構清晰，容易理解

**範例**:
```python
'.*tvconfigs_prebuilt': {
    'target': 'realtek/android-14/mp.google-refplus.wave.backup',
    'path_pattern': '.*refplus5.*'
}
```

##### 3️⃣ **陣列格式**（多重條件匹配）
```python
'.*project_pattern': [
    {
        'path_pattern': '.*condition1.*',
        'target': 'target_branch_1'
    },
    {
        'path_pattern': '.*condition2.*', 
        'target': 'target_branch_2'
    },
    {
        'path_pattern': '.*condition3.*',
        'target': 'target_branch_3'
    }
]
```

**特點**:
- 支援同一專案名稱模式對應多個不同的目標分支
- 根據路徑條件選擇不同的轉換目標
- 按陣列順序檢查，第一個匹配的條件生效
- 適用於複雜的條件式轉換

**範例**:
```python
'.*tvconfigs_prebuilt': [
    {
        'path_pattern': '.*refplus2.*',
        'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
    },
    {
        'path_pattern': '.*refplus3.*',
        'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
    },
    {
        'path_pattern': '.*refplus5.*',
        'target': 'realtek/android-14/mp.google-refplus.wave.backup'
    }
]
```

#### 🎯 條件匹配邏輯

1. **專案名稱匹配** (`project_pattern`)
   - 使用正規表達式匹配專案的 `name` 屬性
   - 支援萬用字元：`.*`（任意字符）、`^`（開始）、`$`（結束）等
   - 範例：`.*tvconfigs.*` 匹配包含 "tvconfigs" 的專案名稱

2. **路徑條件匹配** (`path_pattern`)
   - 額外的路徑條件限制，為可選參數
   - 匹配專案的 `path` 屬性
   - 只有名稱和路徑都匹配時才套用該規則
   - 範例：`.*refplus2.*` 匹配路徑包含 "refplus2" 的專案

3. **執行順序** (陣列格式)
   - 按陣列中的順序逐一檢查條件
   - 第一個同時匹配名稱和路徑的規則生效
   - 後續規則將被跳過

#### 💡 實際使用範例

```python
FEATURE_THREE_CUSTOM_CONVERSIONS = {
    'master_to_premp': {
        # 範例1: 特殊專案的簡單轉換
        '.*special_kernel': 'realtek/android-14/premp.google-refplus.special',
        
        # 範例2: 基於版本的條件轉換
        '.*legacy_project': {
            'target': 'realtek/android-14/premp.google-refplus.legacy',
            'path_pattern': '.*legacy.*'
        }
    },
    
    'premp_to_mp': {
        # 範例3: 測試環境的特殊轉換
        '.*test_.*': 'realtek/android-14/mp.google-refplus.wave.test'
    },
    
    'mp_to_mpbackup': {
        # 範例4: 複雜的多條件轉換 - TVConfig 專案
        '.*tvconfigs_prebuilt': [
            {
                'path_pattern': '.*refplus2.*',
                'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
            },            
            {
                'path_pattern': '.*refplus3.*',
                'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
            },
            {
                'path_pattern': '.*refplus5.*',
                'target': 'realtek/android-14/mp.google-refplus.wave.backup'
            }
        ],
        
        # 範例5: 另一個專案的簡單轉換
        '.*another_special': 'realtek/android-14/mp.google-refplus.wave.backup.special',
        
        # 範例6: 條件式轉換
        '.*conditional_project': {
            'target': 'realtek/android-14/mp.google-refplus.wave.backup.conditional',
            'path_pattern': '.*specific_condition.*'
        }
    }
}
```

#### 🏃‍♂️ 處理流程

1. **專案名稱檢查**: 使用正規表達式檢查專案名稱是否匹配 pattern
2. **格式判斷**: 判斷規則是簡單字串、字典物件或陣列
3. **路徑條件檢查**: 如果有 `path_pattern`，檢查專案路徑是否匹配
4. **目標分支返回**: 返回對應的 `target` 分支名稱
5. **日誌記錄**: 記錄匹配的規則和轉換結果

---

## 🎯 處理優先級順序

系統按以下優先級處理每個專案的 revision 轉換：

```
1. ⛔ 系統跳過檢查 (最高優先級)
   ├── Google 項目 (google/*)
   ├── Git Tags (refs/tags/*)
   └── 空 revision 專案

2. 🚫 跳過專案設定
   └── FEATURE_THREE_SKIP_PROJECTS 配置

3. 🎯 自定義轉換規則
   └── FEATURE_THREE_CUSTOM_CONVERSIONS 配置

4. 🔍 精確匹配轉換
   └── 完全相符的預定義轉換規則

5. 🔧 模式匹配轉換
   ├── 版本格式轉換
   ├── Upgrade 版本轉換
   ├── Linux Kernel 轉換
   ├── Android 版本轉換
   └── 晶片特定轉換

6. 🔄 智能備案轉換 (最低優先級)
   └── 通用替換和預設轉換
```

---

## 🔵 第一階段：Master to PreMP 映射規則

### 🎯 精確匹配規則

| 原始 Revision | 轉換後 Revision |
|---------------|-----------------|
| `realtek/master` | `realtek/android-14/premp.google-refplus` |
| `realtek/gaia` | `realtek/android-14/premp.google-refplus` |
| `realtek/gki/master` | `realtek/android-14/premp.google-refplus` |
| `realtek/android-14/master` | `realtek/android-14/premp.google-refplus` |
| `realtek/mp.google-refplus` | `realtek/android-14/premp.google-refplus` |
| `realtek/android-14/mp.google-refplus` | `realtek/android-14/premp.google-refplus` |

### 🔧 模式匹配轉換

#### 版本號格式轉換
| 模式 | 轉換規則 | 範例 |
|------|----------|------|
| `realtek/vX.X.X/master` | `realtek/vX.X.X/premp.google-refplus` | `realtek/v1.2.3/master` → `realtek/v1.2.3/premp.google-refplus` |

#### Upgrade 版本轉換
| 模式 | 轉換規則 | 範例 |
|------|----------|------|
| `realtek/android-Y/mp.google-refplus.upgrade-X.rtdZZZZ` | `realtek/android-{current}/premp.google-refplus.upgrade-X.rtdZZZZ` | `realtek/android-14/mp.google-refplus.upgrade-11.rtd2851a` → `realtek/android-14/premp.google-refplus.upgrade-11.rtd2851a` |
| `realtek/android-Y/mp.google-refplus.upgrade-X` | `realtek/android-{current}/premp.google-refplus.upgrade-X` | `realtek/android-14/mp.google-refplus.upgrade-11` → `realtek/android-14/premp.google-refplus.upgrade-11` |

#### Linux Kernel 轉換
| 模式 | 轉換規則 | 範例 |
|------|----------|------|
| `realtek/linux-X.X/master` | `realtek/linux-X.X/android-{current}/premp.google-refplus` | `realtek/linux-5.15/master` → `realtek/linux-5.15/android-14/premp.google-refplus` |
| `realtek/linux-X.X/android-Y/master` | `realtek/linux-X.X/android-{current}/premp.google-refplus` | `realtek/linux-4.14/android-14/master` → `realtek/linux-4.14/android-14/premp.google-refplus` |
| `realtek/linux-X.X/android-Y/mp.google-refplus` | `realtek/linux-X.X/android-{current}/premp.google-refplus` | `realtek/linux-5.15/android-14/mp.google-refplus` → `realtek/linux-5.15/android-14/premp.google-refplus` |
| `realtek/linux-X.X/android-Y/mp.google-refplus.rtdZZZZ` | `realtek/linux-X.X/android-{current}/premp.google-refplus.rtdZZZZ` | `realtek/linux-5.15/android-14/mp.google-refplus.rtd2851a` → `realtek/linux-5.15/android-14/premp.google-refplus.rtd2851a` |

#### Android 版本轉換
| 模式 | 轉換規則 | 範例 |
|------|----------|------|
| `realtek/android-Y/mp.google-refplus` | `realtek/android-{current}/premp.google-refplus` | `realtek/android-14/mp.google-refplus` → `realtek/android-14/premp.google-refplus` |
| `realtek/android-Y/mp.google-refplus.rtdZZZZ` | `realtek/android-{current}/premp.google-refplus.rtdZZZZ` | `realtek/android-14/mp.google-refplus.rtd2851a` → `realtek/android-14/premp.google-refplus.rtd2851a` |

#### 晶片特定轉換
| 晶片型號 | RTD 型號 | 轉換規則 |
|----------|----------|----------|
| `mac7p` | `rtd2851a` | `realtek/mac7p/master` → `realtek/android-14/premp.google-refplus.rtd2851a` |
| `mac8q` | `rtd2851f` | `realtek/mac8q/master` → `realtek/android-14/premp.google-refplus.rtd2851f` |
| `mac9p` | `rtd2895p` | `realtek/mac9p/master` → `realtek/android-14/premp.google-refplus.rtd2895p` |
| `merlin7` | `rtd6748` | `realtek/merlin7/master` → `realtek/android-14/premp.google-refplus.rtd6748` |
| `merlin8` | `rtd2885p` | `realtek/merlin8/master` → `realtek/android-14/premp.google-refplus.rtd2885p` |
| `merlin8p` | `rtd2885q` | `realtek/merlin8p/master` → `realtek/android-14/premp.google-refplus.rtd2885q` |
| `merlin9` | `rtd2875q` | `realtek/merlin9/master` → `realtek/android-14/premp.google-refplus.rtd2875q` |
| `matrix` | `rtd2811` | `realtek/matrix/master` → `realtek/android-14/premp.google-refplus.rtd2811` |

---

## 🟢 第二階段：PreMP to MP 映射規則

### 🎯 核心轉換規則

**單一替換邏輯**: `premp.google-refplus` → `mp.google-refplus.wave`

| 原始 Revision | 轉換後 Revision |
|---------------|-----------------|
| `realtek/android-14/premp.google-refplus` | `realtek/android-14/mp.google-refplus.wave` |
| `realtek/android-14/premp.google-refplus.rtd2851a` | `realtek/android-14/mp.google-refplus.wave.rtd2851a` |
| `realtek/linux-5.15/android-14/premp.google-refplus` | `realtek/linux-5.15/android-14/mp.google-refplus.wave` |
| `realtek/android-14/premp.google-refplus.upgrade-11` | `realtek/android-14/mp.google-refplus.wave.upgrade-11` |
| `realtek/android-14/premp.google-refplus.upgrade-11.rtd2851a` | `realtek/android-14/mp.google-refplus.wave.upgrade-11.rtd2851a` |

---

## 🟠 第三階段：MP to MPBackup 映射規則

### 🎯 核心轉換規則

**單一替換邏輯**: `mp.google-refplus.wave` → `mp.google-refplus.wave.backup`

| 原始 Revision | 轉換後 Revision |
|---------------|-----------------|
| `realtek/android-14/mp.google-refplus.wave` | `realtek/android-14/mp.google-refplus.wave.backup` |
| `realtek/android-14/mp.google-refplus.wave.rtd2851a` | `realtek/android-14/mp.google-refplus.wave.backup.rtd2851a` |
| `realtek/linux-5.15/android-14/mp.google-refplus.wave` | `realtek/linux-5.15/android-14/mp.google-refplus.wave.backup` |
| `realtek/android-14/mp.google-refplus.wave.upgrade-11` | `realtek/android-14/mp.google-refplus.wave.backup.upgrade-11` |
| `realtek/android-14/mp.google-refplus.wave.upgrade-11.rtd2851a` | `realtek/android-14/mp.google-refplus.wave.backup.upgrade-11.rtd2851a` |

### ⚠️ 特殊處理

| 情況 | 處理方式 |
|------|----------|
| **已是 backup 格式** | 保持不變，不重複添加 `.backup` |
| **以 .wave 結尾** | 直接添加 `.backup` 後綴 |
| **包含 wave 但格式特殊** | 在 wave 後插入 `.backup` |

---

## 🔍 特殊情況處理

### ⛔ 系統自動跳過項目

| 項目類型 | 模式 | 處理方式 | 原因 |
|----------|------|----------|------|
| **Google 項目** | `google/*` | 保持不變 | 外部專案，不應修改 |
| **Git Tags** | `refs/tags/*` | 保持不變 | 版本標籤，不應轉換 |
| **空 Revision** | 無 revision 屬性 | 跳過轉換 | 缺少必要資訊 |

### 🔄 Revision 類型判斷與處理

| Revision 類型 | 判斷標準 | 處理方式 |
|---------------|----------|----------|
| **Commit Hash** | 7-40字符的十六進制字串 | 使用專案的 `upstream` 欄位進行轉換 |
| **Branch Name** | 包含路徑分隔符的字串 | 直接使用 `revision` 欄位進行轉換 |
| **預設值處理** | `revision` 為空且 `remote=rtk` | 使用 manifest 的 default revision |

### 📊 轉換統計分類

| 統計項目 | 說明 | 標記方式 |
|----------|------|----------|
| **總專案數** | 所有處理的專案數量 | - |
| **實際轉換專案數** | `revision` 有變更的專案 | `changed: true` |
| **未轉換專案數** | `revision` 保持不變的專案 | `changed: false` |
| **跳過專案數** | 在跳過清單中的專案 | `skipped: true, skip_reason: 'in_skip_list'` |
| **自定義轉換數** | 使用自定義規則轉換的專案 | 日誌中標記為「使用自定義轉換規則」 |
| **無 Revision 跳過** | 沒有 revision 的專案 | `skip_reason: 'no_revision'` |
| **Hash Revision 數量** | 使用 commit hash 的專案 | 使用 `upstream` 進行轉換 |
| **Branch Revision 數量** | 使用分支名稱的專案 | 直接使用 `revision` 轉換 |

---

## 📈 完整轉換範例

### 🔄 基本轉換鏈

```
realtek/master
    ↓ master_to_premp (精確匹配)
realtek/android-14/premp.google-refplus
    ↓ premp_to_mp (關鍵字替換)
realtek/android-14/mp.google-refplus.wave
    ↓ mp_to_mpbackup (關鍵字替換)
realtek/android-14/mp.google-refplus.wave.backup
```

### 💾 晶片特定轉換鏈

```
realtek/merlin7/master
    ↓ master_to_premp (晶片特定規則)
realtek/android-14/premp.google-refplus.rtd6748
    ↓ premp_to_mp (關鍵字替換)
realtek/android-14/mp.google-refplus.wave.rtd6748
    ↓ mp_to_mpbackup (關鍵字替換)
realtek/android-14/mp.google-refplus.wave.backup.rtd6748
```

### 🎯 自定義轉換範例

```
# 假設專案 "realtek/tvconfigs_prebuilt" 且 path 包含 "refplus2"
realtek/android-14/mp.google-refplus.wave
    ↓ mp_to_mpbackup (自定義轉換規則)
realtek/android-14/mp.google-refplus.wave.backup.upgrade-11
```

### 🚫 跳過轉換範例

```
# 假設專案 "platform/system/core" 在跳過清單中
realtek/master
    ↓ master_to_premp (跳過轉換)
realtek/master (保持不變)
```

---

## ⚙️ 系統配置說明

### 🔧 動態版本設定

| 配置項目 | 當前值 | 功能說明 |
|----------|--------|----------|
| `CURRENT_ANDROID_VERSION` | `'14'` | 當前使用的 Android 版本 |
| `get_default_premp_branch()` | `realtek/android-14/premp.google-refplus` | PreMP 預設分支 |
| `get_default_android_master_branch()` | `realtek/android-14/master` | Android Master 分支 |

### 🎯 晶片映射表 (`CHIP_TO_RTD_MAPPING`)

```python
CHIP_TO_RTD_MAPPING = {
    'mac7p': 'rtd2851a',
    'mac8q': 'rtd2851f', 
    'mac9p': 'rtd2895p',
    'merlin7': 'rtd6748',
    'merlin8': 'rtd2885p',
    'merlin8p': 'rtd2885q',
    'merlin9': 'rtd2875q',
    'matrix': 'rtd2811'
}
```

---

## 🛠️ 完整配置範例

### 📋 實際配置模板

```python
# =====================================
# Feature Three 跳過專案設定
# =====================================
FEATURE_THREE_SKIP_PROJECTS = {
    'master_to_premp': [
        'external/googletest',      # 跳過外部測試框架
        'platform/system/core',    # 跳過系統核心專案
        'test_',                    # 跳過所有測試相關專案
        'platform/frameworks/base' # 跳過框架基礎專案
    ],
    
    'premp_to_mp': [
        'special_debug_project',    # 跳過特殊除錯專案
        'legacy_'                   # 跳過舊版相關專案
    ],
    
    'mp_to_mpbackup': [
        'experimental_feature'      # 跳過實驗性功能專案
    ]
}

# =====================================
# Feature Three 自定義轉換規則
# =====================================
FEATURE_THREE_CUSTOM_CONVERSIONS = {
    'master_to_premp': {
        # 特殊核心專案的版本控制
        '.*kernel_special': 'realtek/android-14/premp.google-refplus.kernel-special',
        
        # 基於路徑的條件轉換
        '.*legacy_driver': {
            'target': 'realtek/android-14/premp.google-refplus.legacy',
            'path_pattern': '.*legacy.*'
        }
    },
    
    'premp_to_mp': {
        # 測試環境的特殊處理
        '.*test_framework': 'realtek/android-14/mp.google-refplus.wave.test',
        
        # 開發分支的特殊處理
        '.*development_.*': {
            'target': 'realtek/android-14/mp.google-refplus.wave.dev',
            'path_pattern': '.*dev.*'
        }
    },
    
    'mp_to_mpbackup': {
        # 🎯 TVConfig 專案的複雜條件轉換
        '.*tvconfigs_prebuilt': [
            {
                'path_pattern': '.*refplus2.*',
                'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
            },            
            {
                'path_pattern': '.*refplus3.*',
                'target': 'realtek/android-14/mp.google-refplus.wave.backup.upgrade-11'
            },
            {
                'path_pattern': '.*refplus5.*',
                'target': 'realtek/android-14/mp.google-refplus.wave.backup'
            }
        ],
        
        # 特殊硬體支援專案
        '.*hardware_special': 'realtek/android-14/mp.google-refplus.wave.backup.hw-special',
        
        # 條件式安全更新專案
        '.*security_update': {
            'target': 'realtek/android-14/mp.google-refplus.wave.backup.security',
            'path_pattern': '.*security.*'
        },
        
        # 效能最佳化專案
        '.*performance_.*': [
            {
                'path_pattern': '.*cpu.*',
                'target': 'realtek/android-14/mp.google-refplus.wave.backup.perf-cpu'
            },
            {
                'path_pattern': '.*gpu.*',
                'target': 'realtek/android-14/mp.google-refplus.wave.backup.perf-gpu'
            }
        ]
    }
}
```

---

## 📚 重要提醒與最佳實踐

### ✅ 配置建議

1. **跳過專案設定**
   - 優先使用簡短且明確的模式匹配
   - 避免過於廣泛的模式，以免誤跳過重要專案
   - 定期檢查跳過清單的必要性

2. **自定義轉換規則**
   - 簡單情況使用字串格式，複雜情況使用字典或陣列格式
   - 路徑條件要具體明確，避免過於廣泛匹配
   - 陣列格式中將最特殊的條件放在前面

3. **測試與驗證**
   - 新增規則後要進行完整測試
   - 檢查 Excel 報告中的轉換統計和差異分析
   - 注意觀察日誌中的自定義規則匹配情況

### 🔄 系統特性

- ✅ 支援動態 Android 版本調整（`CURRENT_ANDROID_VERSION`）
- ✅ 完整的優先級處理機制
- ✅ 詳細的轉換統計和日誌記錄
- ✅ 靈活的跳過專案機制
- ✅ 複雜的多條件自定義轉換支援
- ✅ 支援基於專案名稱和路徑的雙重條件匹配
- ✅ 完整的錯誤處理和備案機制
- ✅ Excel 報告中的詳細差異分析

### 🎯 Debug 技巧

1. **檢查轉換日誌** - 查看哪些專案使用了自定義規則
2. **Excel 差異頁籤** - 分析轉換後與 Gerrit 的差異
3. **統計數據驗證** - 確認跳過和自定義轉換的專案數量
4. **路徑條件測試** - 驗證 `path_pattern` 是否正確匹配

---

*本文檔涵蓋了 Feature Three 的完整映射規則和特殊處理功能，為複雜的 manifest 轉換需求提供了全面的解決方案。*