# 📋 Manifest 分支映射規則手冊（完整版）

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

## 🛠️ Feature Three 專用配置

### 🚫 跳過專案設定 (`FEATURE_THREE_SKIP_PROJECTS`)

允許指定特定專案跳過轉換，保持原始 revision 不變。

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

**使用方式**：
- 專案名稱包含指定模式的專案將跳過轉換
- 保持原始 revision 值不變
- 在 Excel 報告中標記為 "跳過轉換"

**範例**：
```python
'master_to_premp': [
    'special_project',  # 跳過名稱包含 'special_project' 的專案
    'test_'             # 跳過名稱包含 'test_' 的專案
]
```

### 🎯 自定義轉換規則 (`FEATURE_THREE_CUSTOM_CONVERSIONS`)

提供靈活的自定義轉換規則，支援複雜的條件匹配。

#### 📝 基本配置結構

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

##### 1️⃣ **簡單格式**（直接字串）
```python
'.*project_pattern': 'target_branch_name'
```

**範例**：
```python
'.*tvconfigs_prebuilt': 'realtek/android-14/mp.google-refplus.wave.backup'
```

##### 2️⃣ **字典格式**（單一條件）
```python
'.*project_pattern': {
    'target': 'target_branch_name',
    'path_pattern': '.*path_pattern.*'  # 可選的路徑條件
}
```

**範例**：
```python
'.*tvconfigs_prebuilt': {
    'target': 'realtek/android-14/mp.google-refplus.wave.backup',
    'path_pattern': '.*refplus5.*'
}
```

##### 3️⃣ **陣列格式**（多重條件）
```python
'.*project_pattern': [
    {
        'path_pattern': '.*condition1.*',
        'target': 'target_branch_1'
    },
    {
        'path_pattern': '.*condition2.*', 
        'target': 'target_branch_2'
    }
]
```

**範例**：
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
   - 支援萬用字元如 `.*`、`^`、`$` 等

2. **路徑條件匹配** (`path_pattern`)
   - 額外的路徑條件限制，可選
   - 匹配專案的 `path` 屬性
   - 只有名稱和路徑都匹配時才套用規則

3. **優先級順序**
   - 自定義轉換規則 > 跳過專案規則 > 標準轉換規則
   - 陣列格式中按順序檢查，第一個匹配的條件生效

#### 💡 實際使用範例

```python
FEATURE_THREE_CUSTOM_CONVERSIONS = {
    'mp_to_mpbackup': {
        # 範例1: 簡單轉換
        '.*special_project': 'realtek/android-14/mp.google-refplus.wave.backup.special',
        
        # 範例2: 基於路徑的條件轉換
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
        
        # 範例3: 單一條件轉換
        '.*another_pattern': {
            'target': 'custom_target_branch',
            'path_pattern': '.*specific_path.*'
        }
    }
}
```

---

## 🔵 第一階段：Master to PreMP 映射規則

### 🎯 精確匹配規則（最高優先級）

| 原始 Revision | 轉換後 Revision |
|---------------|-----------------|
| `realtek/master` | `realtek/android-14/premp.google-refplus` |
| `realtek/gaia` | `realtek/android-14/premp.google-refplus` |
| `realtek/gki/master` | `realtek/android-14/premp.google-refplus` |
| `realtek/android-14/master` | `realtek/android-14/premp.google-refplus` |
| `realtek/mp.google-refplus` | `realtek/android-14/premp.google-refplus` |
| `realtek/android-14/mp.google-refplus` | `realtek/android-14/premp.google-refplus` |

### 🔧 版本格式轉換

| 轉換類型 | 模式 | 轉換規則 |
|----------|------|----------|
| **版本號格式** | `realtek/vX.X.X/master` | `realtek/vX.X.X/premp.google-refplus` |

**範例**:
- `realtek/v1.2.3/master` → `realtek/v1.2.3/premp.google-refplus`
- `realtek/v2.5.0/master` → `realtek/v2.5.0/premp.google-refplus`

### 🚀 Upgrade 版本轉換

| 轉換類型 | 模式 | 轉換規則 |
|----------|------|----------|
| **Upgrade + 晶片** | `realtek/android-Y/mp.google-refplus.upgrade-X.rtdZZZZ` | `realtek/android-Y/premp.google-refplus.upgrade-X.rtdZZZZ` |
| **Upgrade 基本** | `realtek/android-Y/mp.google-refplus.upgrade-X` | `realtek/android-Y/premp.google-refplus.upgrade-X` |

**範例**:
- `realtek/android-14/mp.google-refplus.upgrade-11.rtd2851a` → `realtek/android-14/premp.google-refplus.upgrade-11.rtd2851a`
- `realtek/android-14/mp.google-refplus.upgrade-11` → `realtek/android-14/premp.google-refplus.upgrade-11`

### 🐧 Linux Kernel 轉換

| 轉換類型 | 模式 | 轉換規則 |
|----------|------|----------|
| **Linux Master** | `realtek/linux-X.X/master` | `realtek/linux-X.X/android-14/premp.google-refplus` |
| **Linux Android Master** | `realtek/linux-X.X/android-Y/master` | `realtek/linux-X.X/android-14/premp.google-refplus` |
| **Linux MP** | `realtek/linux-X.X/android-Y/mp.google-refplus` | `realtek/linux-X.X/android-14/premp.google-refplus` |
| **Linux MP + 晶片** | `realtek/linux-X.X/android-Y/mp.google-refplus.rtdZZZZ` | `realtek/linux-X.X/android-14/premp.google-refplus.rtdZZZZ` |

**範例**:
- `realtek/linux-5.15/master` → `realtek/linux-5.15/android-14/premp.google-refplus`
- `realtek/linux-4.14/android-14/master` → `realtek/linux-4.14/android-14/premp.google-refplus`

### 📱 Android 版本轉換

| 轉換類型 | 模式 | 轉換規則 |
|----------|------|----------|
| **Android MP** | `realtek/android-Y/mp.google-refplus` | `realtek/android-14/premp.google-refplus` |
| **Android MP + 晶片** | `realtek/android-Y/mp.google-refplus.rtdZZZZ` | `realtek/android-14/premp.google-refplus.rtdZZZZ` |

**範例**:
- `realtek/android-14/mp.google-refplus` → `realtek/android-14/premp.google-refplus`
- `realtek/android-14/mp.google-refplus.rtd2851a` → `realtek/android-14/premp.google-refplus.rtd2851a`

### 💾 晶片特定轉換

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

### ⛔ 跳過轉換的項目

| 項目類型 | 模式 | 處理方式 |
|----------|------|----------|
| **Google 項目** | `google/*` | 保持不變 |
| **Git Tags** | `refs/tags/*` | 保持不變 |

### 🔄 智能備案轉換

| 情況 | 處理邏輯 |
|------|----------|
| **包含 mp.google-refplus** | 替換為 `premp.google-refplus` |
| **包含 /master + Android 版本** | 轉換為對應版本的 premp |
| **其他未匹配情況** | 使用預設 `realtek/android-14/premp.google-refplus` |

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
| **已是 backup 格式** | 保持不變，不重複添加 |
| **以 .wave 結尾** | 直接添加 `.backup` 後綴 |

---

## 📊 完整轉換範例

### 🔄 基本轉換鏈

```
realtek/master
    ↓ master_to_premp
realtek/android-14/premp.google-refplus
    ↓ premp_to_mp
realtek/android-14/mp.google-refplus.wave
    ↓ mp_to_mpbackup
realtek/android-14/mp.google-refplus.wave.backup
```

### 💾 晶片特定轉換鏈

```
realtek/merlin7/master
    ↓ master_to_premp (晶片轉換)
realtek/android-14/premp.google-refplus.rtd6748
    ↓ premp_to_mp
realtek/android-14/mp.google-refplus.wave.rtd6748
    ↓ mp_to_mpbackup
realtek/android-14/mp.google-refplus.wave.backup.rtd6748
```

### 🐧 Linux Kernel 轉換鏈

```
realtek/linux-5.15/android-14/master
    ↓ master_to_premp (版本升級)
realtek/linux-5.15/android-14/premp.google-refplus
    ↓ premp_to_mp
realtek/linux-5.15/android-14/mp.google-refplus.wave
    ↓ mp_to_mpbackup
realtek/linux-5.15/android-14/mp.google-refplus.wave.backup
```

### 🚀 Upgrade 版本轉換鏈

```
realtek/android-14/mp.google-refplus.upgrade-11.rtd2851a
    ↓ master_to_premp
realtek/android-14/premp.google-refplus.upgrade-11.rtd2851a
    ↓ premp_to_mp
realtek/android-14/mp.google-refplus.wave.upgrade-11.rtd2851a
    ↓ mp_to_mpbackup
realtek/android-14/mp.google-refplus.wave.backup.upgrade-11.rtd2851a
```

### 🎯 自定義轉換範例

```
# 假設有專案 "realtek/tvconfigs_prebuilt" 且 path 包含 "refplus2"
realtek/android-14/mp.google-refplus.wave
    ↓ mp_to_mpbackup (使用自定義規則)
realtek/android-14/mp.google-refplus.wave.backup.upgrade-11
```

---

## 🎯 特殊處理規則

### 🔍 Revision 類型判斷

| Revision 類型 | 判斷標準 | 處理方式 |
|---------------|----------|----------|
| **Commit Hash** | 40字符或7-12字符的十六進制 | 使用 `upstream` 欄位進行轉換 |
| **Branch Name** | 包含斜線和文字的路徑格式 | 直接使用 `revision` 欄位 |
| **空值** | 無 revision 且 remote=rtk | 使用 default revision |

### 📋 處理優先級

1. **跳過檢查**: Google 項目、Git Tags
2. **跳過專案**: `FEATURE_THREE_SKIP_PROJECTS` 配置
3. **自定義轉換**: `FEATURE_THREE_CUSTOM_CONVERSIONS` 規則
4. **精確匹配**: 完全相符的轉換規則
5. **模式匹配**: 正規表達式匹配規則
6. **智能備案**: 通用轉換邏輯

---

## 📈 轉換統計分類

| 統計項目 | 說明 |
|----------|------|
| **總專案數** | 所有處理的專案數量 |
| **實際轉換專案數** | revision 有變更的專案 |
| **未轉換專案數** | revision 保持不變的專案 |
| **跳過專案數** | 在跳過清單中的專案 |
| **自定義轉換數** | 使用自定義規則轉換的專案 |
| **Hash Revision 數量** | 使用 commit hash 的專案 |
| **Branch Revision 數量** | 使用分支名稱的專案 |
| **使用 Upstream 轉換數量** | hash revision 使用 upstream 的專案 |

---

## ⚙️ 系統配置

### 🔧 動態版本設定

| 配置項目 | 當前值 | 說明 |
|----------|--------|------|
| **Android 版本** | `14` | 當前使用的 Android 版本 |
| **預設分支** | `realtek/android-14/premp.google-refplus` | PreMP 預設分支 |
| **Master 分支** | `realtek/android-14/master` | Android Master 分支 |

### 🎯 重要提醒

- ✅ 所有轉換規則都支援動態 Android 版本調整
- ✅ 晶片映射表可擴展新的晶片型號
- ✅ Linux kernel 版本完全動態匹配
- ✅ Upgrade 版本號自動保留和轉換
- ✅ 支援靈活的跳過專案配置
- ✅ 支援複雜的自定義轉換規則
- ✅ 支援基於專案名稱和路徑的條件匹配

---

## 🔧 配置範例

### 完整配置範例

```python
# 跳過專案設定
FEATURE_THREE_SKIP_PROJECTS = {
    'master_to_premp': [
        'external/googletest',
        'platform/system/core'
    ],
    
    'premp_to_mp': [
        'test_project'
    ],
    
    'mp_to_mpbackup': []
}

# 自定義轉換規則
FEATURE_THREE_CUSTOM_CONVERSIONS = {
    'master_to_premp': {},
    
    'premp_to_mp': {},
    
    'mp_to_mpbackup': {
        # 複雜的條件匹配
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
        
        # 簡單轉換
        '.*special_project': 'realtek/android-14/mp.google-refplus.wave.backup.special',
        
        # 單一條件轉換
        '.*conditional_project': {
            'target': 'custom_target_branch',
            'path_pattern': '.*specific_condition.*'
        }
    }
}
```

這個配置系統提供了極大的靈活性，可以處理各種複雜的轉換需求和特殊情況。