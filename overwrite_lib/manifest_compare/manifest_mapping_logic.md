# Manifest 分支映射邏輯說明文檔

## 📋 總體概述

本文檔說明 feature_two.py 和 feature_three.py 中實現的三種分支映射轉換邏輯：

1. **Master to PreMP** (`master_vs_premp`) - 從 master 分支轉換到 premp 分支
2. **PreMP to Wave** (`premp_vs_mp`) - 從 premp 分支轉換到 mp.wave 分支  
3. **Wave to Wave Backup** (`mp_vs_mpbackup`) - 從 wave 分支轉換到 wave.backup 分支

---

## 🎯 轉換邏輯概要

### 轉換鏈條
```
Master → PreMP → Wave → Wave Backup
  ↓        ↓       ↓
master   premp    mp      mp
分支   .google-  .google- .google-
      refplus   refplus  refplus
                .wave    .wave
                         .backup
```

### 處理順序
1. **前置處理**：判斷 revision 類型（Hash vs Branch Name）
2. **Default Revision**：處理空 revision 的情況
3. **轉換邏輯**：根據轉換類型應用對應規則
4. **後處理**：生成連結和比較資訊

---

## 🔥 1. Master to PreMP 轉換邏輯

### 1.1 精確匹配規則（優先級最高）

| 原始 Revision | 轉換後 Revision | 說明 |
|---------------|-----------------|------|
| `realtek/master` | `realtek/android-14/premp.google-refplus` | 基本 master 轉換 |
| `realtek/gaia` | `realtek/android-14/premp.google-refplus` | Gaia 分支轉換 |
| `realtek/gki/master` | `realtek/android-14/premp.google-refplus` | GKI master 轉換 |
| `realtek/android-14/master` | `realtek/android-14/premp.google-refplus` | Android 14 master |
| `realtek/mp.google-refplus` | `realtek/android-14/premp.google-refplus` | 直接 MP 轉換 |
| `realtek/android-14/mp.google-refplus` | `realtek/android-14/premp.google-refplus` | Android 14 MP |

### 1.2 Linux Kernel 分支轉換

| 模式 | 轉換規則 | 範例 |
|------|----------|------|
| `realtek/linux-X.X/master` | `realtek/linux-X.X/android-14/premp.google-refplus` | `realtek/linux-5.15/master` → `realtek/linux-5.15/android-14/premp.google-refplus` |
| `realtek/linux-X.X/android-Y/master` | `realtek/linux-X.X/android-Y/premp.google-refplus` | `realtek/linux-4.14/android-14/master` → `realtek/linux-4.14/android-14/premp.google-refplus` |
| `realtek/linux-X.X/android-Y/mp.google-refplus` | `realtek/linux-X.X/android-Y/premp.google-refplus` | `realtek/linux-5.15/android-14/mp.google-refplus` → `realtek/linux-5.15/android-14/premp.google-refplus` |

### 1.3 晶片特定轉換

| 晶片 | RTD 型號 | 轉換規則 |
|------|----------|----------|
| `mac7p` | `rtd2851a` | `realtek/mac7p/master` → `realtek/android-14/premp.google-refplus.rtd2851a` |
| `mac8q` | `rtd2851f` | `realtek/mac8q/master` → `realtek/android-14/premp.google-refplus.rtd2851f` |
| `mac9p` | `rtd2895p` | `realtek/mac9p/master` → `realtek/android-14/premp.google-refplus.rtd2895p` |
| `merlin7` | `rtd6748` | `realtek/merlin7/master` → `realtek/android-14/premp.google-refplus.rtd6748` |
| `merlin8` | `rtd2885p` | `realtek/merlin8/master` → `realtek/android-14/premp.google-refplus.rtd2885p` |
| `merlin8p` | `rtd2885q` | `realtek/merlin8p/master` → `realtek/android-14/premp.google-refplus.rtd2885q` |
| `merlin9` | `rtd2875q` | `realtek/merlin9/master` → `realtek/android-14/premp.google-refplus.rtd2875q` |

### 1.4 Upgrade 版本轉換

| 模式 | 轉換規則 | 範例 |
|------|----------|------|
| `realtek/android-Y/mp.google-refplus.upgrade-X.rtdZZZZ` | `realtek/android-Y/premp.google-refplus.upgrade-X.rtdZZZZ` | `realtek/android-14/mp.google-refplus.upgrade-11.rtd2851a` → `realtek/android-14/premp.google-refplus.upgrade-11.rtd2851a` |
| `realtek/android-Y/mp.google-refplus.upgrade-X` | `realtek/android-Y/premp.google-refplus.upgrade-X` | `realtek/android-14/mp.google-refplus.upgrade-11` → `realtek/android-14/premp.google-refplus.upgrade-11` |

### 1.5 跳過轉換的項目

- **Google 項目**：以 `google/` 開頭的項目保持不變
- **Git Tags**：以 `refs/tags/` 開頭的項目保持不變

### 1.6 智能備案轉換

如果沒有匹配到精確規則：

1. **包含 `mp.google-refplus`**：替換為 `premp.google-refplus`
2. **包含 `/master` 且有 Android 版本**：轉換為對應 Android 版本的 premp
3. **其他情況**：使用預設 `realtek/android-14/premp.google-refplus`

---

## 🔄 2. PreMP to Wave 轉換邏輯

### 2.1 轉換規則

**核心邏輯**：將 `premp.google-refplus` 關鍵字替換為 `mp.google-refplus.wave`

| 原始 Revision | 轉換後 Revision |
|---------------|-----------------|
| `realtek/android-14/premp.google-refplus` | `realtek/android-14/mp.google-refplus.wave` |
| `realtek/android-14/premp.google-refplus.rtd2851a` | `realtek/android-14/mp.google-refplus.wave.rtd2851a` |
| `realtek/linux-5.15/android-14/premp.google-refplus` | `realtek/linux-5.15/android-14/mp.google-refplus.wave` |
| `realtek/android-14/premp.google-refplus.upgrade-11` | `realtek/android-14/mp.google-refplus.wave.upgrade-11` |

### 2.2 實作方式

```python
def _convert_premp_to_mp(self, revision: str) -> str:
    """premp → mp 轉換規則"""
    return revision.replace('premp.google-refplus', 'mp.google-refplus.wave')
```

---

## 🔄 3. Wave to Wave Backup 轉換邏輯

### 3.1 轉換規則

**核心邏輯**：將 `mp.google-refplus.wave` 關鍵字替換為 `mp.google-refplus.wave.backup`

| 原始 Revision | 轉換後 Revision |
|---------------|-----------------|
| `realtek/android-14/mp.google-refplus.wave` | `realtek/android-14/mp.google-refplus.wave.backup` |
| `realtek/android-14/mp.google-refplus.wave.rtd2851a` | `realtek/android-14/mp.google-refplus.wave.backup.rtd2851a` |
| `realtek/linux-5.15/android-14/mp.google-refplus.wave` | `realtek/linux-5.15/android-14/mp.google-refplus.wave.backup` |

### 3.2 實作方式

```python
def _convert_mp_to_mpbackup(self, revision: str) -> str:
    """mp → mpbackup 轉換規則"""
    return revision.replace('mp.google-refplus.wave', 'mp.google-refplus.wave.backup')
```

---

## 🎯 4. 特殊處理邏輯

### 4.1 Hash vs Branch Name 處理

#### 判斷邏輯
```python
def _is_revision_hash(self, revision: str) -> bool:
    """判斷是否為 commit hash"""
    if len(revision) == 40 and all(c in '0123456789abcdefABCDEF' for c in revision):
        return True  # 40字符十六進制 = Hash
    return False     # 其他情況 = Branch Name
```

#### 處理方式

| Revision 類型 | 使用欄位 | 處理邏輯 | 範例 |
|---------------|----------|----------|------|
| **Hash** | `upstream` | 使用 upstream 欄位進行轉換和建立連結 | `revision="5dccbb8e..."` + `upstream="realtek/master"` → 使用 `upstream` |
| **Branch Name** | `revision` | 直接使用 revision 欄位 | `revision="realtek/master"` → 直接使用 `revision` |

### 4.2 Default Revision 處理

當專案的 `revision` 為空且 `remote="rtk"` 時，使用 `<default>` 標籤的 revision：

```xml
<default remote="rtk" revision="refs/tags/u-tv-keystone-rtk-refplus-wave4-release-UKR9.20250803" sync-j="2" sync-c="true"/>
```

#### 處理邏輯
1. 讀取 `<default>` 標籤的 `remote` 和 `revision`
2. 遍歷所有 `<project>` 元素
3. 如果 `project.revision` 為空且 `project.remote="rtk"`
4. 自動應用 `default.revision`

---

## 📊 5. 實際轉換範例

### 5.1 完整轉換鏈範例

```
原始: realtek/master
  ↓ master_to_premp
步驟1: realtek/android-14/premp.google-refplus
  ↓ premp_to_mp  
步驟2: realtek/android-14/mp.google-refplus.wave
  ↓ mp_to_mpbackup
步驟3: realtek/android-14/mp.google-refplus.wave.backup
```

### 5.2 晶片特定轉換範例

```
原始: realtek/merlin7/master
  ↓ master_to_premp (晶片轉換)
步驟1: realtek/android-14/premp.google-refplus.rtd6748
  ↓ premp_to_mp
步驟2: realtek/android-14/mp.google-refplus.wave.rtd6748
  ↓ mp_to_mpbackup  
步驟3: realtek/android-14/mp.google-refplus.wave.backup.rtd6748
```

### 5.3 Linux Kernel 轉換範例

```
原始: realtek/linux-5.15/android-14/master
  ↓ master_to_premp (Linux kernel 轉換)
步驟1: realtek/linux-5.15/android-14/premp.google-refplus
  ↓ premp_to_mp
步驟2: realtek/linux-5.15/android-14/mp.google-refplus.wave
  ↓ mp_to_mpbackup
步驟3: realtek/linux-5.15/android-14/mp.google-refplus.wave.backup
```

---

## 🔧 6. 實作細節

### 6.1 轉換方法對應

| 轉換類型 | 方法名稱 | 說明 |
|----------|----------|------|
| `master_vs_premp` | `_convert_master_to_premp()` | 複雜的精確匹配 + 模式匹配 |
| `premp_vs_mp` | `_convert_premp_to_mp()` | 簡單的字串替換 |
| `mp_vs_mpbackup` | `_convert_mp_to_mpbackup()` | 簡單的字串替換 |

### 6.2 調用流程

```python
def _convert_revision_by_type(self, revision: str, process_type: str) -> str:
    if process_type == 'master_vs_premp':
        return self._convert_master_to_premp(revision)
    elif process_type == 'premp_vs_mp':
        return self._convert_premp_to_mp(revision)
    elif process_type == 'mp_vs_mpbackup':
        return self._convert_mp_to_mpbackup(revision)
    else:
        return revision
```

### 6.3 有效 Revision 取得邏輯

```python
def _get_effective_revision_for_conversion(self, project: Dict) -> str:
    revision = project.get('revision', '')
    upstream = project.get('upstream', '')
    
    if self._is_revision_hash(revision):
        # Hash → 使用 upstream
        return upstream if upstream else ''
    else:
        # Branch Name → 直接使用 revision
        return revision
```

---

## 📈 7. 統計和驗證

### 7.1 轉換統計項目

- 總專案數
- Hash revision 數量
- Branch revision 數量  
- 使用 upstream 轉換的數量
- 使用 default revision 的數量
- 轉換成功數量
- 轉換失敗數量

### 7.2 驗證機制

1. **revision_diff**：比對轉換後分支與目標分支的 revision hash
2. **target_branch_exists**：檢查目標分支是否存在於 Gerrit
3. **branch_link**：生成 Gerrit 連結驗證可訪問性

---

## 🎯 8. 重要注意事項

### 8.1 同步要求

⚠️ **feature_two.py** 和 **feature_three.py** 必須使用完全相同的轉換邏輯，確保：
- 映射表生成（feature_two）與實際轉換（feature_three）結果一致
- 測試驗證能正確反映實際轉換效果

### 8.2 維護建議

1. **新增轉換規則**：同時更新兩個檔案的轉換方法
2. **測試驗證**：使用 `test_manifest_conversion.py` 驗證轉換正確性
3. **調試模式**：啟用詳細日誌查看轉換過程

### 8.3 錯誤處理

- **跳過項目**：Google 項目和 Git Tags 自動跳過
- **備案轉換**：無法精確匹配時使用智能推斷
- **失敗記錄**：所有轉換失敗都記錄到 Excel 報告

---

## 📝 結語

此映射邏輯設計旨在自動化處理 Android manifest 檔案中的分支轉換，支援多種轉換情境和特殊處理需求。透過精確的規則匹配和智能備案機制，確保轉換的準確性和完整性。