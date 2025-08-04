// 結果報表頁面 JavaScript - 使用真實資料

const taskId = window.location.pathname.split('/').pop();
let currentData = null;
let currentSheet = null;
let pivotMode = false;
let filters = {};

console.log('Task ID:', taskId);  // 除錯用

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('頁面載入完成，開始載入資料...');
    loadPivotData();
});

// 載入樞紐分析資料
async function loadPivotData() {
    try {
        // 顯示載入中狀態
        showLoading();
        
        console.log(`正在載入任務 ${taskId} 的資料...`);
        
        const response = await fetch(`/api/pivot-data/${taskId}`);
        console.log('API 回應狀態:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('收到的資料:', data);
        
        if (!data || Object.keys(data).length === 0) {
            // 如果沒有資料，顯示提示訊息
            console.log('沒有找到資料');
            showNoDataMessage();
            return;
        }
        
        currentData = data;
        console.log('資料載入成功，工作表數量:', Object.keys(data).length);
        
        // 填充資料表選項
        const selector = document.getElementById('sheetSelector');
        selector.innerHTML = '';
        
        // 按照特定順序顯示資料表
        const sheetOrder = ['revision_diff', 'branch_error', 'lost_project', 'version_diff', '無法比對', '摘要'];
        const orderedSheets = [];
        
        // 先加入已定義順序的資料表
        sheetOrder.forEach(sheetName => {
            if (data[sheetName]) {
                orderedSheets.push(sheetName);
            }
        });
        
        // 再加入其他資料表
        Object.keys(data).forEach(sheetName => {
            if (!orderedSheets.includes(sheetName)) {
                orderedSheets.push(sheetName);
            }
        });
        
        // 填充選擇器
        orderedSheets.forEach(sheetName => {
            const option = document.createElement('option');
            option.value = sheetName;
            option.textContent = getSheetDisplayName(sheetName);
            selector.appendChild(option);
        });
        
        // 載入第一個資料表
        if (orderedSheets.length > 0) {
            console.log('載入第一個資料表:', orderedSheets[0]);
            loadSheet(orderedSheets[0]);
        }
        
    } catch (error) {
        console.error('載入資料錯誤:', error);
        showErrorMessage(error.message);
    }
}

// 顯示載入中
function showLoading() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="100%" class="empty-message">
                <div class="loading">
                    <i class="fas fa-spinner fa-spin"></i>
                    <p>載入資料中...</p>
                </div>
            </td>
        </tr>
    `;
}

// 顯示無資料訊息
function showNoDataMessage() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="100%" class="empty-message">
                <div class="no-data-message">
                    <i class="fas fa-inbox"></i>
                    <h3>暫無資料可顯示</h3>
                    <p>此任務可能還在處理中，或尚未產生報表。</p>
                    <button class="btn btn-primary" onclick="location.reload()">
                        <i class="fas fa-sync"></i> 重新載入
                    </button>
                </div>
            </td>
        </tr>
    `;
    
    // 隱藏統計和圖表
    document.getElementById('statsGrid').innerHTML = '';
}

// 顯示錯誤訊息
function showErrorMessage(message = '無法載入報表資料') {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="100%" class="empty-message">
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>載入資料失敗</h3>
                    <p>${message}</p>
                    <div class="action-buttons">
                        <button class="btn btn-primary" onclick="location.reload()">
                            <i class="fas fa-sync"></i> 重試
                        </button>
                        <button class="btn btn-outline" onclick="window.history.back()">
                            <i class="fas fa-arrow-left"></i> 返回
                        </button>
                    </div>
                </div>
            </td>
        </tr>
    `;
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

// 載入資料表
function loadSheet(sheetName) {
    console.log('載入資料表:', sheetName);
    
    currentSheet = sheetName;
    const sheetData = currentData[sheetName];
    
    if (!sheetData) {
        console.error('找不到資料表:', sheetName);
        return;
    }
    
    console.log(`資料表 ${sheetName} 有 ${sheetData.data ? sheetData.data.length : 0} 筆資料`);
    
    // 更新選擇器
    document.getElementById('sheetSelector').value = sheetName;
    
    // 更新統計資料
    updateStatistics(sheetData);
    
    // 生成篩選器
    generateFilters(sheetData);
    
    if (pivotMode) {
        // 樞紐分析模式
        renderPivotTable(sheetData);
    } else {
        // 一般表格模式
        renderDataTable(sheetData);
    }
    
    // 繪製圖表
    drawDataCharts(sheetData);
}

// 渲染資料表格
function renderDataTable(sheetData) {
    const thead = document.getElementById('tableHead');
    const tbody = document.getElementById('tableBody');
    
    // 清空表格
    thead.innerHTML = '';
    tbody.innerHTML = '';
    
    if (!sheetData.data || sheetData.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="100%" class="empty-message">此資料表沒有資料</td></tr>';
        return;
    }
    
    // 取得欄位（從資料或定義中）
    const columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
    console.log('欄位:', columns);
    
    // 建立表頭
    const headerRow = document.createElement('tr');
    columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        th.onclick = () => sortTable(col);
        th.style.cursor = 'pointer';
        
        // 標記重要欄位
        if (['base_short', 'base_revision', 'compare_short', 'compare_revision', 'problem', '狀態', 'is_different'].includes(col)) {
            th.classList.add('highlight-header');
        }
        
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    
    // 建立表格內容
    const filteredData = applyDataFilters(sheetData.data);
    console.log(`顯示 ${filteredData.length} 筆資料`);
    
    filteredData.forEach((row, index) => {
        const tr = document.createElement('tr');
        columns.forEach(col => {
            const td = document.createElement('td');
            const value = row[col];
            
            // 特殊格式處理
            if (col.includes('link') && value && typeof value === 'string' && value.startsWith('http')) {
                td.innerHTML = `<a href="${value}" target="_blank" class="link">
                    <i class="fas fa-external-link-alt"></i> 查看
                </a>`;
            } else if (col === 'has_wave' || col === 'is_different') {
                const badgeClass = value === 'Y' ? 'badge-success' : 'badge-default';
                td.innerHTML = `<span class="badge ${badgeClass}">${value || 'N'}</span>`;
            } else if (col === '狀態') {
                let badgeClass = 'badge-default';
                if (value === '新增') badgeClass = 'badge-success';
                else if (value === '刪除') badgeClass = 'badge-danger';
                else if (value === '修改') badgeClass = 'badge-warning';
                td.innerHTML = `<span class="badge ${badgeClass}">${value || ''}</span>`;
            } else if (col === 'problem' && value) {
                td.innerHTML = `<span class="text-danger font-weight-bold">${value}</span>`;
            } else {
                td.textContent = value !== null && value !== undefined ? value : '';
            }
            
            // 標記重要欄位內容
            if (['base_short', 'base_revision', 'compare_short', 'compare_revision'].includes(col) && value) {
                td.classList.add('highlight-red');
            }
            
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    
    // 如果沒有資料顯示
    if (filteredData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="100%" class="empty-message">沒有符合篩選條件的資料</td></tr>';
    }
}

// 渲染樞紐分析表
function renderPivotTable(sheetData) {
    const container = document.getElementById('pivotContainer');
    container.innerHTML = '';
    
    if (!sheetData.data || sheetData.data.length === 0) {
        container.innerHTML = '<div class="empty-message">沒有資料可供分析</div>';
        return;
    }
    
    // 使用 PivotTable.js
    try {
        $(container).pivotUI(sheetData.data, {
            rows: [],
            cols: [],
            aggregatorName: "計數",
            rendererName: "表格",
            unusedAttrsVertical: true,
            renderers: $.extend(
                $.pivotUtilities.renderers,
                $.pivotUtilities.c3_renderers,
                $.pivotUtilities.d3_renderers
            ),
            localeStrings: {
                renderError: "渲染錯誤",
                computeError: "計算錯誤",
                uiRenderError: "UI 渲染錯誤",
                selectAll: "全選",
                selectNone: "全不選",
                tooMany: "(太多值無法顯示)",
                filterResults: "篩選結果",
                totals: "總計",
                vs: "vs",
                by: "by"
            }
        });
    } catch (error) {
        console.error('樞紐分析錯誤:', error);
        container.innerHTML = '<div class="error-message">樞紐分析表載入失敗</div>';
    }
}

// 切換樞紐分析模式
function togglePivotMode() {
    pivotMode = !pivotMode;
    
    document.getElementById('tableView').classList.toggle('hidden', pivotMode);
    document.getElementById('pivotView').classList.toggle('hidden', !pivotMode);
    document.getElementById('pivotToggleText').textContent = pivotMode ? '切換表格檢視' : '切換樞紐分析';
    
    if (currentSheet) {
        loadSheet(currentSheet);
    }
}

// 更新統計資料
function updateStatistics(sheetData) {
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.innerHTML = '';
    
    if (!sheetData.data || sheetData.data.length === 0) return;
    
    // 計算基本統計
    const stats = [
        {
            label: '總筆數',
            value: sheetData.data.length,
            icon: 'fa-list',
            color: 'blue'
        },
        {
            label: '欄位數',
            value: sheetData.columns ? sheetData.columns.length : Object.keys(sheetData.data[0] || {}).length,
            icon: 'fa-columns',
            color: 'blue'
        }
    ];
    
    // 特定資料表的統計
    if (currentSheet === 'revision_diff') {
        const uniqueModules = new Set(sheetData.data.map(row => row.module).filter(m => m));
        const hasWaveY = sheetData.data.filter(row => row.has_wave === 'Y').length;
        const hasWaveN = sheetData.data.filter(row => row.has_wave === 'N').length;
        
        stats.push({
            label: '模組數',
            value: uniqueModules.size,
            icon: 'fa-cube',
            color: 'purple'
        });
        
        if (hasWaveY > 0) {
            stats.push({
                label: '包含 Wave',
                value: hasWaveY,
                icon: 'fa-check-circle',
                color: 'success'
            });
        }
        
        if (hasWaveN > 0) {
            stats.push({
                label: '缺少 Wave',
                value: hasWaveN,
                icon: 'fa-exclamation-triangle',
                color: 'warning'
            });
        }
    }
    
    if (currentSheet === 'branch_error') {
        const hasWaveN = sheetData.data.filter(row => row.has_wave === 'N').length;
        if (hasWaveN > 0) {
            stats.push({
                label: '需修正',
                value: hasWaveN,
                icon: 'fa-exclamation-triangle',
                color: 'warning'
            });
        }
    }
    
    if (currentSheet === 'lost_project') {
        const added = sheetData.data.filter(row => row['狀態'] === '新增').length;
        const deleted = sheetData.data.filter(row => row['狀態'] === '刪除').length;
        
        if (added > 0) {
            stats.push({
                label: '新增專案',
                value: added,
                icon: 'fa-plus-circle',
                color: 'success'
            });
        }
        if (deleted > 0) {
            stats.push({
                label: '刪除專案',
                value: deleted,
                icon: 'fa-minus-circle',
                color: 'danger'
            });
        }
    }
    
    // 渲染統計卡片
    stats.forEach(stat => {
        const card = document.createElement('div');
        card.className = `stat-card ${stat.color || ''}`;
        card.innerHTML = `
            <div class="stat-icon">
                <i class="fas ${stat.icon}"></i>
            </div>
            <div class="stat-content">
                <div class="stat-value">${stat.value}</div>
                <div class="stat-label">${stat.label}</div>
            </div>
        `;
        statsGrid.appendChild(card);
    });
}

// 生成篩選器
function generateFilters(sheetData) {
    const filterContent = document.getElementById('filterContent');
    filterContent.innerHTML = '';
    
    const columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
    
    // 為每個欄位生成篩選器
    columns.forEach(col => {
        // 跳過某些欄位
        if (col.includes('link') || col.includes('content') || col.includes('revision')) return;
        
        // 取得唯一值
        const uniqueValues = [...new Set(sheetData.data.map(row => row[col]))].filter(v => v !== null && v !== undefined);
        
        if (uniqueValues.length > 0 && uniqueValues.length < 50) {
            const filterGroup = document.createElement('div');
            filterGroup.className = 'filter-group';
            filterGroup.innerHTML = `
                <label class="filter-label">${col}</label>
                <select class="filter-select" multiple data-column="${col}">
                    ${uniqueValues.map(val => `
                        <option value="${val}">${val}</option>
                    `).join('')}
                </select>
            `;
            filterContent.appendChild(filterGroup);
        }
    });
    
    // 如果沒有可篩選的欄位
    if (filterContent.children.length === 0) {
        filterContent.innerHTML = '<p class="text-muted text-center">沒有可篩選的欄位</p>';
    }
}

// 套用篩選器
function applyFilters() {
    // 收集篩選條件
    filters = {};
    document.querySelectorAll('.filter-select').forEach(select => {
        const column = select.dataset.column;
        const selectedValues = Array.from(select.selectedOptions).map(opt => opt.value);
        if (selectedValues.length > 0) {
            filters[column] = selectedValues;
        }
    });
    
    // 重新載入資料
    if (currentSheet) {
        loadSheet(currentSheet);
    }
    
    utils.showNotification('已套用篩選', 'success');
    
    // 關閉篩選面板
    document.getElementById('filterPanel').classList.remove('show');
}

// 清除篩選器
function clearFilters() {
    filters = {};
    document.querySelectorAll('.filter-select').forEach(select => {
        select.selectedIndex = -1;
    });
    
    if (currentSheet) {
        loadSheet(currentSheet);
    }
    
    utils.showNotification('已清除篩選', 'info');
}

// 套用資料篩選
function applyDataFilters(data) {
    if (Object.keys(filters).length === 0) return data;
    
    return data.filter(row => {
        for (const [column, values] of Object.entries(filters)) {
            const rowValue = row[column];
            if (!values.includes(String(rowValue))) {
                return false;
            }
        }
        return true;
    });
}

// 表格排序
let sortOrder = {};
function sortTable(column) {
    const order = sortOrder[column] === 'asc' ? 'desc' : 'asc';
    sortOrder[column] = order;
    
    const sheetData = currentData[currentSheet];
    if (!sheetData || !sheetData.data) return;
    
    sheetData.data.sort((a, b) => {
        const aVal = a[column];
        const bVal = b[column];
        
        // 處理 null 和 undefined
        if (aVal === null || aVal === undefined) return 1;
        if (bVal === null || bVal === undefined) return -1;
        
        // 數字排序
        if (typeof aVal === 'number' && typeof bVal === 'number') {
            return order === 'asc' ? aVal - bVal : bVal - aVal;
        }
        
        // 字串排序
        const aStr = String(aVal);
        const bStr = String(bVal);
        
        if (order === 'asc') {
            return aStr.localeCompare(bStr);
        } else {
            return bStr.localeCompare(aStr);
        }
    });
    
    renderDataTable(sheetData);
}

// 繪製資料圖表
function drawDataCharts(sheetData) {
    if (!sheetData.data || sheetData.data.length === 0) return;
    
    // 清除舊圖表
    const charts = ['distributionChart', 'trendChart'];
    charts.forEach(chartId => {
        const canvas = document.getElementById(chartId);
        if (canvas) {
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 銷毀舊的 Chart 實例
            if (window[chartId + 'Instance']) {
                window[chartId + 'Instance'].destroy();
            }
        }
    });
    
    // 分布圖
    const distCanvas = document.getElementById('distributionChart');
    if (distCanvas) {
        const distCtx = distCanvas.getContext('2d');
        
        // 根據資料表類型決定圖表內容
        let chartData = {};
        
        if (currentSheet === 'revision_diff' || currentSheet === 'branch_error') {
            // 按模組統計
            sheetData.data.forEach(row => {
                const module = row.module;
                if (module) {
                    chartData[module] = (chartData[module] || 0) + 1;
                }
            });
        } else if (currentSheet === 'lost_project') {
            // 按狀態統計
            sheetData.data.forEach(row => {
                const status = row['狀態'];
                if (status) {
                    chartData[status] = (chartData[status] || 0) + 1;
                }
            });
        } else {
            // 預設按第一個非數字欄位統計
            const columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
            const firstStringCol = columns.find(col => {
                const firstValue = sheetData.data[0][col];
                return typeof firstValue === 'string';
            });
            
            if (firstStringCol) {
                sheetData.data.forEach(row => {
                    const value = row[firstStringCol];
                    if (value) {
                        chartData[value] = (chartData[value] || 0) + 1;
                    }
                });
            }
        }
        
        if (Object.keys(chartData).length > 0) {
            window.distributionChartInstance = new Chart(distCtx, {
                type: 'pie',
                data: {
                    labels: Object.keys(chartData),
                    datasets: [{
                        data: Object.values(chartData),
                        backgroundColor: [
                            '#2196F3', '#4CAF50', '#FF9800', '#F44336',
                            '#9C27B0', '#00BCD4', '#FFEB3B', '#795548',
                            '#607D8B', '#E91E63', '#3F51B5', '#009688'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right'
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        }
    }
    
    // 趨勢圖（如果有時間序列資料）
    const trendCanvas = document.getElementById('trendChart');
    if (trendCanvas && currentSheet === 'revision_diff') {
        const trendCtx = trendCanvas.getContext('2d');
        
        // 按模組分組計算差異數量
        const moduleData = {};
        sheetData.data.forEach(row => {
            const module = row.module;
            if (module) {
                if (!moduleData[module]) {
                    moduleData[module] = 0;
                }
                moduleData[module]++;
            }
        });
        
        // 只顯示前 10 個模組
        const sortedModules = Object.entries(moduleData)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10);
        
        window.trendChartInstance = new Chart(trendCtx, {
            type: 'bar',
            data: {
                labels: sortedModules.map(item => item[0]),
                datasets: [{
                    label: '差異數量',
                    data: sortedModules.map(item => item[1]),
                    backgroundColor: '#2196F3',
                    borderColor: '#1976D2',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
}

// 切換篩選器面板
function toggleFilterPanel() {
    document.getElementById('filterPanel').classList.toggle('show');
}

// 匯出當前檢視
function exportCurrentView(format) {
    if (!currentData || !currentSheet) {
        utils.showNotification('請先選擇資料表', 'error');
        return;
    }
    
    if (format === 'excel') {
        window.location.href = `/api/export-excel/${taskId}`;
    } else if (format === 'html') {
        // 生成當前檢視的 HTML
        const sheetData = currentData[currentSheet];
        const htmlContent = generateHTMLReport(sheetData);
        
        const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report_${taskId}_${currentSheet}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// 生成 HTML 報告
function generateHTMLReport(sheetData) {
    const columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
    const rows = sheetData.data || [];
    
    let tableHTML = `
        <table class="data-table">
            <thead>
                <tr>
                    ${columns.map(col => `<th>${col}</th>`).join('')}
                </tr>
            </thead>
            <tbody>
    `;
    
    rows.forEach(row => {
        tableHTML += '<tr>';
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
                }
            }
            
            tableHTML += `<td>${cellContent}</td>`;
        });
        tableHTML += '</tr>';
    });
    
    tableHTML += '</tbody></table>';
    
    return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>報表: ${getSheetDisplayName(currentSheet)} - ${taskId}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #1A237E; margin-bottom: 10px; }
        .info { color: #666; margin-bottom: 30px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #2196F3; color: white; padding: 12px; text-align: left; font-weight: 600; }
        td { padding: 10px; border-bottom: 1px solid #e0e0e0; }
        tr:hover { background: #f5f5f5; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.85em; font-weight: 500; }
        .badge-success { background: #E8F5E9; color: #2E7D32; }
        .badge-danger { background: #FFEBEE; color: #C62828; }
        .badge-default { background: #F5F5F5; color: #757575; }
    </style>
</head>
<body>
    <div class="container">
        <h1>報表: ${getSheetDisplayName(currentSheet)}</h1>
        <div class="info">
            <p>任務 ID: ${taskId}</p>
            <p>匯出時間: ${new Date().toLocaleString('zh-TW')}</p>
            <p>資料筆數: ${rows.length} 筆</p>
        </div>
        ${tableHTML}
    </div>
</body>
</html>
    `;
}

// 下載完整報表
function downloadFullReport() {
    window.location.href = `/api/export-zip/${taskId}`;
}

// 監聽資料表選擇
document.getElementById('sheetSelector').addEventListener('change', (e) => {
    if (e.target.value) {
        loadSheet(e.target.value);
    }
});

// 匯出函數
window.togglePivotMode = togglePivotMode;
window.applyFilters = applyFilters;
window.clearFilters = clearFilters;
window.toggleFilterPanel = toggleFilterPanel;
window.exportCurrentView = exportCurrentView;
window.downloadFullReport = downloadFullReport;