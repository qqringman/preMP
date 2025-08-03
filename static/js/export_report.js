// 匯出報表頁面 JavaScript - 使用真實資料

let currentTaskId = null;
let currentData = null;
let selectedSheet = null;

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', () => {
    // 綁定函數到 window
    window.loadTaskData = loadTaskData;
    window.loadSheet = loadSheet;
    window.exportData = exportData;
    window.quickExport = quickExport;
    window.downloadFullReport = downloadFullReport;
    
    // 初始化
    initializePage();
});

// 初始化頁面
async function initializePage() {
    // 載入可用的任務列表
    await loadAvailableTasks();
    
    // 監聽任務選擇
    const taskSelector = document.getElementById('taskSelector');
    if (taskSelector) {
        taskSelector.addEventListener('change', (e) => {
            if (e.target.value) {
                loadTaskData(e.target.value);
            }
        });
    }
    
    // 監聽資料表選擇
    const sheetSelector = document.getElementById('sheetSelector');
    if (sheetSelector) {
        sheetSelector.addEventListener('change', (e) => {
            if (e.target.value) {
                loadSheet(e.target.value);
            }
        });
    }
}

// 載入可用的任務列表
async function loadAvailableTasks() {
    try {
        const response = await utils.apiRequest('/api/list-export-tasks');
        const tasks = response.tasks || [];
        
        const taskSelector = document.getElementById('taskSelector');
        taskSelector.innerHTML = '<option value="">請選擇任務...</option>';
        
        tasks.forEach(task => {
            const option = document.createElement('option');
            option.value = task.id;
            option.textContent = `${task.name} - ${new Date(task.timestamp).toLocaleString('zh-TW')}`;
            taskSelector.appendChild(option);
        });
        
        // 如果 URL 中有任務 ID，自動載入
        const urlParams = new URLSearchParams(window.location.search);
        const taskId = urlParams.get('task_id');
        if (taskId) {
            taskSelector.value = taskId;
            loadTaskData(taskId);
        }
        
    } catch (error) {
        console.error('Load tasks error:', error);
        showError('無法載入任務列表');
    }
}

// 載入任務資料
async function loadTaskData(taskId) {
    if (!taskId) return;
    
    currentTaskId = taskId;
    showLoading();
    
    try {
        const data = await utils.apiRequest(`/api/pivot-data/${taskId}`);
        
        if (!data || Object.keys(data).length === 0) {
            showEmpty();
            return;
        }
        
        currentData = data;
        
        // 更新資料表選擇器
        const sheetSelector = document.getElementById('sheetSelector');
        sheetSelector.innerHTML = '<option value="">請選擇資料表...</option>';
        
        Object.keys(data).forEach(sheetName => {
            const option = document.createElement('option');
            option.value = sheetName;
            option.textContent = getSheetDisplayName(sheetName);
            sheetSelector.appendChild(option);
        });
        
        // 顯示統計摘要
        showTaskSummary();
        
        // 預設載入第一個資料表
        if (Object.keys(data).length > 0) {
            sheetSelector.value = Object.keys(data)[0];
            loadSheet(Object.keys(data)[0]);
        }
        
    } catch (error) {
        console.error('Load task data error:', error);
        showError('無法載入任務資料');
    }
}

// 載入資料表
function loadSheet(sheetName) {
    if (!sheetName || !currentData) return;
    
    selectedSheet = sheetName;
    const sheetData = currentData[sheetName];
    
    if (!sheetData) {
        showEmpty();
        return;
    }
    
    // 顯示資料預覽
    showDataPreview(sheetData);
    
    // 更新統計
    updateStatistics(sheetData);
}

// 顯示資料預覽
function showDataPreview(sheetData) {
    const container = document.getElementById('previewContainer');
    
    if (!sheetData.data || sheetData.data.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>此資料表沒有資料</p></div>';
        return;
    }
    
    // 建立表格
    let html = '<div class="data-table-wrapper"><table class="data-table">';
    
    // 表頭
    const columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
    html += '<thead><tr>';
    columns.forEach(col => {
        html += `<th>${col}</th>`;
    });
    html += '</tr></thead>';
    
    // 表格內容 (只顯示前 20 筆)
    html += '<tbody>';
    const previewData = sheetData.data.slice(0, 20);
    
    previewData.forEach(row => {
        html += '<tr>';
        columns.forEach(col => {
            const value = row[col];
            let cellContent = value !== null && value !== undefined ? value : '';
            
            // 特殊格式處理
            if (col === 'has_wave' || col === 'is_different') {
                if (value === 'Y') {
                    cellContent = '<span class="badge badge-success">Y</span>';
                } else {
                    cellContent = '<span class="badge badge-default">N</span>';
                }
            } else if (col === '狀態') {
                if (value === '新增') {
                    cellContent = '<span class="badge badge-success">新增</span>';
                } else if (value === '刪除') {
                    cellContent = '<span class="badge badge-danger">刪除</span>';
                } else {
                    cellContent = `<span class="badge badge-warning">${value}</span>`;
                }
            }
            
            html += `<td>${cellContent}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</tbody></table></div>';
    
    // 如果資料超過 20 筆，顯示提示
    if (sheetData.data.length > 20) {
        html += `<div class="export-hint">
            <i class="fas fa-info-circle"></i>
            <span>預覽顯示前 20 筆資料，共 ${sheetData.data.length} 筆</span>
        </div>`;
    }
    
    container.innerHTML = html;
}

// 顯示任務摘要
function showTaskSummary() {
    const container = document.getElementById('taskSummary');
    if (!container || !currentData) return;
    
    let totalRows = 0;
    let totalSheets = Object.keys(currentData).length;
    
    // 計算總資料筆數
    Object.values(currentData).forEach(sheet => {
        if (sheet.data) {
            totalRows += sheet.data.length;
        }
    });
    
    container.innerHTML = `
        <div class="stats-summary">
            <div class="stat-card total">
                <div class="stat-icon">
                    <i class="fas fa-table"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${totalSheets}</div>
                    <div class="stat-label">資料表</div>
                </div>
            </div>
            <div class="stat-card success">
                <div class="stat-icon">
                    <i class="fas fa-database"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${totalRows}</div>
                    <div class="stat-label">總資料筆數</div>
                </div>
            </div>
        </div>
    `;
}

// 更新統計資料
function updateStatistics(sheetData) {
    const container = document.getElementById('sheetStatistics');
    if (!container) return;
    
    const stats = [];
    
    // 基本統計
    stats.push({
        label: '資料筆數',
        value: sheetData.data ? sheetData.data.length : 0,
        icon: 'fa-list',
        type: 'total'
    });
    
    stats.push({
        label: '欄位數',
        value: sheetData.columns ? sheetData.columns.length : 0,
        icon: 'fa-columns',
        type: 'total'
    });
    
    // 特定資料表的統計
    if (selectedSheet === 'revision_diff' && sheetData.data) {
        const hasWaveY = sheetData.data.filter(row => row.has_wave === 'Y').length;
        const hasWaveN = sheetData.data.filter(row => row.has_wave === 'N').length;
        
        if (hasWaveY > 0) {
            stats.push({
                label: '包含 Wave',
                value: hasWaveY,
                icon: 'fa-check-circle',
                type: 'success'
            });
        }
        
        if (hasWaveN > 0) {
            stats.push({
                label: '缺少 Wave',
                value: hasWaveN,
                icon: 'fa-exclamation-triangle',
                type: 'warning'
            });
        }
    }
    
    if (selectedSheet === 'lost_project' && sheetData.data) {
        const added = sheetData.data.filter(row => row['狀態'] === '新增').length;
        const deleted = sheetData.data.filter(row => row['狀態'] === '刪除').length;
        
        if (added > 0) {
            stats.push({
                label: '新增專案',
                value: added,
                icon: 'fa-plus-circle',
                type: 'success'
            });
        }
        
        if (deleted > 0) {
            stats.push({
                label: '刪除專案',
                value: deleted,
                icon: 'fa-minus-circle',
                type: 'error'
            });
        }
    }
    
    // 渲染統計卡片
    let html = '<div class="stats-summary">';
    stats.forEach(stat => {
        html += `
            <div class="stat-card ${stat.type}">
                <div class="stat-icon">
                    <i class="fas ${stat.icon}"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stat.value}</div>
                    <div class="stat-label">${stat.label}</div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

// 取得資料表顯示名稱
function getSheetDisplayName(sheetName) {
    const displayNames = {
        'revision_diff': 'Revision 差異',
        'branch_error': '分支錯誤',
        'lost_project': '新增/刪除專案',
        'version_diff': '版本檔案差異',
        '無法比對': '無法比對的模組',
        '摘要': '比對摘要',
        'all_scenarios': '所有情境摘要',
        'master_vs_premp': 'Master vs PreMP',
        'premp_vs_wave': 'PreMP vs Wave',
        'wave_vs_backup': 'Wave vs Backup'
    };
    return displayNames[sheetName] || sheetName;
}

// 匯出資料
async function exportData(format) {
    if (!currentTaskId) {
        utils.showNotification('請先選擇任務', 'error');
        return;
    }
    
    try {
        if (format === 'current-excel' && selectedSheet) {
            // 匯出當前資料表
            window.location.href = `/api/export-sheet/${currentTaskId}/${selectedSheet}?format=excel`;
        } else if (format === 'all-excel') {
            // 匯出所有資料表
            window.location.href = `/api/export-excel/${currentTaskId}`;
        } else if (format === 'pdf') {
            // 匯出 PDF
            window.location.href = `/api/export-pdf/${currentTaskId}`;
        } else if (format === 'html') {
            // 匯出 HTML
            exportHTML();
        } else if (format === 'zip') {
            // 下載完整 ZIP
            downloadFullReport();
        }
        
        utils.showNotification('開始匯出...', 'info');
        
    } catch (error) {
        console.error('Export error:', error);
        utils.showNotification('匯出失敗', 'error');
    }
}

// 快速匯出
function quickExport(format) {
    exportData(format);
}

// 匯出 HTML
function exportHTML() {
    if (!currentData || !selectedSheet) {
        utils.showNotification('請先選擇資料表', 'error');
        return;
    }
    
    const sheetData = currentData[selectedSheet];
    if (!sheetData) return;
    
    // 建立 HTML 內容
    let htmlContent = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${getSheetDisplayName(selectedSheet)} - 匯出報表</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #1A237E; margin-bottom: 10px; }
        .info { color: #666; margin-bottom: 30px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #2196F3; color: white; padding: 12px; text-align: left; font-weight: 600; }
        td { padding: 10px; border-bottom: 1px solid #e0e0e0; }
        tr:hover { background: #f5f5f5; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.85em; font-weight: 500; }
        .badge-success { background: #E8F5E9; color: #2E7D32; }
        .badge-warning { background: #FFF3E0; color: #F57C00; }
        .badge-danger { background: #FFEBEE; color: #C62828; }
        .badge-default { background: #F5F5F5; color: #757575; }
        .footer { margin-top: 30px; text-align: center; color: #999; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>${getSheetDisplayName(selectedSheet)}</h1>
        <div class="info">
            <p>匯出時間：${new Date().toLocaleString('zh-TW')}</p>
            <p>資料筆數：${sheetData.data ? sheetData.data.length : 0} 筆</p>
        </div>
`;
    
    // 建立表格
    const columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
    
    htmlContent += '<table><thead><tr>';
    columns.forEach(col => {
        htmlContent += `<th>${col}</th>`;
    });
    htmlContent += '</tr></thead><tbody>';
    
    if (sheetData.data) {
        sheetData.data.forEach(row => {
            htmlContent += '<tr>';
            columns.forEach(col => {
                let value = row[col];
                
                // 特殊格式處理
                if (col === 'has_wave' || col === 'is_different') {
                    if (value === 'Y') {
                        value = '<span class="badge badge-success">Y</span>';
                    } else {
                        value = '<span class="badge badge-default">N</span>';
                    }
                } else if (col === '狀態') {
                    if (value === '新增') {
                        value = '<span class="badge badge-success">新增</span>';
                    } else if (value === '刪除') {
                        value = '<span class="badge badge-danger">刪除</span>';
                    } else if (value) {
                        value = `<span class="badge badge-warning">${value}</span>`;
                    }
                } else {
                    value = value !== null && value !== undefined ? value : '';
                }
                
                htmlContent += `<td>${value}</td>`;
            });
            htmlContent += '</tr>';
        });
    }
    
    htmlContent += `
        </tbody></table>
        <div class="footer">
            <p>由 SFTP 下載與比較系統 自動產生</p>
        </div>
    </div>
</body>
</html>`;
    
    // 下載 HTML 檔案
    const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedSheet}_${currentTaskId}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// 下載完整報表
function downloadFullReport() {
    if (!currentTaskId) {
        utils.showNotification('請先選擇任務', 'error');
        return;
    }
    
    window.location.href = `/api/export-zip/${currentTaskId}`;
}

// 顯示載入中
function showLoading() {
    const container = document.getElementById('previewContainer');
    container.innerHTML = `
        <div class="loading-state">
            <i class="fas fa-spinner fa-spin"></i>
            <h3>載入中...</h3>
            <p>正在讀取資料，請稍候</p>
        </div>
    `;
}

// 顯示空狀態
function showEmpty() {
    const container = document.getElementById('previewContainer');
    container.innerHTML = `
        <div class="empty-state">
            <i class="fas fa-inbox"></i>
            <h3>沒有資料</h3>
            <p>請選擇任務和資料表來查看內容</p>
        </div>
    `;
}

// 顯示錯誤
function showError(message) {
    const container = document.getElementById('previewContainer');
    container.innerHTML = `
        <div class="empty-state">
            <i class="fas fa-exclamation-triangle" style="color: var(--danger);"></i>
            <h3>載入失敗</h3>
            <p>${message}</p>
        </div>
    `;
}

// 初始化時顯示空狀態
showEmpty();