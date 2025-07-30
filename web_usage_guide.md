# SFTP 下載與比較系統 - Web 介面使用說明

## 系統概述

本系統提供了完整的 Web 介面，支援：
1. **一步到位處理**：自動執行下載→比對→打包全流程
2. **全情境比對**：支援 Master vs PreMP、PreMP vs Wave、Wave vs Wave.backup
3. **互動式樞紐分析**：類似 Excel 的拖拉式資料分析功能
4. **多格式匯出**：支援 Excel、HTML、ZIP 格式輸出

## 系統架構

```
sftp_compare_system/
├── web_app.py              # Flask 主程式
├── templates/              # HTML 模板
│   ├── base.html          # 基礎模板
│   ├── index.html         # 首頁
│   ├── one_step.html      # 一步到位頁面
│   ├── compare.html       # 比較頁面
│   └── results.html       # 結果頁面（含樞紐分析）
├── static/                 # 靜態資源
│   ├── css/
│   │   └── style.css      # 北歐藍風格樣式
│   └── js/
│       ├── main.js        # 主要 JavaScript
│       └── one-step.js    # 一步到位功能
└── [原有系統檔案]
```

## 安裝與執行

### 1. 安裝額外依賴

```bash
# 安裝 Flask 相關套件
pip install flask flask-socketio pandas openpyxl

# 或使用 requirements.txt
pip install -r requirements_web.txt
```

### 2. 創建 requirements_web.txt

```txt
# Web 介面額外需求
flask>=2.0.0
flask-socketio>=5.0.0
python-socketio>=5.0.0
eventlet>=0.30.0  # 用於 WebSocket 支援

# 原有需求
paramiko>=2.7.0
pandas>=1.2.0
openpyxl>=3.0.0
lxml>=4.6.0
```

### 3. 啟動 Web 伺服器

```bash
# 開發模式
python web_app.py

# 生產模式（使用 gunicorn）
pip install gunicorn
gunicorn -k eventlet -w 1 --bind 0.0.0.0:5000 web_app:app
```

伺服器預設在 http://localhost:5000 啟動

## 功能使用指南

### 1. 首頁

訪問 http://localhost:5000 即可看到系統首頁，提供：
- 系統功能概覽
- 快速導航到各功能
- 最近活動記錄
- 處理統計資訊

### 2. 一步到位功能

#### 步驟 1：上傳 Excel
- 支援拖曳上傳或點擊選擇
- 檔案限制：.xlsx 格式，最大 16MB

#### 步驟 2：配置 SFTP
- 預設使用 config.py 設定
- 可自訂連線參數

#### 步驟 3：執行處理
- 點擊「開始執行」
- 即時顯示處理進度
- 自動執行：下載 → 比對 → 打包

#### 步驟 4：查看結果
- 顯示處理摘要
- 提供多種下載選項

### 3. 比較功能

#### 選擇來源目錄
- 自動列出可用的下載目錄
- 支援重新整理目錄列表

#### 選擇比對情境
- **執行所有比對**：自動執行三種情境
- **Master vs PreMP**：比較主版本與預量產
- **PreMP vs Wave**：比較預量產與 Wave
- **Wave vs Backup**：比較 Wave 與備份

#### 查看結果
- 即時進度追蹤
- 統計圖表展示
- 快速匯出功能

### 4. 結果報表（樞紐分析）

#### 資料檢視
- **表格模式**：標準資料表格顯示
  - 點擊欄位標題排序
  - 重要欄位自動標色
  - 支援連結跳轉

- **樞紐分析模式**：互動式資料分析
  - 拖曳欄位到行/列區域
  - 選擇彙總函數（總和、平均、計數等）
  - 支援多維度交叉分析
  - 可匯出分析結果

#### 資料篩選
- 點擊右下角篩選按鈕
- 支援多選篩選
- 即時套用篩選條件

#### 匯出功能
- **Excel**：完整的 .xlsx 報表
- **HTML**：網頁格式報表
- **ZIP**：包含所有結果檔案

## API 端點說明

### 檔案上傳
```
POST /api/upload
Content-Type: multipart/form-data
Body: file (Excel 檔案)
```

### 一步到位處理
```
POST /api/one-step
Content-Type: application/json
Body: {
    "excel_file": "檔案路徑",
    "sftp_config": {
        "host": "選填",
        "port": "選填",
        "username": "選填",
        "password": "選填"
    }
}
```

### 比對處理
```
POST /api/compare
Content-Type: application/json
Body: {
    "source_dir": "來源目錄",
    "scenarios": "all|master_vs_premp|premp_vs_wave|wave_vs_backup"
}
```

### 取得任務狀態
```
GET /api/status/{task_id}
```

### 匯出功能
```
GET /api/export-excel/{task_id}
GET /api/export-html/{task_id}
GET /api/export-zip/{task_id}
```

### 樞紐分析資料
```
GET /api/pivot-data/{task_id}
```

## 特色功能

### 1. 即時進度追蹤
- 使用 WebSocket (Socket.IO) 實現
- 不需要手動重新整理
- 詳細的處理日誌

### 2. 智能資料分析
- 自動統計關鍵指標
- 視覺化圖表展示
- 支援深度資料探索

### 3. 北歐藍設計風格
- 簡潔清爽的介面
- 柔和的藍色系配色
- 優雅的動畫效果
- 響應式設計

### 4. 樞紐分析功能
類似 Excel 的操作體驗：
- 拖放欄位建立分析
- 多種彙總方式
- 即時計算結果
- 支援圖表輸出

## 故障排除

### 1. 無法連線到伺服器
- 檢查防火牆設定
- 確認 5000 埠未被占用
- 檢查 Python 環境

### 2. WebSocket 連線失敗
- 確保安裝了 eventlet
- 檢查瀏覽器是否支援 WebSocket
- 嘗試使用不同瀏覽器

### 3. 檔案上傳失敗
- 檢查檔案大小限制（16MB）
- 確認檔案格式為 .xlsx
- 檢查 uploads 目錄權限

### 4. 樞紐分析無法載入
- 確保網路連線正常（需要載入 CDN 資源）
- 檢查瀏覽器控制台錯誤
- 嘗試重新整理頁面

## 進階設定

### 修改上傳限制
```python
# 在 web_app.py 中
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB
```

### 自訂樣式主題
修改 `static/css/style.css` 中的 CSS 變數：
```css
:root {
    --nordic-blue-600: #2196F3;  /* 主色調 */
    --nordic-gray-50: #FAFBFC;   /* 背景色 */
    /* 更多顏色設定... */
}
```

### 擴充樞紐分析功能
在 `templates/results.html` 中修改 PivotTable 設定：
```javascript
$(container).pivotUI(sheetData.data, {
    rows: ["預設行"],
    cols: ["預設列"],
    aggregatorName: "總和",
    vals: ["數值欄位"],
    // 更多選項...
});
```

## 部署建議

### 1. 使用 Nginx 反向代理
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 2. 使用 Supervisor 管理程序
```ini
[program:sftp_compare]
command=/path/to/venv/bin/gunicorn -k eventlet -w 1 --bind 0.0.0.0:5000 web_app:app
directory=/path/to/sftp_compare_system
user=www-data
autostart=true
autorestart=true
```

### 3. 安全性建議
- 使用 HTTPS
- 設定 CSRF 保護
- 限制上傳檔案類型
- 實作使用者認證

## 總結

本 Web 介面提供了完整的圖形化操作體驗，讓使用者能夠：
1. 輕鬆執行複雜的處理流程
2. 即時監控處理進度
3. 互動式分析比對結果
4. 快速匯出各種格式報表

系統採用現代化的技術架構，提供流暢的使用體驗和美觀的視覺設計。
