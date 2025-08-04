// 結果報表頁面 JavaScript - 使用真實資料

const taskId = window.location.pathname.split('/').pop();
let currentData = null;
let currentSheet = null;
let pivotMode = false;
let filters = {};
let sortOrder = {};
let searchTerm = '';

console.log('Task ID:', taskId);

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('頁面載入完成，開始載入資料...');
    loadPivotData();
    
    // 初始化搜尋功能
    initializeSearch();
});

// 初始化搜尋功能
function initializeSearch() {
    const searchInput = document.getElementById('quickSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function(e) {
            searchTerm = e.target.value.toLowerCase();
            if (currentSheet) {
                renderDataTable(currentData[currentSheet]);
            }
        }, 300));
    }
}

// 防抖函數
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 載入樞紐分析資料
async function loadPivotData() {
    try {
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
        
        sheetOrder.forEach(sheetName => {
            if (data[sheetName]) {
                orderedSheets.push(sheetName);
            }
        });
        
        Object.keys(data).forEach(sheetName => {
            if (!orderedSheets.includes(sheetName)) {
                orderedSheets.push(sheetName);
            }
        });
        
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
    
    document.getElementById('statsGrid').innerHTML = '';
    
    const statsBar = document.querySelector('.table-stats-bar');
    if (statsBar) {
        statsBar.remove();
    }
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
    
    document.getElementById('sheetSelector').value = sheetName;
    
    updateStatistics(sheetData);
    generateFilters(sheetData);
    
    if (pivotMode) {
        renderPivotTable(sheetData);
    } else {
        renderDataTable(sheetData);
    }
    
    drawDataCharts(sheetData);
}

// 高亮文字
function highlightText(text, searchTerm) {
    if (!searchTerm || !text) return text;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    return String(text).replace(regex, '<span class="highlight">$1</span>');
}

// 檢查行是否符合搜尋
function rowMatchesSearch(row, columns, searchTerm) {
    if (!searchTerm) return true;
    
    return columns.some(col => {
        const value = row[col];
        if (value === null || value === undefined) return false;
        return String(value).toLowerCase().includes(searchTerm);
    });
}

// 獲取欄位寬度
function getColumnWidth(columnName) {
    const widthMap = {
        'SN': '60px',
        'module': '150px',
        'location': '120px',
        'location_path': '200px',
        'base_fold': '100px',
        'base_folder': '150px',
        'compare': '100px',
        'compare_folder': '150px',
        'name': '200px',
        'path': '350px',
        'base_short': '120px',
        'base_revision': '180px',
        'compare_short': '120px',
        'compare_revision': '180px',
        'base_link': '150px',
        'compare_link': '150px',
        'has_wave': '80px',
        'problem': '200px',
        '狀態': '80px',
        'is_different': '100px'
    };
    
    return widthMap[columnName] || '150px';
}

// 渲染資料表格 - 改進版
function renderDataTable(sheetData) {
    const tableView = document.getElementById('tableView');
    const table = document.getElementById('dataTable');
    const thead = document.getElementById('tableHead');
    const tbody = document.getElementById('tableBody');
    
    thead.innerHTML = '';
    tbody.innerHTML = '';
    
    if (!sheetData.data || sheetData.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="100%" class="empty-message">此資料表沒有資料</td></tr>';
        updateTableStats(0, 0, 0);
        return;
    }
    
    const columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
    console.log('欄位:', columns);
    
    // 先篩選再搜尋
    let filteredData = applyDataFilters(sheetData.data);
    let searchMatches = 0;
    
    // 如果有搜尋詞，進一步過濾
    if (searchTerm) {
        filteredData = filteredData.filter(row => {
            const matches = rowMatchesSearch(row, columns, searchTerm);
            if (matches) searchMatches++;
            return matches;
        });
    }
    
    updateTableStats(sheetData.data.length, filteredData.length, searchMatches);
    
    // 建立表頭
    const headerRow = document.createElement('tr');
    columns.forEach(col => {
        const th = document.createElement('th');
        th.style.width = getColumnWidth(col);
        th.style.minWidth = getColumnWidth(col);
        
        if (col === 'base_content') {
            th.classList.add('base-content-header');
        } else if (col === 'compare_content') {
            th.classList.add('compare-content-header');
        } else if (['base_short', 'base_revision', 'compare_short', 'compare_revision', 'problem', '狀態', 'is_different'].includes(col)) {
            th.classList.add('highlight-header');
        }
        
        const thContent = document.createElement('div');
        thContent.className = 'th-content';
        
        const thText = document.createElement('span');
        thText.className = 'th-text';
        thText.textContent = col;
        
        const thIcons = document.createElement('span');
        thIcons.className = 'th-icons';
        
        const sortIcon = document.createElement('i');
        sortIcon.className = 'fas fa-sort sort-icon';
        if (sortOrder[col]) {
            sortIcon.className = sortOrder[col] === 'asc' ? 
                'fas fa-sort-up sort-icon active' : 
                'fas fa-sort-down sort-icon active';
        }
        
        thIcons.appendChild(sortIcon);
        
        if (filters[col]) {
            const filterIcon = document.createElement('i');
            filterIcon.className = 'fas fa-filter filter-icon active';
            thIcons.appendChild(filterIcon);
        }
        
        thContent.appendChild(thText);
        thContent.appendChild(thIcons);
        th.appendChild(thContent);
        
        th.onclick = () => sortTable(col);
        th.style.cursor = 'pointer';
        
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    
    // 建立表格內容
    console.log(`顯示 ${filteredData.length} 筆資料`);
    
    filteredData.forEach((row, index) => {
        const tr = document.createElement('tr');
        columns.forEach(col => {
            const td = document.createElement('td');
            const value = row[col];
            
            // 檢查是否為路徑欄位
            if (col === 'path' || col.toLowerCase().includes('path')) {
                td.classList.add('path-cell');
                
                // 如果路徑太長，顯示縮略版本
                if (value && value.length > 50) {
                    const truncated = value.substring(0, 25) + '...' + value.substring(value.length - 20);
                    td.innerHTML = `<span class="truncated-content" title="${value}">${searchTerm ? highlightText(truncated, searchTerm) : truncated}</span>`;
                } else {
                    td.innerHTML = searchTerm ? highlightText(value || '', searchTerm) : (value || '');
                }
            } else if (col === 'base_content' || col === 'compare_content') {
                td.classList.add('content-cell');
                
                // 不再添加紅色背景
                // td.classList.add('base-content'); // 移除這行
                
                if (value) {
                    // 解析內容，只對特定部分標紅
                    let formattedValue = String(value);
                    
                    // 對 P_GIT_ 開頭的行進行高亮
                    formattedValue = formattedValue.replace(/(P_GIT_\d+:[^;]+;[^;]+;[^;]+;[a-f0-9]+)/g, 
                        '<span class="highlight-git">$1</span>');
                    
                    // 對 F_HASH 行進行高亮
                    formattedValue = formattedValue.replace(/(F_HASH:\s*[a-f0-9]+)/g, 
                        '<span class="highlight-hash">$1</span>');
                    
                    // 如果有搜尋詞，也要高亮
                    if (searchTerm) {
                        formattedValue = highlightText(formattedValue, searchTerm);
                    }
                    
                    td.innerHTML = formattedValue;
                } else {
                    td.innerHTML = value || '';
                }
            } else if (col === 'compare_content') {
                td.classList.add('compare-content', 'content-cell');
                td.innerHTML = searchTerm ? highlightText(value || '', searchTerm) : (value || '');
            } else if (col === 'file_type') {
                td.classList.add('file-type');
                td.innerHTML = searchTerm ? highlightText(value || '', searchTerm) : (value || '');
            } else if (col === 'org_folder') {
                td.classList.add('org-cell');
                td.innerHTML = searchTerm ? highlightText(value || '', searchTerm) : (value || '');
            } else if (col.includes('link') && value && typeof value === 'string' && value.startsWith('http')) {
                // 特殊格式處理 - 連結
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
                const highlightedValue = searchTerm ? highlightText(value, searchTerm) : value;
                td.innerHTML = `<span class="text-danger font-weight-bold">${highlightedValue}</span>`;
            } else if (['base_short', 'base_revision', 'compare_short', 'compare_revision'].includes(col) && value) {
                td.classList.add('highlight-hash');
                td.innerHTML = searchTerm ? highlightText(value, searchTerm) : value;
            } else {
                const textValue = value !== null && value !== undefined ? value : '';
                td.innerHTML = searchTerm ? highlightText(textValue, searchTerm) : textValue;
            }
            
            if (['base_short', 'base_revision', 'compare_short', 'compare_revision'].includes(col) && value) {
                td.classList.add('highlight-red');
            }
            
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    
    if (filteredData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="100%" class="empty-message">沒有符合搜尋或篩選條件的資料</td></tr>';
        updateTableStats(sheetData.data.length, 0, 0);
    }
}

// 更新表格統計資訊 - 改進版
function updateTableStats(total, displayed, searchMatches) {
    let statsBar = document.querySelector('.table-stats-bar');
    
    // 如果統計條不存在，創建一個
    if (!statsBar) {
        statsBar = document.createElement('div');
        statsBar.className = 'table-stats-bar';
        
        // 插入到表格容器之前
        const tableView = document.getElementById('tableView');
        const parent = tableView.parentNode;
        parent.insertBefore(statsBar, tableView);
    }
    
    // 更新搜尋計數的顯示邏輯
    const searchCount = document.getElementById('searchCount');
    if (searchCount) {
        if (searchTerm) {
            // 格式化大數字
            let formattedCount = searchMatches;
            if (searchMatches >= 10000) {
                formattedCount = (searchMatches / 1000).toFixed(1) + 'k';
                searchCount.classList.add('large-count');
            } else if (searchMatches >= 1000) {
                formattedCount = searchMatches.toLocaleString();
                searchCount.classList.add('large-count');
            } else {
                searchCount.classList.remove('large-count');
            }
            
            searchCount.textContent = `${formattedCount} 筆`;
            searchCount.style.display = 'inline-block';
        } else {
            searchCount.textContent = '';
            searchCount.style.display = 'none';
            searchCount.classList.remove('large-count');
        }
    }
    
    // 更新統計內容
    statsBar.innerHTML = `
        <div class="table-stats">
            <div class="table-stat-item">
                <i class="fas fa-database"></i>
                <span>總筆數：<span class="table-stat-value">${total}</span></span>
            </div>
            <div class="table-stat-item">
                <i class="fas fa-eye"></i>
                <span>顯示：<span class="table-stat-value">${displayed}</span></span>
            </div>
            ${total !== displayed ? `
            <div class="table-stat-item">
                <i class="fas fa-filter"></i>
                <span>已篩選：<span class="table-stat-value">${total - displayed}</span></span>
            </div>
            ` : ''}
        </div>
    `;
}

// 渲染樞紐分析表
function renderPivotTable(sheetData) {
    const container = document.getElementById('pivotContainer');
    container.innerHTML = '';
    
    if (!sheetData.data || sheetData.data.length === 0) {
        container.innerHTML = '<div class="empty-message">沒有資料可供分析</div>';
        return;
    }
    
    // 使用 PivotTable.js - 修復錯誤
    try {
        const pivotConfig = {
            rows: [],
            cols: [],
            aggregatorName: "Count",
            rendererName: "Table",
            unusedAttrsVertical: true,
            renderers: $.pivotUtilities.renderers,
            aggregators: $.pivotUtilities.aggregators,
            localeStrings: $.pivotUtilities.locales.zh
        };
        
        $(container).pivotUI(sheetData.data, pivotConfig);
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
    
    const pivotIcon = document.getElementById('pivotIcon');
    if (pivotMode) {
        pivotIcon.classList.remove('fa-chart-pie');
        pivotIcon.classList.add('fa-table');
        pivotIcon.parentElement.classList.add('active');
    } else {
        pivotIcon.classList.remove('fa-table');
        pivotIcon.classList.add('fa-chart-pie');
        pivotIcon.parentElement.classList.remove('active');
    }
    
    if (currentSheet) {
        loadSheet(currentSheet);
    }
}

// 更新統計資料
function updateStatistics(sheetData) {
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.innerHTML = '';
    
    if (!sheetData.data || sheetData.data.length === 0) return;
    
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
    
    columns.forEach(col => {
        if (col.includes('link') || col.includes('content') || col.includes('revision')) return;
        
        const uniqueValues = [...new Set(sheetData.data.map(row => row[col]))].filter(v => v !== null && v !== undefined);
        
        if (uniqueValues.length > 0 && uniqueValues.length < 50) {
            const filterGroup = document.createElement('div');
            filterGroup.className = 'filter-group';
            
            // 加入搜尋框
            const searchBox = document.createElement('div');
            searchBox.className = 'filter-search';
            searchBox.innerHTML = `
                <input type="text" 
                       class="filter-search-input" 
                       placeholder="搜尋 ${col}..." 
                       data-column="${col}">
                <i class="fas fa-search"></i>
            `;
            
            const select = document.createElement('select');
            select.className = 'filter-select';
            select.multiple = true;
            select.dataset.column = col;
            
            uniqueValues.forEach(val => {
                const option = document.createElement('option');
                option.value = val;
                option.textContent = val;
                option.dataset.searchText = String(val).toLowerCase();
                
                if (filters[col] && filters[col].includes(String(val))) {
                    option.selected = true;
                }
                
                select.appendChild(option);
            });
            
            filterGroup.innerHTML = `<label class="filter-label">${col}</label>`;
            filterGroup.appendChild(searchBox);
            filterGroup.appendChild(select);
            filterContent.appendChild(filterGroup);
            
            // 綁定搜尋事件
            const searchInput = filterGroup.querySelector('.filter-search-input');
            searchInput.addEventListener('input', function(e) {
                const searchTerm = e.target.value.toLowerCase();
                const options = select.querySelectorAll('option');
                
                options.forEach(option => {
                    const text = option.dataset.searchText;
                    option.style.display = text.includes(searchTerm) ? '' : 'none';
                });
            });
        }
    });
    
    if (filterContent.children.length === 0) {
        filterContent.innerHTML = '<p class="text-muted text-center">沒有可篩選的欄位</p>';
    }
}

// 套用篩選器
function applyFilters() {
    filters = {};
    document.querySelectorAll('.filter-select').forEach(select => {
        const column = select.dataset.column;
        const selectedValues = Array.from(select.selectedOptions).map(opt => opt.value);
        if (selectedValues.length > 0) {
            filters[column] = selectedValues;
        }
    });
    
    if (currentSheet) {
        loadSheet(currentSheet);
    }
    
    const filterCount = Object.keys(filters).length;
    const message = filterCount > 0 
        ? `已套用 ${filterCount} 個篩選條件` 
        : '已清除所有篩選';
    
    console.log(message);
    
    document.getElementById('filterPanel').classList.remove('show');
}

// 清除篩選器
function clearFilters() {
    filters = {};
    document.querySelectorAll('.filter-select').forEach(select => {
        select.selectedIndex = -1;
    });
    
    // 清除搜尋框
    document.querySelectorAll('.filter-search-input').forEach(input => {
        input.value = '';
        input.dispatchEvent(new Event('input'));
    });
    
    if (currentSheet) {
        loadSheet(currentSheet);
    }
    
    console.log('已清除篩選');
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
function sortTable(column) {
    const order = sortOrder[column] === 'asc' ? 'desc' : 'asc';
    sortOrder[column] = order;
    
    const sheetData = currentData[currentSheet];
    if (!sheetData || !sheetData.data) return;
    
    sheetData.data.sort((a, b) => {
        const aVal = a[column];
        const bVal = b[column];
        
        if (aVal === null || aVal === undefined) return 1;
        if (bVal === null || bVal === undefined) return -1;
        
        if (typeof aVal === 'number' && typeof bVal === 'number') {
            return order === 'asc' ? aVal - bVal : bVal - aVal;
        }
        
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
    
    const charts = ['distributionChart', 'trendChart'];
    charts.forEach(chartId => {
        const canvas = document.getElementById(chartId);
        if (canvas) {
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            if (window[chartId + 'Instance']) {
                window[chartId + 'Instance'].destroy();
            }
        }
    });
    
    const distCanvas = document.getElementById('distributionChart');
    if (distCanvas) {
        const distCtx = distCanvas.getContext('2d');
        
        let chartData = {};
        
        if (currentSheet === 'revision_diff' || currentSheet === 'branch_error') {
            sheetData.data.forEach(row => {
                const module = row.module;
                if (module) {
                    chartData[module] = (chartData[module] || 0) + 1;
                }
            });
        } else if (currentSheet === 'lost_project') {
            sheetData.data.forEach(row => {
                const status = row['狀態'];
                if (status) {
                    chartData[status] = (chartData[status] || 0) + 1;
                }
            });
        } else {
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
    
    const trendCanvas = document.getElementById('trendChart');
    if (trendCanvas && currentSheet === 'revision_diff') {
        const trendCtx = trendCanvas.getContext('2d');
        
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
        alert('請先選擇資料表');
        return;
    }
    
    if (format === 'excel') {
        window.location.href = `/api/export-sheet/${taskId}/${currentSheet}?format=excel`;
    }
}

// 下載完整報表
function downloadFullReport() {
    window.location.href = `/api/export-excel/${taskId}`;
}

// 匯出整個頁面為 HTML
function exportPageAsHTML() {
    const pageHTML = document.documentElement.outerHTML;
    const blob = new Blob([pageHTML], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report_${taskId}_${new Date().toISOString().slice(0, 10)}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// 監聽資料表選擇
document.getElementById('sheetSelector').addEventListener('change', (e) => {
    if (e.target.value) {
        sortOrder = {};
        searchTerm = '';
        document.getElementById('quickSearchInput').value = '';
        loadSheet(e.target.value);
    }
});

// 監聽視窗大小變化
window.addEventListener('resize', debounce(() => {
    // 不需要同步欄寬，因為表格現在會自動適應
}, 200));

// 匯出函數
window.togglePivotMode = togglePivotMode;
window.applyFilters = applyFilters;
window.clearFilters = clearFilters;
window.toggleFilterPanel = toggleFilterPanel;
window.exportCurrentView = exportCurrentView;
window.downloadFullReport = downloadFullReport;
window.exportPageAsHTML = exportPageAsHTML;