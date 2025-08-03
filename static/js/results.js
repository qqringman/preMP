// 全域變數
let pivotData = {};
let currentSheet = '';
let charts = {
    trend: null,
    distribution: null
};
let currentFilters = {};
let sortState = {};

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', () => {
    // 確認 taskId 存在
    if (typeof taskId === 'undefined') {
        console.error('Task ID not defined');
        showError('無法取得任務 ID');
        return;
    }
    
    console.log('Loading data for task:', taskId);
    loadPivotData();
    initializeEventListeners();
});

// 初始化事件監聽器
function initializeEventListeners() {
    // Sheet 選擇器
    const sheetSelector = document.getElementById('sheetSelector');
    if (sheetSelector) {
        sheetSelector.addEventListener('change', (e) => {
            const selectedSheet = e.target.value;
            if (selectedSheet) {
                displaySheet(selectedSheet);
                updateStatistics(selectedSheet);
                drawCharts(selectedSheet);
            }
        });
    }
    
    // 處理可能的擴充功能錯誤
    window.addEventListener('error', (e) => {
        if (e.message && e.message.includes('message port closed')) {
            e.preventDefault();
            return true;
        }
    });
}

// 載入樞紐分析資料
async function loadPivotData() {
    showLoading();
    
    try {
        console.log('Fetching pivot data for task:', taskId);
        
        const response = await utils.apiRequest(`/api/pivot-data/${taskId}`);
        console.log('Pivot data response:', response);
        
        if (response && Object.keys(response).length > 0) {
            pivotData = response;
            
            // 按照 Excel 頁籤順序排序
            const orderedSheets = ['revision_diff', 'branch_error', 'lost_project', 'version_diff', '無法比對'];
            const sheets = [];
            
            // 先加入已定義順序的頁籤
            orderedSheets.forEach(sheet => {
                if (sheet in pivotData) {
                    sheets.push(sheet);
                }
            });
            
            // 再加入其他頁籤
            Object.keys(pivotData).forEach(sheet => {
                if (!sheets.includes(sheet)) {
                    sheets.push(sheet);
                }
            });
            
            console.log('Available sheets:', sheets);
            
            updateSheetSelector(sheets);
            
            // 顯示第一個頁籤
            if (sheets.length > 0) {
                displaySheet(sheets[0]);
                updateStatistics(sheets[0]);
                drawCharts(sheets[0]);
            }
            
            hideLoading();
        } else {
            console.log('No data found for task:', taskId);
            showNoData();
        }
    } catch (error) {
        console.error('Load pivot data error:', error);
        showError('載入資料失敗：' + error.message);
    }
}

// 更新資料表選擇器
function updateSheetSelector(sheets) {
    const selector = document.getElementById('sheetSelector');
    if (!selector) return;
    
    selector.innerHTML = '';
    
    sheets.forEach(sheet => {
        const option = document.createElement('option');
        option.value = sheet;
        option.textContent = formatSheetName(sheet);
        selector.appendChild(option);
    });
}

// 格式化資料表名稱
function formatSheetName(sheetName) {
    const nameMap = {
        'revision_diff': 'Revision 差異',
        'branch_error': '分支錯誤',
        'lost_project': '新增/刪除專案',
        'version_diff': '版本檔案差異',
        '無法比對': '無法比對的模組'
    };
    return nameMap[sheetName] || sheetName;
}

// 顯示資料表
function displaySheet(sheetName) {
    currentSheet = sheetName;
    const data = pivotData[sheetName];
    
    if (!data || !data.data) {
        document.getElementById('tableWrapper').innerHTML = '<div class="no-data"><i class="fas fa-inbox"></i><p>無資料</p></div>';
        return;
    }
    
    // 生成表格
    const tableHtml = generateTable(data);
    document.getElementById('tableWrapper').innerHTML = tableHtml;
    
    // 添加排序和篩選功能
    addSortingToTable();
}

// 生成表格 HTML
function generateTable(data) {
    const columns = data.columns || [];
    const rows = data.data || [];
    
    if (columns.length === 0 || rows.length === 0) {
        return '<div class="no-data"><i class="fas fa-inbox"></i><p>無資料</p></div>';
    }
    
    let html = '<table class="data-table" id="dataTable">';
    
    // 表頭
    html += '<thead><tr>';
    columns.forEach(col => {
        html += `<th>${col}</th>`;
    });
    html += '</tr></thead>';
    
    // 表身
    html += '<tbody>';
    rows.forEach(row => {
        html += '<tr>';
        columns.forEach(col => {
            let value = row[col] || '';
            let cellClass = '';
            
            // 特殊處理
            if (col === 'problem' && value) {
                cellClass = 'highlight-red';
            } else if (col === '狀態') {
                if (value === '新增') {
                    value = '<span class="badge badge-success">新增</span>';
                } else if (value === '刪除') {
                    value = '<span class="badge badge-danger">刪除</span>';
                }
            } else if (col === 'has_wave') {
                if (value === 'Y') {
                    value = '<span class="badge badge-info">Y</span>';
                } else if (value === 'N') {
                    value = '<span class="badge badge-warning">N</span>';
                }
            } else if ((col.includes('link') || col.includes('Link')) && value && value.startsWith('http')) {
                value = `<a href="${value}" target="_blank" class="link">${value} <i class="fas fa-external-link-alt"></i></a>`;
            }
            
            html += `<td class="${cellClass}">${value}</td>`;
        });
        html += '</tr>';
    });
    html += '</tbody>';
    
    html += '</table>';
    return html;
}

// 添加排序功能
function addSortingToTable() {
    const headers = document.querySelectorAll('.data-table th');
    
    headers.forEach((header, index) => {
        // 添加排序和篩選圖標
        const icons = document.createElement('span');
        icons.className = 'sort-filter-icons';
        icons.innerHTML = `
            <i class="fas fa-sort sort-icon"></i>
            <i class="fas fa-filter filter-icon"></i>
        `;
        header.appendChild(icons);
        
        // 排序事件
        header.querySelector('.sort-icon').addEventListener('click', (e) => {
            e.stopPropagation();
            sortTable(index, header);
        });
        
        // 篩選事件
        header.querySelector('.filter-icon').addEventListener('click', (e) => {
            e.stopPropagation();
            showFilterDialog(index, header);
        });
    });
}

// 表格排序
function sortTable(columnIndex, headerElement) {
    const table = document.querySelector('.data-table');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // 確定排序方向
    const isAscending = headerElement.classList.contains('sort-asc');
    
    // 移除所有排序類別
    document.querySelectorAll('.data-table th').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc', 'sorted');
    });
    
    // 排序
    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();
        
        // 嘗試數字排序
        const aNum = parseFloat(aText);
        const bNum = parseFloat(bText);
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAscending ? bNum - aNum : aNum - bNum;
        }
        
        // 文字排序
        return isAscending ? 
            bText.localeCompare(aText, 'zh-TW') : 
            aText.localeCompare(bText, 'zh-TW');
    });
    
    // 更新排序類別
    headerElement.classList.add('sorted', isAscending ? 'sort-desc' : 'sort-asc');
    
    // 更新圖標
    const sortIcon = headerElement.querySelector('.sort-icon');
    sortIcon.className = isAscending ? 'fas fa-sort-down sort-icon' : 'fas fa-sort-up sort-icon';
    
    // 更新表格
    rows.forEach(row => tbody.appendChild(row));
}

// 顯示篩選對話框
function showFilterDialog(columnIndex, headerElement) {
    // 獲取該欄位的所有值
    const table = document.querySelector('.data-table');
    const rows = table.querySelectorAll('tbody tr');
    const values = new Set();
    
    rows.forEach(row => {
        const cell = row.cells[columnIndex];
        if (cell) {
            values.add(cell.textContent.trim());
        }
    });
    
    // 創建篩選面板內容
    const filterContent = document.querySelector('.filter-content');
    filterContent.innerHTML = `
        <div class="filter-group">
            <label class="filter-label">${headerElement.textContent.replace(/[\s\n]+/g, ' ').trim()}</label>
            <select class="filter-select" multiple size="10" id="filterSelect">
                ${Array.from(values).sort().map(value => 
                    `<option value="${value}" selected>${value}</option>`
                ).join('')}
            </select>
        </div>
    `;
    
    // 顯示篩選面板
    document.getElementById('filterPanel').classList.add('show');
    
    // 儲存當前篩選的欄位索引
    currentFilters.columnIndex = columnIndex;
}

// 應用篩選
function applyFilters() {
    const filterSelect = document.getElementById('filterSelect');
    const selectedValues = Array.from(filterSelect.selectedOptions).map(opt => opt.value);
    const columnIndex = currentFilters.columnIndex;
    
    if (columnIndex === undefined) return;
    
    const table = document.querySelector('.data-table');
    const rows = table.querySelectorAll('tbody tr');
    
    rows.forEach(row => {
        const cell = row.cells[columnIndex];
        if (cell) {
            const value = cell.textContent.trim();
            row.style.display = selectedValues.includes(value) ? '' : 'none';
        }
    });
    
    // 標記已篩選的欄位
    const headers = table.querySelectorAll('th');
    headers[columnIndex].classList.add('filtered');
    
    hideFilters();
}

// 重置篩選
function resetFilters() {
    const table = document.querySelector('.data-table');
    const rows = table.querySelectorAll('tbody tr');
    
    rows.forEach(row => {
        row.style.display = '';
    });
    
    // 移除篩選標記
    table.querySelectorAll('th').forEach(th => {
        th.classList.remove('filtered');
    });
    
    hideFilters();
}

// 隱藏篩選面板
function hideFilters() {
    document.getElementById('filterPanel').classList.remove('show');
}

// 顯示篩選器
function showFilters() {
    document.getElementById('filterPanel').classList.add('show');
}

// 更新統計資訊
function updateStatistics(sheetName) {
    const data = pivotData[sheetName];
    if (!data || !data.data) return;
    
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.innerHTML = '';
    
    // 基本統計
    const totalRecords = data.data.length;
    
    // 根據不同的資料表顯示不同的統計
    if (sheetName === 'revision_diff') {
        // 統計模組數
        const modules = new Set(data.data.map(row => row.module)).size;
        
        // 統計 has_wave
        let hasWaveY = 0;
        let hasWaveN = 0;
        data.data.forEach(row => {
            if (row.has_wave === 'Y') hasWaveY++;
            else if (row.has_wave === 'N') hasWaveN++;
        });
        
        statsGrid.innerHTML = `
            <div class="stat-card blue">
                <div class="stat-icon">
                    <i class="fas fa-list"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${totalRecords}</div>
                    <div class="stat-label">總記錄數</div>
                </div>
            </div>
            <div class="stat-card purple">
                <div class="stat-icon">
                    <i class="fas fa-cubes"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${modules}</div>
                    <div class="stat-label">模組數</div>
                </div>
            </div>
            <div class="stat-card success">
                <div class="stat-icon">
                    <i class="fas fa-check"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${hasWaveY}</div>
                    <div class="stat-label">Has Wave - Y</div>
                </div>
            </div>
            <div class="stat-card danger">
                <div class="stat-icon">
                    <i class="fas fa-times"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${hasWaveN}</div>
                    <div class="stat-label">Has Wave - N</div>
                </div>
            </div>
        `;
    } else if (sheetName === 'branch_error') {
        // 統計問題類型
        const problems = {};
        let hasWaveN = 0;
        
        data.data.forEach(row => {
            if (row.problem) {
                problems[row.problem] = (problems[row.problem] || 0) + 1;
            }
            if (row.has_wave === 'N') hasWaveN++;
        });
        
        statsGrid.innerHTML = `
            <div class="stat-card blue">
                <div class="stat-icon">
                    <i class="fas fa-list"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${totalRecords}</div>
                    <div class="stat-label">總錯誤數</div>
                </div>
            </div>
            <div class="stat-card danger">
                <div class="stat-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${Object.keys(problems).length}</div>
                    <div class="stat-label">問題類型</div>
                </div>
            </div>
            <div class="stat-card warning">
                <div class="stat-icon">
                    <i class="fas fa-times"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${hasWaveN}</div>
                    <div class="stat-label">Has Wave - N</div>
                </div>
            </div>
        `;
    } else if (sheetName === 'lost_project') {
        // 統計新增和刪除
        let added = 0;
        let deleted = 0;
        data.data.forEach(row => {
            if (row['狀態'] === '新增') added++;
            else if (row['狀態'] === '刪除') deleted++;
        });
        
        statsGrid.innerHTML = `
            <div class="stat-card blue">
                <div class="stat-icon">
                    <i class="fas fa-list"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${totalRecords}</div>
                    <div class="stat-label">總變更數</div>
                </div>
            </div>
            <div class="stat-card success">
                <div class="stat-icon">
                    <i class="fas fa-plus"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${added}</div>
                    <div class="stat-label">新增專案</div>
                </div>
            </div>
            <div class="stat-card danger">
                <div class="stat-icon">
                    <i class="fas fa-minus"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${deleted}</div>
                    <div class="stat-label">刪除專案</div>
                </div>
            </div>
        `;
    } else {
        // 通用統計
        statsGrid.innerHTML = `
            <div class="stat-card blue">
                <div class="stat-icon">
                    <i class="fas fa-database"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${totalRecords}</div>
                    <div class="stat-label">總記錄數</div>
                </div>
            </div>
            <div class="stat-card purple">
                <div class="stat-icon">
                    <i class="fas fa-columns"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${data.columns ? data.columns.length : 0}</div>
                    <div class="stat-label">欄位數</div>
                </div>
            </div>
        `;
    }
}

// 繪製圖表
function drawCharts(sheetName) {
    const data = pivotData[sheetName];
    if (!data || !data.data || data.data.length === 0) {
        clearCharts();
        return;
    }
    
    // 銷毀舊圖表
    if (charts.trend) {
        charts.trend.destroy();
        charts.trend = null;
    }
    if (charts.distribution) {
        charts.distribution.destroy();
        charts.distribution = null;
    }
    
    // 根據不同的資料表類型繪製不同的圖表
    if (sheetName === 'revision_diff') {
        drawRevisionTrendChart(data);
        drawRevisionDistributionChart(data);
    } else if (sheetName === 'branch_error') {
        drawBranchErrorChart(data);
    } else if (sheetName === 'lost_project') {
        drawLostProjectChart(data);
    } else {
        // 通用圖表
        drawGenericCharts(data);
    }
}

// 清空圖表
function clearCharts() {
    if (charts.trend) {
        charts.trend.destroy();
        charts.trend = null;
    }
    if (charts.distribution) {
        charts.distribution.destroy();
        charts.distribution = null;
    }
    
    // 顯示無數據提示
    const ctx1 = document.getElementById('trendChart');
    const ctx2 = document.getElementById('distributionChart');
    
    if (ctx1) {
        const context = ctx1.getContext('2d');
        context.clearRect(0, 0, ctx1.width, ctx1.height);
        context.font = '16px Arial';
        context.textAlign = 'center';
        context.fillStyle = '#999';
        context.fillText('暫無趨勢數據', ctx1.width / 2, ctx1.height / 2);
    }
    
    if (ctx2) {
        const context = ctx2.getContext('2d');
        context.clearRect(0, 0, ctx2.width, ctx2.height);
        context.font = '16px Arial';
        context.textAlign = 'center';
        context.fillStyle = '#999';
        context.fillText('暫無分佈數據', ctx2.width / 2, ctx2.height / 2);
    }
}

// 繪製 revision 趨勢圖
function drawRevisionTrendChart(data) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    
    // 按模組分組統計
    const moduleStats = {};
    data.data.forEach(row => {
        const module = row.module || 'Unknown';
        if (!moduleStats[module]) {
            moduleStats[module] = 0;
        }
        moduleStats[module]++;
    });
    
    charts.trend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Object.keys(moduleStats),
            datasets: [{
                label: 'Revision 差異數量',
                data: Object.values(moduleStats),
                borderColor: '#2196F3',
                backgroundColor: 'rgba(33, 150, 243, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: '各模組 Revision 差異趨勢'
                }
            }
        }
    });
}

// 繪製分佈圖
function drawRevisionDistributionChart(data) {
    const ctx = document.getElementById('distributionChart').getContext('2d');
    
    // 統計 has_wave 的分佈
    let hasWaveY = 0;
    let hasWaveN = 0;
    
    data.data.forEach(row => {
        if (row.has_wave === 'Y') {
            hasWaveY++;
        } else if (row.has_wave === 'N') {
            hasWaveN++;
        }
    });
    
    charts.distribution = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Has Wave - Y', 'Has Wave - N'],
            datasets: [{
                data: [hasWaveY, hasWaveN],
                backgroundColor: ['#4CAF50', '#F44336']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Wave 分佈統計'
                }
            }
        }
    });
}

// 繪製分支錯誤圖表
function drawBranchErrorChart(data) {
    // 趨勢圖
    const trendCtx = document.getElementById('trendChart').getContext('2d');
    const moduleProblems = {};
    
    data.data.forEach(row => {
        const module = row.module || 'Unknown';
        if (!moduleProblems[module]) {
            moduleProblems[module] = {
                total: 0,
                hasWaveN: 0
            };
        }
        moduleProblems[module].total++;
        if (row.has_wave === 'N') {
            moduleProblems[module].hasWaveN++;
        }
    });
    
    const modules = Object.keys(moduleProblems);
    
    charts.trend = new Chart(trendCtx, {
        type: 'bar',
        data: {
            labels: modules,
            datasets: [{
                label: '總錯誤數',
                data: modules.map(m => moduleProblems[m].total),
                backgroundColor: 'rgba(33, 150, 243, 0.5)'
            }, {
                label: 'Has Wave = N',
                data: modules.map(m => moduleProblems[m].hasWaveN),
                backgroundColor: 'rgba(244, 67, 54, 0.5)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: '各模組分支錯誤統計'
                }
            }
        }
    });
    
    // 分佈圖
    const ctx = document.getElementById('distributionChart').getContext('2d');
    
    // 統計問題類型
    const problemTypes = {};
    data.data.forEach(row => {
        const problem = row.problem || '無問題';
        if (!problemTypes[problem]) {
            problemTypes[problem] = 0;
        }
        problemTypes[problem]++;
    });
    
    const labels = Object.keys(problemTypes);
    const values = Object.values(problemTypes);
    const colors = labels.map((label, index) => {
        const colorPalette = ['#F44336', '#FF9800', '#FFC107', '#4CAF50', '#2196F3', '#9C27B0'];
        return colorPalette[index % colorPalette.length];
    });
    
    charts.distribution = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: '分支錯誤類型分佈'
                },
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// 繪製缺失專案圖表
function drawLostProjectChart(data) {
    // 趨勢圖
    const trendCtx = document.getElementById('trendChart').getContext('2d');
    const baseFolderStats = {};
    
    data.data.forEach(row => {
        const baseFolder = row['Base folder'] || 'Unknown';
        if (!baseFolderStats[baseFolder]) {
            baseFolderStats[baseFolder] = {
                added: 0,
                deleted: 0
            };
        }
        if (row['狀態'] === '新增') {
            baseFolderStats[baseFolder].added++;
        } else if (row['狀態'] === '刪除') {
            baseFolderStats[baseFolder].deleted++;
        }
    });
    
    const folders = Object.keys(baseFolderStats);
    
    charts.trend = new Chart(trendCtx, {
        type: 'bar',
        data: {
            labels: folders,
            datasets: [{
                label: '新增',
                data: folders.map(f => baseFolderStats[f].added),
                backgroundColor: 'rgba(76, 175, 80, 0.5)'
            }, {
                label: '刪除',
                data: folders.map(f => baseFolderStats[f].deleted),
                backgroundColor: 'rgba(244, 67, 54, 0.5)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    stacked: true
                },
                y: {
                    stacked: true
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: '各 Base Folder 專案變更統計'
                }
            }
        }
    });
    
    // 分佈圖
    const ctx = document.getElementById('distributionChart').getContext('2d');
    
    // 統計新增和刪除
    let added = 0;
    let deleted = 0;
    
    data.data.forEach(row => {
        if (row['狀態'] === '新增') {
            added++;
        } else if (row['狀態'] === '刪除') {
            deleted++;
        }
    });
    
    charts.distribution = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['新增', '刪除'],
            datasets: [{
                data: [added, deleted],
                backgroundColor: ['#4CAF50', '#F44336']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: '專案變更統計'
                },
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// 繪製通用圖表
function drawGenericCharts(data) {
    // 如果沒有數據，清空圖表
    if (!data.data || data.data.length === 0) {
        clearCharts();
        return;
    }
    
    // 嘗試找出可以用來做圖表的欄位
    const columns = data.columns || [];
    const numericColumns = [];
    const categoricalColumns = [];
    
    // 分析欄位類型
    columns.forEach(col => {
        if (col === 'SN') return; // 跳過序號
        
        // 檢查是否為數值欄位
        let isNumeric = true;
        let hasCategories = new Set();
        
        data.data.forEach(row => {
            const value = row[col];
            if (value !== null && value !== undefined && value !== '') {
                if (isNaN(value)) {
                    isNumeric = false;
                }
                hasCategories.add(value);
            }
        });
        
        if (isNumeric && hasCategories.size > 0) {
            numericColumns.push(col);
        } else if (hasCategories.size > 1 && hasCategories.size < 20) {
            categoricalColumns.push(col);
        }
    });
    
    // 如果有分類欄位，繪製分佈圖
    if (categoricalColumns.length > 0) {
        const col = categoricalColumns[0];
        const distribution = {};
        
        data.data.forEach(row => {
            const value = row[col] || 'Unknown';
            distribution[value] = (distribution[value] || 0) + 1;
        });
        
        const ctx = document.getElementById('distributionChart').getContext('2d');
        
        charts.distribution = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: Object.keys(distribution),
                datasets: [{
                    data: Object.values(distribution),
                    backgroundColor: [
                        '#2196F3', '#4CAF50', '#FF9800', '#F44336', 
                        '#9C27B0', '#00BCD4', '#8BC34A', '#FFC107'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: `${col} 分佈`
                    }
                }
            }
        });
    }
    
    // 如果有數值欄位，繪製趨勢圖
    if (numericColumns.length > 0) {
        const ctx = document.getElementById('trendChart').getContext('2d');
        const labels = data.data.map((_, index) => `#${index + 1}`);
        
        charts.trend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: numericColumns.map((col, index) => ({
                    label: col,
                    data: data.data.map(row => row[col]),
                    borderColor: ['#2196F3', '#4CAF50', '#FF9800'][index % 3],
                    fill: false
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: '數值趨勢'
                    }
                }
            }
        });
    }
}

// 切換檢視
function switchView(view) {
    // 更新按鈕狀態
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // 切換內容
    document.querySelectorAll('.view-content').forEach(content => {
        content.classList.remove('active');
    });
    
    if (view === 'table') {
        document.getElementById('tableView').classList.add('active');
    } else if (view === 'pivot') {
        document.getElementById('pivotView').classList.add('active');
        // TODO: 實現樞紐分析功能
        document.getElementById('pivotTable').innerHTML = '<div class="no-data"><i class="fas fa-wrench"></i><p>樞紐分析功能開發中...</p></div>';
    }
}

// 匯出 Excel
async function exportSheet(format) {
    if (!currentSheet) {
        utils.showNotification('請先選擇資料表', 'warning');
        return;
    }
    
    try {
        if (format === 'excel') {
            const url = `/api/export-sheet/${taskId}/${currentSheet}?format=excel`;
            window.location.href = url;
        } else if (format === 'pdf') {
            utils.showNotification('PDF 匯出功能開發中', 'info');
        }
    } catch (error) {
        console.error('Export error:', error);
        utils.showNotification('匯出失敗', 'error');
    }
}

// 匯出整個頁面為 HTML
async function exportPageAsHTML() {
    try {
        utils.showNotification('正在準備匯出 HTML...', 'info');
        
        // 創建一個隱藏的 iframe 來載入完整頁面
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
        
        // 複製當前頁面到 iframe
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        iframeDoc.open();
        iframeDoc.write(document.documentElement.outerHTML);
        iframeDoc.close();
        
        // 等待內容載入
        setTimeout(() => {
            // 移除不需要的元素
            const elementsToRemove = iframeDoc.querySelectorAll('.control-actions, .filter-panel, .fab, script');
            elementsToRemove.forEach(el => el.remove());
            
            // 獲取所有樣式
            const styles = Array.from(document.styleSheets)
                .map(sheet => {
                    try {
                        return Array.from(sheet.cssRules)
                            .map(rule => rule.cssText)
                            .join('\n');
                    } catch (e) {
                        return '';
                    }
                })
                .join('\n');
            
            // 內嵌樣式
            const styleElement = iframeDoc.createElement('style');
            styleElement.textContent = styles;
            iframeDoc.head.appendChild(styleElement);
            
            // 生成最終 HTML
            const finalHtml = '<!DOCTYPE html>\n' + iframeDoc.documentElement.outerHTML;
            
            // 下載
            const blob = new Blob([finalHtml], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `report_${taskId}_${new Date().getTime()}.html`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            // 清理
            document.body.removeChild(iframe);
            
            utils.showNotification('HTML 頁面已匯出', 'success');
        }, 1000);
        
    } catch (error) {
        console.error('Export HTML error:', error);
        utils.showNotification('匯出失敗', 'error');
    }
}

// 顯示載入中
function showLoading() {
    const loading = document.getElementById('loading');
    const noData = document.getElementById('noData');
    const errorMessage = document.getElementById('errorMessage');
    
    if (loading) loading.classList.remove('hidden');
    if (noData) noData.classList.add('hidden');
    if (errorMessage) errorMessage.classList.add('hidden');
}

// 隱藏載入中
function hideLoading() {
    const loading = document.getElementById('loading');
    if (loading) loading.classList.add('hidden');
}

// 顯示無資料
function showNoData() {
    hideLoading();
    const noData = document.getElementById('noData');
    if (noData) noData.classList.remove('hidden');
}

// 顯示錯誤
function showError(message) {
    hideLoading();
    const errorMessage = document.getElementById('errorMessage');
    const errorText = document.getElementById('errorText');
    
    if (errorText) errorText.textContent = message;
    if (errorMessage) errorMessage.classList.remove('hidden');
}

// 回到頂部
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// 匯出函數
window.switchView = switchView;
window.exportSheet = exportSheet;
window.showFilters = showFilters;
window.hideFilters = hideFilters;
window.applyFilters = applyFilters;
window.resetFilters = resetFilters;
window.scrollToTop = scrollToTop;
window.exportPageAsHTML = exportPageAsHTML;