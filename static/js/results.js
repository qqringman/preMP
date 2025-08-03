// 結果報表頁面 JavaScript

const taskId = window.location.pathname.split('/').pop();
let currentData = null;
let currentSheet = null;
let pivotMode = false;
let filters = {};

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', () => {
    loadPivotData();
});

// 載入樞紐分析資料
async function loadPivotData() {
    try {
        utils.showLoading('載入資料中...');
        
        const data = await utils.apiRequest(`/api/pivot-data/${taskId}`);
        
        if (!data || Object.keys(data).length === 0) {
            // 如果沒有資料，顯示提示訊息
            showNoDataMessage();
            utils.hideLoading();
            return;
        }
        
        currentData = data;
        
        // 填充資料表選項
        const selector = document.getElementById('sheetSelector');
        selector.innerHTML = '';
        
        Object.keys(data).forEach(sheetName => {
            const option = document.createElement('option');
            option.value = sheetName;
            option.textContent = getSheetDisplayName(sheetName);
            selector.appendChild(option);
        });
        
        // 載入第一個資料表
        if (Object.keys(data).length > 0) {
            loadSheet(Object.keys(data)[0]);
        }
        
        utils.hideLoading();
        
    } catch (error) {
        console.error('Load data error:', error);
        utils.hideLoading();
        showErrorMessage();
    }
}

// 顯示無資料訊息
function showNoDataMessage() {
    const container = document.querySelector('.data-view-container');
    container.innerHTML = `
        <div class="no-data-message">
            <i class="fas fa-inbox fa-4x text-muted mb-3"></i>
            <h3>暫無資料可顯示</h3>
            <p class="text-muted">此任務可能還在處理中，或尚未產生報表。</p>
            <button class="btn btn-primary mt-3" onclick="location.reload()">
                <i class="fas fa-sync"></i> 重新載入
            </button>
        </div>
    `;
}

// 顯示錯誤訊息
function showErrorMessage() {
    const container = document.querySelector('.data-view-container');
    container.innerHTML = `
        <div class="error-message">
            <i class="fas fa-exclamation-triangle fa-4x text-danger mb-3"></i>
            <h3>載入資料失敗</h3>
            <p class="text-muted">無法載入報表資料，請稍後再試。</p>
            <div class="mt-3">
                <button class="btn btn-primary" onclick="location.reload()">
                    <i class="fas fa-sync"></i> 重試
                </button>
                <button class="btn btn-outline ml-2" onclick="window.history.back()">
                    <i class="fas fa-arrow-left"></i> 返回
                </button>
            </div>
        </div>
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
    currentSheet = sheetName;
    const sheetData = currentData[sheetName];
    
    if (!sheetData) {
        console.error('Sheet data not found:', sheetName);
        return;
    }
    
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
    const table = document.getElementById('dataTable');
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
                const badgeClass = value === '新增' ? 'badge-success' : 'badge-warning';
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
        console.error('Pivot table error:', error);
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
        const hasWaveCount = sheetData.data.filter(row => row.has_wave === 'Y').length;
        stats.push({
            label: '模組數',
            value: uniqueModules.size,
            icon: 'fa-cube',
            color: 'purple'
        });
        stats.push({
            label: '包含 Wave',
            value: hasWaveCount,
            icon: 'fa-water',
            color: 'info'
        });
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
            <div class="stat-icon ${stat.color ? `bg-${stat.color}` : ''}">
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
            new Chart(distCtx, {
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
        
        new Chart(trendCtx, {
            type: 'bar',
            data: {
                labels: Object.keys(moduleData),
                datasets: [{
                    label: '差異數量',
                    data: Object.values(moduleData),
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
    if (format === 'excel') {
        window.location.href = `/api/export-excel/${taskId}`;
    } else if (format === 'html') {
        // 生成當前檢視的 HTML
        const currentView = pivotMode ? 
            document.getElementById('pivotContainer').innerHTML : 
            document.getElementById('dataTable').outerHTML;
            
        const htmlContent = `
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>報表匯出 - ${taskId}</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    table { border-collapse: collapse; width: 100%; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #f2f2f2; font-weight: bold; }
                    tr:nth-child(even) { background-color: #f9f9f9; }
                    .highlight-red { color: #F44336; font-weight: bold; }
                    .badge { padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }
                    .badge-success { background: #4CAF50; color: white; }
                    .badge-warning { background: #FF9800; color: white; }
                    .badge-default { background: #9E9E9E; color: white; }
                </style>
            </head>
            <body>
                <h1>報表: ${getSheetDisplayName(currentSheet)}</h1>
                <p>匯出時間: ${new Date().toLocaleString('zh-TW')}</p>
                ${currentView}
            </body>
            </html>
        `;
        
        const blob = new Blob([htmlContent], { type: 'text/html' });
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