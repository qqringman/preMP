// 結果報表頁面 JavaScript - 使用真實資料

const taskId = window.location.pathname.split('/').pop();
let currentData = null;
let currentSheet = null;
let pivotMode = false;
let filters = {};
let sortOrder = {};
let searchTerm = '';
let currentScenario = 'all';
let currentPivotDropdown = null;
const filterStates = {}; // 動態儲存每個篩選框的狀態
let pivotFilterStates = {}; // 儲存每個欄位的篩選狀態
let currentFilterField = null; // 當前正在篩選的欄位
// 篩選器相關全域變數
let customFilterCurrentElement = null;
let customFilterCurrentData = [];

console.log('Task ID:', taskId);

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('頁面載入完成，開始載入資料...');
    
    // 1. 首先從URL參數讀取情境設定
    initializeScenarioFromURL();
    
    // 2. 初始化情境選擇器
    initializeScenarioSelector();
    
    // 3. 載入資料
    loadPivotData();
    
    // 4. 初始化搜尋功能
    initializeSearch();
});

// 添加這些新函數
async function initializeScenarioSelector() {
    try {
        const response = await fetch(`/api/check-scenarios/${taskId}`);
        const scenarioStatus = await response.json();
        updateScenarioButtons(scenarioStatus);
    } catch (error) {
        console.error('檢查情境失敗:', error);
        document.querySelector('.scenario-selector-container').style.display = 'none';
    }
}

function updateScenarioButtons(scenarioStatus) {
    let hasAnyScenario = false;
    
    // 獲取從 URL 傳入的特定情境
    const urlParams = new URLSearchParams(window.location.search);
    const specificScenario = urlParams.get('scenario');
    
    console.log('更新情境按鈕，特定情境:', specificScenario);
    
    for (const [scenario, exists] of Object.entries(scenarioStatus)) {
        const button = document.querySelector(`[data-scenario="${scenario}"]`);
        if (button) {
            if (exists) {
                // 如果有特定情境參數，只顯示該情境，否則顯示所有可用情境
                if (specificScenario) {
                    if (scenario === specificScenario || scenario === 'all') {
                        button.style.display = 'flex';
                        button.disabled = false;
                        hasAnyScenario = true;
                    } else {
                        button.style.display = 'none';
                    }
                } else {
                    button.style.display = 'flex';
                    button.disabled = false;
                    hasAnyScenario = true;
                }
            } else {
                button.style.display = 'none';
            }
        }
    }
    
    const container = document.querySelector('.scenario-selector-container');
    if (container) {
        // 如果有特定情境，隱藏整個情境選擇器
        if (specificScenario && specificScenario !== 'all') {
            container.style.display = 'none';
        } else {
            container.style.display = hasAnyScenario ? 'block' : 'none';
        }
    }
    
    // 設定當前情境和預選按鈕
    if (specificScenario && specificScenario !== 'all' && scenarioStatus[specificScenario]) {
        // 有特定情境且該情境存在，使用特定情境
        currentScenario = specificScenario;
        setActiveScenarioButton(specificScenario);
        console.log('設定為特定情境:', specificScenario);
    } else if (currentScenario && currentScenario !== 'all' && scenarioStatus[currentScenario]) {
        // 使用已初始化的情境
        setActiveScenarioButton(currentScenario);
        console.log('使用已初始化的情境:', currentScenario);
    } else if (scenarioStatus.all) {
        // 使用全部情境
        currentScenario = 'all';
        setActiveScenarioButton('all');
        console.log('設定為全部情境');
    } else {
        // 最後備案：使用第一個可用的情境
        for (const [scenario, exists] of Object.entries(scenarioStatus)) {
            if (exists) {
                currentScenario = scenario;
                setActiveScenarioButton(scenario);
                console.log('設定為第一個可用情境:', scenario);
                break;
            }
        }
    }
    
    // 重新綁定點擊事件
    rebindScenarioEvents();
}

function setActiveScenarioButton(activeScenario) {
    document.querySelectorAll('.scenario-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    const activeButton = document.querySelector(`[data-scenario="${activeScenario}"]`);
    if (activeButton) {
        activeButton.classList.add('active');
    }
}

// 當點擊情境tab時的處理邏輯
function rebindScenarioEvents() {
    document.querySelectorAll('.scenario-tab').forEach(tab => {
        tab.onclick = function() {
            if (this.style.display === 'none') return;
            
            // 更新視覺狀態
            document.querySelectorAll('.scenario-tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // 設定當前情境並重新載入資料
            const newScenario = this.dataset.scenario;
            currentScenario = newScenario;
            loadPivotData(); // 重新載入該情境的資料
        };
    });
}

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

// 修改 loadPivotData 函數以支援情境
async function loadPivotData() {
    // 根據情境構建 API URL
    let apiUrl = `/api/pivot-data/${taskId}`;
    if (currentScenario !== 'all') {
        apiUrl += `?scenario=${currentScenario}`;
    }
    
    // 載入該情境的專屬資料
    const response = await fetch(apiUrl);
    const data = await response.json();
    
    // 更新頁面顯示
    currentData = data;
    updatePageHeader(); // 顯示當前情境名稱
    populateSheetSelector(data);
    
    // 載入第一個資料表
    const sheets = Object.keys(data);
    if (sheets.length > 0) {
        loadSheet(sheets[0]);
    }
}

// 取得情境的顯示名稱
function getScenarioDisplayName(scenario) {
    const displayNames = {
        'all': '全部情境',
        'master_vs_premp': 'Master vs PreMP',
        'premp_vs_wave': 'PreMP vs Wave', 
        'wave_vs_backup': 'Wave vs Backup'
    };
    return displayNames[scenario] || scenario;
}

// 更新頁面標題以顯示當前情境
// 更新頁面標題以顯示當前情境
function updatePageHeader() {
    const pageSubtitle = document.querySelector('.page-subtitle');
    if (!pageSubtitle) {
        console.warn('找不到頁面副標題元素');
        return;
    }
    
    if (currentScenario !== 'all') {
        // 檢查是否已有情境指示器
        let indicator = pageSubtitle.querySelector('.current-scenario-indicator');
        if (!indicator) {
            indicator = document.createElement('span');
            indicator.className = 'current-scenario-indicator';
            indicator.style.marginLeft = '10px';
            indicator.style.padding = '4px 8px';
            indicator.style.backgroundColor = '#2196F3';
            indicator.style.color = 'white';
            indicator.style.borderRadius = '4px';
            indicator.style.fontSize = '0.85em';
            pageSubtitle.appendChild(indicator);
        }
        
        if (indicator) {
            indicator.innerHTML = `
                <i class="fas fa-filter"></i>
                ${getScenarioDisplayName(currentScenario)}
            `;
        }
    } else {
        // 移除情境指示器
        const indicator = pageSubtitle.querySelector('.current-scenario-indicator');
        if (indicator) {
            indicator.remove();
        }
    }
}

// 填充資料表選擇器
function populateSheetSelector(data) {
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
}

// 顯示載入中
function showLoading() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="100%" style="text-align: center; padding: 0;">
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
                <div class="no-data-container">
                    <div class="no-data-icon">
                        <i class="fas fa-database"></i>
                        <i class="fas fa-slash"></i>
                    </div>
                    <h3>暫無資料可顯示</h3>
                    <p>此任務可能還在處理中，或尚未產生報表。</p>
                    <div class="no-data-actions">
                        <button class="btn btn-primary" onclick="location.reload()">
                            <i class="fas fa-sync-alt"></i> 重新整理
                        </button>
                        <button class="btn btn-outline" onclick="window.history.back()">
                            <i class="fas fa-arrow-left"></i> 返回上一頁
                        </button>
                    </div>
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

// 顯示錯誤訊息 - 簡潔版本
function showErrorMessage(message = '無法載入資料') {
    const tbody = document.getElementById('tableBody');
    
    // 提取 HTTP 錯誤碼
    let errorCode = '';
    if (message.includes('404')) {
        errorCode = 'HTTP 404';
    } else if (message.includes('500')) {
        errorCode = 'HTTP 500';
    }
    
    tbody.innerHTML = `
        <tr>
            <td colspan="100%" style="padding: 0; border: none;">
                <div class="simple-error">
                    <div class="simple-error-icon">
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                    <div class="simple-error-title">找不到資料</div>
                    <div class="simple-error-message">請確認資料檔案是否存在</div>
                    ${errorCode ? `<div class="simple-error-code">${errorCode}</div>` : ''}
                    <button class="simple-error-action" onclick="location.reload()">
                        <i class="fas fa-redo"></i> 重試
                    </button>
                </div>
            </td>
        </tr>
    `;
    
    // 清空統計資料
    document.getElementById('statsGrid').innerHTML = '';
    
    // 移除統計條
    const statsBar = document.querySelector('.table-stats-bar');
    if (statsBar) {
        statsBar.remove();
    }
}

// 取得資料表顯示名稱
function getSheetDisplayName(sheetName) {
    const displayNames = {
        'revision_diff': 'Revision差異',
        'branch_error': '分支錯誤',
        'lost_project': '新增刪除專案',  // 移除 /
        'version_diff': '版本檔案差異',
        '無法比對': '無法比對的模組',
        '摘要': '比對摘要',
        'all_scenarios': '所有情境摘要',
        'master_vs_premp': 'Master vs PreMP',
        'premp_vs_wave': 'PreMP vs Wave',
        'wave_vs_backup': 'Wave vs Backup'
    };
    
    let displayName = displayNames[sheetName] || sheetName;
    
    // 移除或替換Excel工作表名稱不支援的特殊字符
    displayName = displayName.replace(/[\\\/\?\*\[\]:]/g, '_');
    
    // 限制長度（Excel工作表名稱最長31個字符）
    if (displayName.length > 31) {
        displayName = displayName.substring(0, 28) + '...';
    }
    
    return displayName;
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

// 渲染資料表格 - 完整版本（配合新的表格結構）
function renderDataTable(sheetData) {
    console.log('開始渲染資料表格', sheetData);
    
    // 取得 DOM 元素 - 支援新舊結構
    let thead, tbody;
    
    // 嘗試新結構
    const headerTable = document.querySelector('.table-header-container .data-table');
    const bodyTable = document.querySelector('.table-body-container .data-table');
    
    if (headerTable && bodyTable) {
        // 新結構
        thead = headerTable.querySelector('thead');
        tbody = bodyTable.querySelector('tbody');
        
        // 如果 thead 不存在，創建它
        if (!thead) {
            thead = document.createElement('thead');
            headerTable.appendChild(thead);
        }
    } else {
        // 舊結構（fallback）
        thead = document.getElementById('tableHead');
        tbody = document.getElementById('tableBody');
    }
    
    // 檢查元素是否存在
    if (!thead || !tbody) {
        console.error('找不到表格元素', { thead, tbody });
        return;
    }
    
    // 清空現有內容
    thead.innerHTML = '';
    tbody.innerHTML = '';
    
    // 檢查是否有資料
    if (!sheetData || !sheetData.data || sheetData.data.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="100%" style="padding: 0; border: none;">
                    <div class="no-data-message">
                        <i class="fas fa-inbox"></i>
                        <h3>此資料表沒有資料</h3>
                    </div>
                </td>
            </tr>
        `;
        updateTableStats(0, 0, 0);
        return;
    }
    
    // 取得欄位列表
    let columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
    console.log('原始欄位:', columns);
    
    // 【只保留版本檔案差異的 SN 欄位移至第一欄】
    if (currentSheet === 'version_diff' || currentSheet === '版本檔案差異') {
        const snIndex = columns.indexOf('SN');
        if (snIndex > -1 && snIndex !== 0) {
            columns.splice(snIndex, 1);
            columns.unshift('SN');
            console.log('版本檔案差異SN移至首位:', columns);
        }
    }
    
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
    
    // 更新統計資訊
    updateTableStats(sheetData.data.length, filteredData.length, searchMatches);
    
    // 建立表頭
    const headerRow = document.createElement('tr');
    columns.forEach((col, index) => {
        const th = document.createElement('th');
        th.style.width = getColumnWidth(col);
        th.style.minWidth = getColumnWidth(col);
        
        // 設定標頭顏色
        if (col === 'base_content' || col === 'compare_content') {
            th.classList.add('base-content-header');
        } else if (col === 'problem' || col === '問題') {
            th.classList.add('danger-header');
        } else if ((currentSheet === 'lost_project' || currentSheet === '新增/刪除專案') && 
                (col === 'base_folder' || col === 'Base folder' || col === '狀態')) {
            th.classList.add('danger-header');
        } else if (currentSheet === 'revision_diff' && 
                ['base_short', 'base_revision', 'compare_short', 'compare_revision'].includes(col)) {
            th.classList.add('danger-header');
        }
        
        // 建立標頭內容
        const thContent = document.createElement('div');
        thContent.className = 'th-content';
        
        const thText = document.createElement('span');
        thText.className = 'th-text';
        thText.textContent = col;
        
        const thIcons = document.createElement('span');
        thIcons.className = 'th-icons';
        
        // 排序圖示
        const sortIcon = document.createElement('i');
        sortIcon.className = 'fas fa-sort sort-icon';
        if (sortOrder[col]) {
            sortIcon.className = sortOrder[col] === 'asc' ? 
                'fas fa-sort-up sort-icon active' : 
                'fas fa-sort-down sort-icon active';
        }
        
        thIcons.appendChild(sortIcon);
        
        // 篩選圖示
        if (filters[col]) {
            const filterIcon = document.createElement('i');
            filterIcon.className = 'fas fa-filter filter-icon active';
            thIcons.appendChild(filterIcon);
        }
        
        thContent.appendChild(thText);
        thContent.appendChild(thIcons);
        th.appendChild(thContent);
        
        // 綁定排序事件
        th.onclick = () => sortTable(col);
        th.style.cursor = 'pointer';
        
        // 加入拖曳功能屬性
        th.draggable = true;
        th.dataset.column = index;
        
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
            
            // 根據欄位類型添加 class
            td.classList.add('path-cell');

            // 根據欄位類型處理顯示
            if (col === 'path' || col.toLowerCase().includes('path')) {
                td.classList.add('path-cell');
                
                if (value && value.length > 80) {
                    // 使用 tooltip 顯示完整路徑
                    const truncated = value.substring(0, 40) + '...' + value.substring(value.length - 35);
                    td.innerHTML = `
                        <span class="truncated-content" title="${value}">
                            ${searchTerm ? highlightText(truncated, searchTerm) : truncated}
                        </span>
                    `;
                } else {
                    td.innerHTML = searchTerm ? highlightText(value || '', searchTerm) : (value || '');
                }
            } else if (col === 'base_content' || col === 'compare_content') {
                td.classList.add('content-cell');
                
                if (value) {
                    if (value === '(檔案不存在)' || value === '(檔案存在)') {
                        if (value === '(檔案不存在)') {
                            td.classList.add('highlight-red');
                        }
                        td.innerHTML = searchTerm ? highlightText(value, searchTerm) : value;
                    } else {
                        // 獲取對應的比較值
                        const isBaseContent = col === 'base_content';
                        const compareCol = isBaseContent ? 'compare_content' : 'base_content';
                        const compareValue = row[compareCol];
                        
                        let formattedValue = String(value);
                        
                        // 【修正】檢查是否包含多行內容，添加分隔線
                        if (value.includes('\n') || value.includes('P_GIT_')) {
                            // 多行內容需要添加分隔線
                            formattedValue = formatMultiLineContentWithDivider(value, compareValue, row['file_type']);
                        } else if (value.includes('F_HASH:')) {
                            if (compareValue) {
                                formattedValue = formatFHashContent(value, compareValue);
                            }
                        } else if (value.includes(':')) {
                            if (compareValue && compareValue.includes(':')) {
                                formattedValue = formatColonContent(value, compareValue);
                            }
                        }
                        
                        if (searchTerm) {
                            formattedValue = highlightText(formattedValue, searchTerm);
                        }
                        
                        td.innerHTML = formattedValue;
                    }
                } else {
                    td.innerHTML = '';
                }
            } else if (col === 'file_type') {
                // 檔案類型欄位
                td.classList.add('file-type');
                td.innerHTML = searchTerm ? highlightText(value || '', searchTerm) : (value || '');
            } else if (col === 'org_folder') {
                // 組織資料夾欄位
                td.classList.add('org-cell');
                td.innerHTML = searchTerm ? highlightText(value || '', searchTerm) : (value || '');
            } else if (col.includes('link') && value && typeof value === 'string' && value.startsWith('http')) {
                // 連結欄位
                td.innerHTML = `<a href="${value}" target="_blank" class="link">
                    <i class="fas fa-external-link-alt"></i> 查看
                </a>`;
            } else if (col === 'has_wave' || col === 'is_different') {
                // 布林值欄位
                const badgeClass = value === 'Y' ? 'badge-success' : 'badge-default';
                td.innerHTML = `<span class="badge ${badgeClass}">${value || 'N'}</span>`;
            } else if (col === '狀態') {
                // 狀態欄位
                let badgeClass = 'badge-default';
                if (value === '新增') badgeClass = 'badge-success';
                else if (value === '刪除') badgeClass = 'badge-danger';
                else if (value === '修改') badgeClass = 'badge-warning';
                td.innerHTML = `<span class="badge ${badgeClass}">${value || ''}</span>`;
            } else if (col === 'problem' && value) {
                // 問題欄位
                const highlightedValue = searchTerm ? highlightText(value, searchTerm) : value;
                td.innerHTML = `<span class="text-danger font-weight-bold">${highlightedValue}</span>`;
            } else if (['base_short', 'base_revision', 'compare_short', 'compare_revision'].includes(col) && value) {
                // 版本相關欄位
                td.classList.add('highlight-hash');
                td.innerHTML = searchTerm ? highlightText(value, searchTerm) : value;
                td.classList.add('highlight-red');
            } else {
                // 一般欄位
                const textValue = value !== null && value !== undefined ? value : '';
                td.innerHTML = searchTerm ? highlightText(textValue, searchTerm) : textValue;
            }
            
            tr.appendChild(td);
        });
        
        tbody.appendChild(tr);
    });
    
    // 當篩選後沒有資料時
    if (filteredData.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="${columns.length}" style="padding: 0; border: none;">
                    <div class="no-data-message">
                        <i class="fas fa-filter"></i>
                        <h3>沒有符合搜尋或篩選條件的資料</h3>
                    </div>
                </td>
            </tr>
        `;
        updateTableStats(sheetData.data.length, 0, 0);
    }

    // 控制浮動篩選按鈕的顯示
    const fabFilter = document.getElementById('fabFilter');
    if (fabFilter) {
        if (sheetData.data && sheetData.data.length > 0) {
            fabFilter.style.display = 'flex';
        } else {
            fabFilter.style.display = 'none';
        }
    }

    setTimeout(() => {
        try {
            // 同步標頭和內容的橫向捲動
            const bodyContainer = document.querySelector('.table-body-container');
            const headerContainer = document.querySelector('.table-header-container');
            const tableView = document.getElementById('tableView');
            
            // 設定 data-sheet 屬性以應用特定樣式（版本檔案差異的分隔線）
            if (tableView && currentSheet) {
                let dataSheetValue = currentSheet;
                
                // 統一工作表名稱映射
                if (currentSheet === '版本檔案差異') {
                    dataSheetValue = 'version_diff';
                } else if (currentSheet === '分支錯誤') {
                    dataSheetValue = 'branch_error';
                } else if (currentSheet === 'Revision差異') {
                    dataSheetValue = 'revision_diff';
                }
                
                tableView.setAttribute('data-sheet', dataSheetValue);
                console.log('設定 data-sheet 屬性:', dataSheetValue);
            }
            
            if (bodyContainer && headerContainer) {
                // 移除舊的事件監聽器
                const newBodyContainer = bodyContainer.cloneNode(true);
                bodyContainer.parentNode.replaceChild(newBodyContainer, bodyContainer);
                
                // 添加新的捲動同步
                newBodyContainer.addEventListener('scroll', function() {
                    headerContainer.scrollLeft = this.scrollLeft;
                });
                
                // 同步表格寬度
                const headerTable = headerContainer.querySelector('table');
                const bodyTable = newBodyContainer.querySelector('table');
                
                if (headerTable && bodyTable) {
                    // 確保兩個表格有相同的寬度
                    const computedWidth = Math.max(1200, headerTable.scrollWidth, bodyTable.scrollWidth);
                    headerTable.style.width = computedWidth + 'px';
                    bodyTable.style.width = computedWidth + 'px';
                    
                    // 同步每個欄位的寬度
                    const headerCells = headerTable.querySelectorAll('th');
                    const firstBodyRow = bodyTable.querySelector('tr');
                    
                    if (firstBodyRow && firstBodyRow.cells.length > 0) {
                        const bodyCells = firstBodyRow.querySelectorAll('td');
                        
                        // 先計算每個欄位應有的寬度
                        const columnWidths = [];
                        headerCells.forEach((th, index) => {
                            const td = bodyCells[index];
                            if (td) {
                                // 取標頭和內容中較寬的那個
                                const maxWidth = Math.max(
                                    th.getBoundingClientRect().width,
                                    td.getBoundingClientRect().width
                                );
                                columnWidths.push(maxWidth);
                            }
                        });
                        
                        // 應用計算出的寬度
                        headerCells.forEach((th, index) => {
                            if (columnWidths[index]) {
                                th.style.width = columnWidths[index] + 'px';
                                th.style.minWidth = columnWidths[index] + 'px';
                                th.style.maxWidth = columnWidths[index] + 'px';
                            }
                        });
                        
                        // 對所有內容行應用相同寬度
                        const allBodyRows = bodyTable.querySelectorAll('tr');
                        allBodyRows.forEach(row => {
                            const cells = row.querySelectorAll('td');
                            cells.forEach((td, index) => {
                                if (columnWidths[index]) {
                                    td.style.width = columnWidths[index] + 'px';
                                    td.style.minWidth = columnWidths[index] + 'px';
                                    td.style.maxWidth = columnWidths[index] + 'px';
                                }
                            });
                        });
                    }
                }
            }
            
            // 啟用拖曳功能
            enableTableFeatures();
            
        } catch (error) {
            console.error('同步表格時發生錯誤:', error);
        }
    }, 100);
}

function formatMultiLineContentWithDivider(value, compareValue, fileType) {
    if (!value) return value;
    
    const lines = value.split('\n');
    let compareLines = [];
    
    if (compareValue) {
        compareLines = compareValue.split('\n');
    }
    
    // 建立比較行的映射表
    const compareMap = {};
    compareLines.forEach(line => {
        if (line.startsWith('P_GIT_')) {
            const gitId = line.split(';')[0];
            compareMap[gitId] = line;
        } else if (line.includes(':')) {
            const key = line.split(':')[0].trim();
            compareMap[key] = line;
        } else {
            compareMap[line.substring(0, 20)] = line;
        }
    });
    
    let formattedLines = [];
    
    lines.forEach((line, index) => {
        let compareLine = '';
        let formattedLine = line;
        
        if (line.startsWith('P_GIT_')) {
            const gitId = line.split(';')[0];
            compareLine = compareMap[gitId] || '';
            
            if (compareLine) {
                // 直接比較並格式化 P_GIT 行
                const parts1 = line.split(';');
                const parts2 = compareLine.split(';');
                
                if (parts1.length >= 5 && parts2.length >= 5) {
                    let result = '';
                    for (let i = 0; i < parts1.length; i++) {
                        if (i > 0) result += ';';
                        
                        // 索引 3 是 git hash，索引 4 是 revision
                        if ((i === 3 || i === 4) && parts1[i] !== parts2[i]) {
                            result += `<span class="highlight-red" style="color: #dc3545 !important; font-weight: 600 !important;">${parts1[i]}</span>`;
                        } else {
                            result += parts1[i];
                        }
                    }
                    formattedLine = result;
                }
            }
        } else if (line.includes(':')) {
            const key = line.split(':')[0].trim();
            compareLine = compareMap[key] || '';
            
            if (compareLine) {
                const val1 = line.split(':')[1]?.trim() || '';
                const val2 = compareLine.split(':')[1]?.trim() || '';
                
                if (val1 !== val2) {
                    formattedLine = `${key}: <span class="highlight-red" style="color: #dc3545 !important; font-weight: 600 !important;">${val1}</span>`;
                }
            }
        }
        
        // 【關鍵】添加分隔線，除了最後一行
        if (index < lines.length - 1) {
            formattedLine += '<div class="content-divider"></div>';
        }
        
        formattedLines.push(formattedLine);
    });
    
    return formattedLines;
}

function formatMultiLineContent(value, compareValue, fileType) {
    if (!value) return value;
    if (!compareValue) return value; // 如果沒有比較值，返回原值
    
    const lines = value.split('\n');
    const compareLines = compareValue.split('\n');
    
    // 建立比較行的映射表
    const compareMap = {};
    compareLines.forEach(line => {
        if (line.startsWith('P_GIT_')) {
            const gitId = line.split(';')[0];
            compareMap[gitId] = line;
        } else if (line.includes(':')) {
            const key = line.split(':')[0].trim();
            compareMap[key] = line;
        } else {
            // 對於其他格式，使用整行作為 key
            compareMap[line.substring(0, 20)] = line;
        }
    });
    
    let formattedLines = [];
    
    lines.forEach((line) => {
        let compareLine = '';
        let formattedLine = line;
        
        if (line.startsWith('P_GIT_')) {
            const gitId = line.split(';')[0];
            compareLine = compareMap[gitId] || '';
            
            if (compareLine) {
                // 直接比較並格式化 P_GIT 行
                const parts1 = line.split(';');
                const parts2 = compareLine.split(';');
                
                if (parts1.length >= 5 && parts2.length >= 5) {
                    let result = '';
                    for (let i = 0; i < parts1.length; i++) {
                        if (i > 0) result += ';';
                        
                        // 索引 3 是 git hash，索引 4 是 revision
                        if ((i === 3 || i === 4) && parts1[i] !== parts2[i]) {
                            result += `<span class="highlight-red" style="color: #dc3545 !important; font-weight: 600 !important;">${parts1[i]}</span>`;
                        } else {
                            result += parts1[i];
                        }
                    }
                    formattedLine = result;
                }
            }
        } else if (line.includes(':')) {
            const key = line.split(':')[0].trim();
            compareLine = compareMap[key] || '';
            
            if (compareLine) {
                const val1 = line.split(':')[1]?.trim() || '';
                const val2 = compareLine.split(':')[1]?.trim() || '';
                
                if (val1 !== val2) {
                    formattedLine = `${key}: <span class="highlight-red" style="color: #dc3545 !important; font-weight: 600 !important;">${val1}</span>`;
                }
            }
        }
        
        formattedLines.push(formattedLine);
    });
    
    return formattedLines.join('<br>');
}

// 啟用表格功能（拖曳和調整寬度）
function enableTableFeatures() {
    // 嘗試新結構
    let headers;
    const headerTable = document.querySelector('.table-header-container .data-table');
    
    if (headerTable) {
        // 新結構 - 從 header-only 表格取得標頭
        headers = headerTable.querySelectorAll('th');
    } else {
        // 舊結構（fallback）
        const table = document.getElementById('dataTable');
        if (table) {
            headers = table.querySelectorAll('th');
        }
    }
    
    // 如果找不到標頭，直接返回
    if (!headers || headers.length === 0) {
        console.log('找不到表格標頭，跳過表格功能初始化');
        return;
    }
    
    headers.forEach((header, index) => {
        // 創建調整寬度的手柄
        const resizer = document.createElement('div');
        resizer.className = 'column-resizer';
        resizer.addEventListener('mousedown', initResize);
        resizer.dataset.column = index;
        header.appendChild(resizer);
        
        // 啟用拖曳
        header.addEventListener('dragstart', handleDragStart);
        header.addEventListener('dragover', handleDragOver);
        header.addEventListener('drop', handleDrop);
        header.addEventListener('dragend', handleDragEnd);
    });
}

let startX, startWidth, resizingColumn;

function initResize(e) {
    resizingColumn = e.target.parentElement;
    startX = e.pageX;
    startWidth = resizingColumn.offsetWidth;
    
    document.addEventListener('mousemove', doResize);
    document.addEventListener('mouseup', stopResize);
    e.preventDefault();
}

function doResize(e) {
    if (resizingColumn) {
        const width = startWidth + e.pageX - startX;
        resizingColumn.style.width = width + 'px';
        resizingColumn.style.minWidth = width + 'px';
        
        // 同步內容表格的欄寬（新結構）
        const columnIndex = Array.from(resizingColumn.parentElement.children).indexOf(resizingColumn);
        const bodyTable = document.querySelector('.table-body-container .data-table');
        
        if (bodyTable) {
            const firstRow = bodyTable.querySelector('tbody tr');
            if (firstRow && firstRow.cells[columnIndex]) {
                firstRow.cells[columnIndex].style.width = width + 'px';
                firstRow.cells[columnIndex].style.minWidth = width + 'px';
            }
        }
    }
}

function stopResize() {
    resizingColumn = null;
    document.removeEventListener('mousemove', doResize);
    document.removeEventListener('mouseup', stopResize);
}

let draggedColumn = null;

function handleDragStart(e) {
    draggedColumn = this;
    e.dataTransfer.effectAllowed = 'move';
    this.classList.add('dragging');
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    
    const afterElement = getDragAfterElement(e.currentTarget.parentElement, e.clientX);
    if (afterElement == null) {
        e.currentTarget.parentElement.appendChild(draggedColumn);
    } else {
        e.currentTarget.parentElement.insertBefore(draggedColumn, afterElement);
    }
    
    return false;
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }
    return false;
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
    
    // 重新排序表格內容
    reorderTableColumns();
}

function getDragAfterElement(container, x) {
    const draggableElements = [...container.querySelectorAll('th:not(.dragging)')];
    
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = x - box.left - box.width / 2;
        
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function reorderTableColumns() {
    // 嘗試新結構
    const headerTable = document.querySelector('.table-header-container .data-table');
    const bodyTable = document.querySelector('.table-body-container .data-table');
    
    let headerCells, rows;
    
    if (headerTable && bodyTable) {
        // 新結構
        headerCells = Array.from(headerTable.querySelectorAll('thead th'));
        rows = bodyTable.querySelectorAll('tbody tr');
    } else {
        // 舊結構（fallback）
        const table = document.getElementById('dataTable');
        if (!table) return;
        
        headerCells = Array.from(table.querySelectorAll('thead th'));
        rows = table.querySelectorAll('tbody tr');
    }
    
    if (!headerCells || headerCells.length === 0) return;
    
    const newOrder = headerCells.map((th, index) => parseInt(th.dataset.column));
    
    // 重新排序所有行的單元格
    rows.forEach(row => {
        const cells = Array.from(row.cells);
        const reorderedCells = newOrder.map(oldIndex => cells[oldIndex]);
        
        row.innerHTML = '';
        reorderedCells.forEach(cell => {
            if (cell) row.appendChild(cell);
        });
    });
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
    
    // 更新搜尋計數
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

let pivotInitialData = null;
let pivotInitialConfig = null;

function renderPivotTable(sheetData) {
    const container = document.getElementById('pivotContainer');
    container.innerHTML = '';
    
    if (!sheetData.data || sheetData.data.length === 0) {
        container.innerHTML = '<div class="empty-message">沒有資料可供分析</div>';
        return;
    }
    
    // 儲存原始資料和配置
    pivotData = sheetData.data;
    pivotInitialData = JSON.parse(JSON.stringify(sheetData.data)); // 深拷貝
    
    // 定義初始配置
    pivotInitialConfig = {
        rows: [],
        cols: [],
        vals: [],
        aggregatorName: "Count",
        rendererName: "Table",
        unusedAttrsVertical: true,
        renderers: $.pivotUtilities.renderers,
        aggregators: $.pivotUtilities.aggregators,
        localeStrings: {
            renderError: "結果計算錯誤",
            computeError: "資料計算錯誤",
            uiRenderError: "介面繪製錯誤",
            aggregators: {
                "Count": "計數",
                "Count Unique Values": "計數唯一值",
                "List Unique Values": "列出唯一值",
                "Sum": "總和",
                "Integer Sum": "整數總和",
                "Average": "平均",
                "Median": "中位數",
                "Sample Variance": "樣本變異數",
                "Sample Standard Deviation": "樣本標準差",
                "Minimum": "最小值",
                "Maximum": "最大值",
                "First": "第一個",
                "Last": "最後一個",
                "Sum over Sum": "總和比例",
                "Sum as Fraction of Total": "總和佔比",
                "Sum as Fraction of Rows": "列總和佔比",
                "Sum as Fraction of Columns": "欄總和佔比",
                "Count as Fraction of Total": "計數佔比",
                "Count as Fraction of Rows": "列計數佔比",
                "Count as Fraction of Columns": "欄計數佔比"
            },
            renderers: {
                "Table": "表格",
                "Table Barchart": "表格長條圖",
                "Heatmap": "熱圖",
                "Row Heatmap": "列熱圖",
                "Col Heatmap": "欄熱圖"
            }
        },
        onRefresh: function(config) {
            pivotConfig = config;
        }
    };
    
    try {
        $(container).pivotUI(pivotInitialData, pivotInitialConfig);
        // 移除 fixPivotDropdownPosition 調用
    } catch (error) {
        console.error('樞紐分析錯誤:', error);
        container.innerHTML = '<div class="error-message">樞紐分析表載入失敗</div>';
    }
}

function resetPivotTable() {
    if (!pivotData) {
        showAlertDialog('提示', '沒有資料可重置', 'warning');
        return;
    }
    
    showConfirmDialog(
        '重置樞紐分析表',
        '確定要重置樞紐分析表嗎？這將清除所有已拖曳的欄位設定。',
        () => {
            try {
                // 獲取當前的樞紐分析表配置
                const pivotUIOptions = $('#pivotContainer').data("pivotUIOptions");
                
                if (pivotUIOptions) {
                    // 清空行、列、值區域的欄位
                    pivotUIOptions.rows = [];
                    pivotUIOptions.cols = [];
                    pivotUIOptions.vals = [];
                    
                    // 重置聚合方式和渲染器為預設值
                    pivotUIOptions.aggregatorName = "Count";
                    pivotUIOptions.rendererName = "Table";
                    
                    // 保持其他設定不變（如 localeStrings）
                    const container = document.getElementById('pivotContainer');
                    $(container).empty();
                    
                    // 使用更新後的配置重新渲染
                    $(container).pivotUI(pivotData, pivotUIOptions);
                    
                    // 如果目前是隱藏拖曳區的狀態，重新應用
                    if (!areasVisible) {
                        setTimeout(() => {
                            $('.pvtUnused, .pvtRows, .pvtCols, .pvtVals').hide();
                            $('.pvtRenderer, .pvtAggregator, .pvtAttrDropdown').parent().hide();
                        }, 100);
                    }
                    
                    showToast('樞紐分析表欄位已清空', 'success');
                } else {
                    // 如果無法獲取配置，則重新載入
                    renderPivotTable(currentData[currentSheet]);
                    showToast('樞紐分析表已重置', 'success');
                }
            } catch (error) {
                console.error('重置失敗:', error);
                // 發生錯誤時重新載入
                renderPivotTable(currentData[currentSheet]);
                showToast('樞紐分析表已重置', 'success');
            }
        }
    );
}

// 匯出樞紐分析表
function exportPivotTable() {
    try {
        const pivotTable = document.querySelector('#pivotContainer .pvtTable');
        
        if (!pivotTable) {
            showAlertDialog('提示', '請先建立樞紐分析表', 'warning');
            return;
        }
        
        const exportHtml = `
            <div class="custom-dialog-overlay">
                <div class="custom-dialog export-dialog">
                    <div class="dialog-header">
                        <i class="fas fa-file-export"></i>
                        <h3>選擇匯出格式</h3>
                    </div>
                    <div class="dialog-body export-options">
                        <button class="export-option" data-format="1">
                            <i class="fas fa-file-excel"></i>
                            <span>Excel (.xlsx)</span>
                        </button>
                        <button class="export-option" data-format="2">
                            <i class="fas fa-file-csv"></i>
                            <span>CSV (.csv)</span>
                        </button>
                        <button class="export-option" data-format="3">
                            <i class="fas fa-file-code"></i>
                            <span>HTML (.html)</span>
                        </button>
                    </div>
                    <div class="dialog-footer">
                        <button class="btn btn-outline btn-sm" id="exportCancel">
                            <i class="fas fa-times"></i> 取消
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        const dialogElement = document.createElement('div');
        dialogElement.innerHTML = exportHtml;
        
        // 檢查是否在全螢幕模式
        const fullscreenElement = document.fullscreenElement;
        if (fullscreenElement) {
            fullscreenElement.appendChild(dialogElement);
        } else {
            document.body.appendChild(dialogElement);
        }
        
        setTimeout(() => {
            dialogElement.querySelector('.custom-dialog-overlay').classList.add('show');
            dialogElement.querySelector('.custom-dialog').classList.add('show');
        }, 10);
        
        const closeDialog = () => {
            dialogElement.querySelector('.custom-dialog-overlay').classList.remove('show');
            dialogElement.querySelector('.custom-dialog').classList.remove('show');
            setTimeout(() => {
                if (fullscreenElement && dialogElement.parentNode === fullscreenElement) {
                    fullscreenElement.removeChild(dialogElement);
                } else {
                    document.body.removeChild(dialogElement);
                }
            }, 300);
        };
        
        const cancelBtn = document.getElementById('exportCancel');
        const exportOptions = dialogElement.querySelectorAll('.export-option');
        
        cancelBtn.addEventListener('click', closeDialog);
        
        exportOptions.forEach(option => {
            option.addEventListener('click', () => {
                const format = option.dataset.format;
                closeDialog();
                
                switch(format) {
                    case '1':
                        exportPivotToExcel(pivotTable);
                        break;
                    case '2':
                        exportPivotToCSV(pivotTable);
                        break;
                    case '3':
                        exportPivotToHTML(pivotTable);
                        break;
                }
            });
        });
        
    } catch (error) {
        console.error('匯出錯誤:', error);
        showAlertDialog('錯誤', '匯出失敗：' + error.message, 'error');
    }
}

// 匯出為 Excel
function exportPivotToExcel(table) {
    try {
        // 將 HTML 表格轉換為工作表
        const worksheet = XLSX.utils.table_to_sheet(table);
        const workbook = XLSX.utils.book_new();
        
        // 添加工作表
        XLSX.utils.book_append_sheet(workbook, worksheet, '樞紐分析結果');
        
        // 生成檔案
        const timestamp = new Date().toISOString().slice(0, 10);
        XLSX.writeFile(workbook, `pivot_analysis_${timestamp}.xlsx`);
        
        showToast('Excel 檔案已匯出', 'success');
    } catch (error) {
        console.error('Excel 匯出錯誤:', error);
        alert('Excel 匯出失敗');
    }
}

// 匯出為 CSV
function exportPivotToCSV(table) {
    try {
        const rows = table.querySelectorAll('tr');
        let csv = [];
        
        rows.forEach(row => {
            const cells = row.querySelectorAll('th, td');
            const rowData = Array.from(cells).map(cell => {
                // 處理包含逗號的內容
                let text = cell.textContent.trim();
                if (text.includes(',') || text.includes('"') || text.includes('\n')) {
                    text = '"' + text.replace(/"/g, '""') + '"';
                }
                return text;
            });
            csv.push(rowData.join(','));
        });
        
        // 創建 Blob 並下載
        const csvContent = '\ufeff' + csv.join('\n'); // 添加 BOM 支援中文
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `pivot_analysis_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        showToast('CSV 檔案已匯出', 'success');
    } catch (error) {
        console.error('CSV 匯出錯誤:', error);
        alert('CSV 匯出失敗');
    }
}

// 匯出為 HTML
function exportPivotToHTML(table) {
    try {
        const htmlContent = `
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>樞紐分析結果 - ${currentSheet} - ${taskId}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #1A237E;
            margin-bottom: 10px;
        }
        .meta {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        th {
            background: #2196F3;
            color: white;
            font-weight: 600;
        }
        tr:nth-child(even) {
            background: #f9f9f9;
        }
        tr:hover {
            background: #f0f0f0;
        }
        .pvtTotal {
            background: #E3F2FD !important;
            font-weight: 600;
        }
        .pvtGrandTotal {
            background: #1976D2 !important;
            color: white !important;
            font-weight: 700;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>樞紐分析結果</h1>
        <div class="meta">
            <p>資料表：${currentSheet}</p>
            <p>任務 ID：${taskId}</p>
            <p>匯出時間：${new Date().toLocaleString('zh-TW')}</p>
        </div>
        ${table.outerHTML}
    </div>
</body>
</html>
        `;
        
        // 創建 Blob 並下載
        const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `pivot_analysis_${currentSheet}_${new Date().toISOString().slice(0, 10)}.html`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        showToast('HTML 檔案已匯出', 'success');
    } catch (error) {
        console.error('HTML 匯出錯誤:', error);
        alert('HTML 匯出失敗');
    }
}

// 顯示提示訊息 - 支援置中顯示
function showToast(message, type = 'info', centered = false) {
    // 如果是切換情境的訊息，使用置中顯示
    if (message.includes('切換至') || centered) {
        showCenteredToast(message, type);
        return;
    }
    
    // 原有的底部提示邏輯
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-info-circle'}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// 顯示置中的提示訊息
function showCenteredToast(message, type = 'info') {
    // 創建遮罩層
    const overlay = document.createElement('div');
    overlay.className = 'toast-overlay';
    
    // 創建提示元素
    const toast = document.createElement('div');
    toast.className = `toast-center toast-${type}`;
    
    const iconMap = {
        'info': 'fa-info-circle',
        'success': 'fa-check-circle',
        'warning': 'fa-exclamation-triangle',
        'error': 'fa-times-circle'
    };
    
    toast.innerHTML = `
        <i class="fas ${iconMap[type]}"></i>
        <span>${message}</span>
    `;
    
    // 添加到頁面
    const fullscreenElement = document.fullscreenElement || document.querySelector('.fullscreen');
    if (fullscreenElement) {
        fullscreenElement.appendChild(overlay);
    } else {
        document.body.appendChild(overlay);
    }
    document.body.appendChild(toast);
    
    // 顯示動畫
    setTimeout(() => {
        overlay.classList.add('show');
        toast.classList.add('show');
    }, 10);
    
    // 1.5秒後移除
    setTimeout(() => {
        overlay.classList.remove('show');
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(overlay);
            document.body.removeChild(toast);
        }, 300);
    }, 1500);
}

// 匯出函數
window.resetPivotTable = resetPivotTable;
window.exportPivotTable = exportPivotTable;

// 同時檢查 togglePivotMode 函數，確保正確呼叫
function togglePivotMode() {
    pivotMode = !pivotMode;
    
    document.getElementById('tableView').classList.toggle('hidden', pivotMode);
    document.getElementById('pivotView').classList.toggle('hidden', !pivotMode);
    
    // 控制 table-stats-bar 的顯示/隱藏
    const statsBar = document.querySelector('.table-stats-bar');
    if (statsBar) {
        if (pivotMode) {
            statsBar.style.display = 'none';
        } else {
            statsBar.style.display = 'flex';
        }
    }
    
    const pivotIcon = document.getElementById('pivotIcon');
    if (pivotMode) {
        pivotIcon.classList.remove('fa-chart-pie');
        pivotIcon.classList.add('fa-table');
        pivotIcon.parentElement.classList.add('active');
        
        // 確保有資料才載入樞紐分析
        if (currentSheet && currentData && currentData[currentSheet]) {
            console.log('切換到樞紐分析模式，載入資料表:', currentSheet);
            renderPivotTable(currentData[currentSheet]);
        } else {
            console.warn('沒有選擇資料表或資料不存在');
            const container = document.getElementById('pivotContainer');
            container.innerHTML = `
                <div class="no-data-message">
                    <i class="fas fa-table"></i>
                    <h3>請先選擇資料表</h3>
                </div>
            `;
        }
    } else {
        pivotIcon.classList.remove('fa-table');
        pivotIcon.classList.add('fa-chart-pie');
        pivotIcon.parentElement.classList.remove('active');
        
        // 切換回表格模式時重新載入資料
        if (currentSheet) {
            loadSheet(currentSheet);
        }
    }
}

// 更新統計資料
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
        }
    ];
    
    // 根據資料表類型調整統計
    if (currentSheet === 'revision_diff') {
        // revision_diff 的統計保持不變
        const differentRevisions = sheetData.data.length;
        const uniqueModules = new Set(sheetData.data.map(row => row.module).filter(m => m));
        const hasWaveY = sheetData.data.filter(row => row.has_wave === 'Y').length;
        const hasWaveN = sheetData.data.filter(row => row.has_wave === 'N').length;
        
        stats.push({
            label: '不同版號',
            value: differentRevisions,
            icon: 'fa-code-branch',
            color: 'warning'
        });
        
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
    } else if (currentSheet === '摘要' || currentSheet === '比對摘要' || currentSheet === 'summary') {
        // 【修正】比對摘要的統計邏輯
        let totalSuccess = 0;
        let totalFailed = 0;
        let validItemCount = 0;
        
        console.log('比對摘要統計開始 - 資料筆數:', sheetData.data.length);
        
        sheetData.data.forEach((row, index) => {
            console.log(`=== 第${index+1}行分析 ===`);
            console.log('完整行資料:', row);
            console.log('所有欄位名稱:', Object.keys(row));
            
            // 【修正】直接從項目欄位取值，不再要求情境欄位
            const item = row['項目'] || row['item'] || row['Item'] || '';
            
            console.log(`第${index+1}行 - 項目: "${item}"`);
            
            // 跳過總計行和空項目
            if (!item || 
                item === '總計' || 
                item.toLowerCase() === 'total' ||
                item.trim() === '') {
                console.log(`跳過第${index+1}行 - 項目為空或總計:${item}`);
                return;
            }
            
            // 只處理包含"模組數"的項目
            if (!item.includes('模組數') && !item.includes('模組')) {
                console.log(`跳過第${index+1}行 - 不是模組統計:${item}`);
                return;
            }
            
            // 【修正】直接從"值"欄位取數字
            const valueField = row['值'] || row['value'] || row['Value'] || row['數量'] || '';
            const numValue = parseInt(valueField) || 0;
            
            console.log(`項目: "${item}", 值欄位: "${valueField}", 轉換後數值: ${numValue}`);
            
            // 根據項目名稱分類統計
            if (item.includes('成功') || item.includes('通過') || item.includes('正確')) {
                totalSuccess += numValue;
                console.log(`識別為成功項目，累加成功數: ${numValue}, 總成功: ${totalSuccess}`);
            } else if (item.includes('失敗') || item.includes('錯誤') || item.includes('異常')) {
                totalFailed += numValue;
                console.log(`識別為失敗項目，累加失敗數: ${numValue}, 總失敗: ${totalFailed}`);
            }
            
            validItemCount++;
            console.log(`第${index+1}行處理完畢，有效項目計數: ${validItemCount}`);
        });
        
        console.log(`最終統計結果:`);
        console.log(`- 有效項目數: ${validItemCount}`);
        console.log(`- 總成功模組: ${totalSuccess}`);
        console.log(`- 總失敗模組: ${totalFailed}`);
        
        // 計算總模組數
        const totalModules = totalSuccess + totalFailed;
        
        // 重置stats陣列，只顯示需要的統計資訊
        stats.length = 0;
        
        // 1. 總模組數（放在最前面）
        stats.push({
            label: '總模組數',
            value: totalModules,
            icon: 'fa-cubes',
            color: 'blue'
        });
        
        // 2. 成功模組
        stats.push({
            label: '成功模組',
            value: totalSuccess,
            icon: 'fa-check-circle',
            color: 'success'
        });
        
        // 3. 失敗模組
        stats.push({
            label: '失敗模組', 
            value: totalFailed,
            icon: 'fa-times-circle',
            color: totalFailed > 0 ? 'danger' : 'blue'
        });
        
        // 4. 成功率
        if (totalModules > 0) {
            const successRate = Math.round((totalSuccess / totalModules) * 100);
            stats.push({
                label: '成功率',
                value: successRate + '%',
                icon: 'fa-percentage',
                color: successRate >= 80 ? 'success' : (successRate >= 60 ? 'warning' : 'danger')
            });
        }
    } else if (currentSheet === 'version_diff' || currentSheet === '版本檔案差異') {
        // version_diff 的統計保持不變
        let differentCount = 0;
        let fileNotFoundCount = 0;
        
        sheetData.data.forEach(row => {
            const baseContent = row.base_content || '';
            const compareContent = row.compare_content || '';
            
            if (baseContent === '(檔案不存在)' || compareContent === '(檔案不存在)') {
                fileNotFoundCount++;
            }
            
            if (baseContent !== compareContent) {
                differentCount++;
            }
        });
        
        stats.push({
            label: '版本不同',
            value: differentCount,
            icon: 'fa-code-branch',
            color: 'warning'
        });
        
        if (fileNotFoundCount > 0) {
            stats.push({
                label: '找不到檔案',
                value: fileNotFoundCount,
                icon: 'fa-file-excel',
                color: 'danger'
            });
        }
    } else if (currentSheet === 'branch_error') {
        const hasWaveN = sheetData.data.filter(row => row.has_wave === 'N').length;
        if (hasWaveN > 0) {
            stats.push({
                label: '需修正',
                value: hasWaveN,
                icon: 'fa-exclamation-triangle',
                color: 'warning'
            });
        }
    } else if (currentSheet === 'lost_project' || currentSheet === '新增/刪除專案') {
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
    } else {
        stats.push({
            label: '欄位數',
            value: sheetData.columns ? sheetData.columns.length : Object.keys(sheetData.data[0] || {}).length,
            icon: 'fa-columns',
            color: 'blue'
        });
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
                <div class="stat-value">${typeof stat.value === 'number' ? stat.value.toLocaleString() : stat.value}</div>
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
            
            // 加入搜尋框和清除按鈕
            filterGroup.innerHTML = `
                <div class="filter-header-row">
                    <label class="filter-label">${col}</label>
                    <button class="clear-filter-btn" data-column="${col}" style="display: none;">
                        <i class="fas fa-times"></i> 清除
                    </button>
                </div>
            `;
            
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
            
            // 綁定清除按鈕事件
            const clearBtn = filterGroup.querySelector('.clear-filter-btn');
            clearBtn.addEventListener('click', function() {
                select.selectedIndex = -1;
                searchInput.value = '';
                searchInput.dispatchEvent(new Event('input'));
                updateClearButton(col);
            });
            
            // 監聽選擇變化
            select.addEventListener('change', function() {
                updateClearButton(col);
            });
            
            // 初始化清除按鈕狀態
            updateClearButton(col);
        }
    });
    
    if (filterContent.children.length === 0) {
        filterContent.innerHTML = '<p class="text-muted text-center">沒有可篩選的欄位</p>';
    }
}

// 更新清除按鈕狀態
function updateClearButton(column) {
    const select = document.querySelector(`select[data-column="${column}"]`);
    const clearBtn = document.querySelector(`.clear-filter-btn[data-column="${column}"]`);
    
    if (select && clearBtn) {
        const hasSelection = select.selectedOptions.length > 0;
        clearBtn.style.display = hasSelection ? 'inline-flex' : 'none';
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
    
    // 更新清除按鈕
    document.querySelectorAll('.clear-filter-btn').forEach(btn => {
        btn.style.display = 'none';
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
        } else if (currentSheet === 'lost_project' || currentSheet === '新增/刪除專案') {
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
    if (trendCanvas) {
        const trendCtx = trendCanvas.getContext('2d');
        
        let chartData = {};
        let chartTitle = '趨勢分析';
        
        // 根據不同資料表類型產生趨勢圖
        if (currentSheet === 'revision_diff') {
            // Revision差異的模組分析
            sheetData.data.forEach(row => {
                const module = row.module;
                if (module) {
                    chartData[module] = (chartData[module] || 0) + 1;
                }
            });
            chartTitle = '模組差異統計';
            
        } else if (currentSheet === 'branch_error') {
            // 分支錯誤分析
            sheetData.data.forEach(row => {
                const hasWave = row.has_wave || 'N';
                const module = row.module || '未知模組';
                const key = `${module} (${hasWave === 'Y' ? '有Wave' : '缺少Wave'})`;
                chartData[key] = (chartData[key] || 0) + 1;
            });
            chartTitle = '分支錯誤分析';
            
        } else if (currentSheet === 'lost_project' || currentSheet === '新增/刪除專案') {
            // 專案變更分析
            sheetData.data.forEach(row => {
                const status = row['狀態'] || '未知';
                chartData[status] = (chartData[status] || 0) + 1;
            });
            chartTitle = '專案變更統計';
            
        } else if (currentSheet === '摘要') {
            // 摘要數據分析
            sheetData.data.forEach(row => {
                const scenario = row['比對情境'] || row['scenario'] || '未知情境';
                if (scenario !== '總計' && scenario.toLowerCase() !== 'total') {
                    const successCount = parseInt(row['成功模組數'] || row['success_count'] || 0);
                    const failedCount = parseInt(row['失敗模組數'] || row['failed_count'] || 0);
                    
                    if (!isNaN(successCount) && successCount > 0) {
                        chartData[scenario + ' (成功)'] = successCount;
                    }
                    if (!isNaN(failedCount) && failedCount > 0) {
                        chartData[scenario + ' (失敗)'] = failedCount;
                    }
                }
            });
            chartTitle = '比對情境統計';
            
        } else {
            // 通用分析：使用第一個字串欄位
            const columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
            const firstStringCol = columns.find(col => {
                const firstValue = sheetData.data[0] && sheetData.data[0][col];
                return typeof firstValue === 'string' && col !== 'path' && !col.includes('content');
            });
            
            if (firstStringCol) {
                sheetData.data.forEach(row => {
                    const value = row[firstStringCol];
                    if (value && typeof value === 'string') {
                        chartData[value] = (chartData[value] || 0) + 1;
                    }
                });
                chartTitle = `${firstStringCol} 分布`;
            }
        }
        
        // 如果有資料，繪製圖表
        if (Object.keys(chartData).length > 0) {
            // 排序並取前10項
            const sortedData = Object.entries(chartData)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10);
            
            window.trendChartInstance = new Chart(trendCtx, {
                type: 'bar',
                data: {
                    labels: sortedData.map(item => item[0]),
                    datasets: [{
                        label: '數量',
                        data: sortedData.map(item => item[1]),
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
                        },
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 0
                            }
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: chartTitle
                        },
                        legend: {
                            display: false
                        }
                    }
                }
            });
        } else {
            // 沒有資料時顯示提示
            trendCtx.font = '16px Arial';
            trendCtx.fillStyle = '#666';
            trendCtx.textAlign = 'center';
            trendCtx.fillText('暫無資料可分析', trendCanvas.width / 2, trendCanvas.height / 2);
        }
    }
}

// 切換篩選器面板
function toggleFilterPanel() {
    document.getElementById('filterPanel').classList.toggle('show');
}

async function exportCurrentView(format) {
    if (!currentData || !currentSheet) {
        showAlertDialog('提示', '請先選擇資料表', 'warning');
        return;
    }
    
    try {
        if (format === 'excel') {
            showExportLoading();
            
            // 取得後端對應的資料表名稱
            const backendSheetName = getCurrentSheetBackendName();
            
            console.log('匯出資訊:', {
                taskId: taskId,
                currentSheet: currentSheet,
                backendSheetName: backendSheetName,
                currentScenario: currentScenario
            });
            
            // 建構API URL - 使用後端期望的路徑格式
            let apiUrl = `/api/export-excel-single/${encodeURIComponent(taskId)}/${encodeURIComponent(backendSheetName)}`;
            
            // 如果有選擇特定情境，加入參數
            if (currentScenario && currentScenario !== 'all') {
                apiUrl += `?scenario=${encodeURIComponent(currentScenario)}`;
            }
            
            console.log(`匯出API URL: ${apiUrl}`);
            
            const response = await fetch(apiUrl, {
                method: 'GET',
                headers: {
                    'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                }
            });
            
            console.log('API回應狀態:', response.status, response.statusText);
            
            if (!response.ok) {
                let errorMessage = '匯出失敗';
                
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                    console.error('API錯誤詳情:', errorData);
                } catch (parseError) {
                    const errorText = await response.text();
                    console.error('API錯誤文字:', errorText);
                    errorMessage = errorText || `HTTP ${response.status}: ${response.statusText}`;
                }
                
                // 根據錯誤類型提供不同的處理方式
                if (response.status === 404) {
                    if (errorMessage.includes('找不到資料表')) {
                        // 資料表名稱不匹配，嘗試其他可能的名稱
                        console.log('嘗試其他可能的資料表名稱...');
                        const alternativeNames = [
                            currentSheet, // 原始名稱
                            getSheetDisplayName(currentSheet), // 顯示名稱
                            getBackendSheetName(getSheetDisplayName(currentSheet)) // 映射名稱
                        ];
                        
                        let success = false;
                        for (const altName of alternativeNames) {
                            if (altName !== backendSheetName) {
                                const altUrl = `/api/export-excel-single/${encodeURIComponent(taskId)}/${encodeURIComponent(altName)}`;
                                console.log(`嘗試替代名稱: ${altName}, URL: ${altUrl}`);
                                
                                try {
                                    const altResponse = await fetch(altUrl, {
                                        method: 'GET',
                                        headers: {
                                            'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                        }
                                    });
                                    
                                    if (altResponse.ok) {
                                        console.log(`替代名稱成功: ${altName}`);
                                        const blob = await altResponse.blob();
                                        downloadBlob(blob, altName);
                                        hideExportLoading();
                                        showToast('Excel 檔案已匯出', 'success');
                                        success = true;
                                        break;
                                    }
                                } catch (altError) {
                                    console.log(`替代名稱失敗: ${altName}`, altError);
                                }
                            }
                        }
                        
                        if (success) return;
                    }
                    
                    // 如果所有伺服器端嘗試都失敗，使用客戶端匯出
                    hideExportLoading();
                    console.log('伺服器端匯出失敗，切換到客戶端匯出');
                    exportToExcelClientSide();
                    return;
                }
                
                throw new Error(errorMessage);
            }
            
            // 檢查回應內容類型
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('spreadsheetml.sheet')) {
                console.warn('警告：回應不是Excel格式，Content-Type:', contentType);
            }
            
            // 獲取檔案blob
            const blob = await response.blob();
            
            if (blob.size === 0) {
                throw new Error('收到空的檔案');
            }
            
            // 下載檔案
            downloadBlob(blob, backendSheetName);
            
            hideExportLoading();
            showToast('Excel 檔案已匯出', 'success');
        }
    } catch (error) {
        console.error('匯出錯誤:', error);
        hideExportLoading();
        
        // 如果是網路錯誤或伺服器錯誤，嘗試客戶端匯出
        if (error.message.includes('fetch') || error.message.includes('NetworkError') || 
            error.message.includes('找不到') || error.message.includes('404')) {
            console.log('切換到客戶端匯出作為備案');
            exportToExcelClientSide();
        } else {
            showAlertDialog('匯出錯誤', `匯出失敗：${error.message}`, 'error');
        }
    }
}

// 輔助函數：下載blob檔案
function downloadBlob(blob, sheetName) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    
    // 生成檔案名稱
    let filename = `${getSheetDisplayName(sheetName)}_${new Date().toISOString().slice(0, 10)}`;
    if (currentScenario && currentScenario !== 'all') {
        filename += `_${currentScenario}`;
    }
    filename += '.xlsx';
    
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// 下載完整報表
function downloadFullReport() {
    const url = `/api/export-excel/${taskId}?scenario=${currentScenario}`;
    window.open(url, '_blank');
}

// 客戶端Excel匯出功能
function exportToExcelClientSide() {
    try {
        console.log('開始客戶端Excel匯出...');
        
        if (!currentData || !currentSheet || !currentData[currentSheet]) {
            showAlertDialog('錯誤', '沒有資料可以匯出', 'error');
            return;
        }
        
        // 檢查是否有 XLSX 庫
        if (typeof XLSX === 'undefined') {
            showAlertDialog('錯誤', 'Excel匯出庫未載入，請重新整理頁面', 'error');
            return;
        }
        
        showExportLoading();
        
        const sheetData = currentData[currentSheet];
        console.log('當前資料表資料:', sheetData);
        
        if (!sheetData.data || sheetData.data.length === 0) {
            hideExportLoading();
            showAlertDialog('提示', '當前資料表沒有資料', 'warning');
            return;
        }
        
        // 獲取欄位和資料
        let columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
        let data = [...sheetData.data]; // 創建副本避免修改原始資料
        
        // 應用目前的篩選和搜尋
        data = applyDataFilters(data);
        if (searchTerm) {
            data = data.filter(row => rowMatchesSearch(row, columns, searchTerm));
        }
        
        console.log(`篩選後資料筆數: ${data.length}`);
        
        // 【只保留版本檔案差異的欄位順序調整】
        if (currentSheet === 'version_diff' || currentSheet === '版本檔案差異') {
            const snIndex = columns.indexOf('SN');
            if (snIndex > -1 && snIndex !== 0) {
                columns.splice(snIndex, 1);
                columns.unshift('SN');
                console.log('版本檔案差異SN移至首位:', columns);
            }
        }
        
        // 建立工作簿
        const workbook = XLSX.utils.book_new();
        
        // 準備資料陣列（表頭 + 資料）
        const worksheetData = [];
        
        // 加入表頭
        worksheetData.push(columns);
        
        // 加入資料行
        data.forEach((row, rowIndex) => {
            const rowData = columns.map(col => {
                let value = row[col];
                
                // 處理 null/undefined
                if (value === null || value === undefined) {
                    return '';
                }
                
                // 處理HTML內容（移除標籤）
                if (typeof value === 'string' && value.includes('<')) {
                    value = value.replace(/<[^>]*>/g, '');
                    value = value.replace(/&nbsp;/g, ' ');
                    value = value.replace(/&amp;/g, '&');
                    value = value.replace(/&lt;/g, '<');
                    value = value.replace(/&gt;/g, '>');
                }
                
                // 處理長文字（截斷過長內容，Excel單元格限制）
                if (typeof value === 'string' && value.length > 32767) {
                    value = value.substring(0, 32764) + '...';
                }
                
                return value;
            });
            worksheetData.push(rowData);
        });
        
        console.log(`工作表資料行數: ${worksheetData.length}`);
        
        // 建立工作表
        const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
        
        // 設定欄寬
        const columnWidths = columns.map((col, index) => {
            if (col === 'SN') return { wch: 8 };
            if (col === 'module') return { wch: 25 };
            if (col === 'location') return { wch: 15 };
            if (col === 'location_path') return { wch: 35 };
            if (col === 'problem') return { wch: 50 };
            if (col === 'has_wave') return { wch: 12 };
            if (col.includes('content')) return { wch: 60 };
            if (col.includes('path')) return { wch: 45 };
            if (col.includes('revision')) return { wch: 20 };
            return { wch: 18 };
        });
        
        worksheet['!cols'] = columnWidths;
        
        // 設定自動篩選
        if (worksheetData.length > 1) {
            const range = XLSX.utils.encode_range({
                s: { c: 0, r: 0 },
                e: { c: columns.length - 1, r: worksheetData.length - 1 }
            });
            worksheet['!autofilter'] = { ref: range };
        }
        
        // 清理工作表名稱
        let sheetName = getSheetDisplayName(currentSheet);
        
        // 進一步清理，確保完全符合Excel規範
        sheetName = cleanExcelSheetName(sheetName);
        
        console.log(`清理後的工作表名稱: "${sheetName}"`);
        
        // 加入工作表到工作簿
        XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);
        
        // 生成檔案名稱（檔案名稱也要清理）
        let filename = cleanFileName(sheetName) + '_' + new Date().toISOString().slice(0, 10);
        if (currentScenario && currentScenario !== 'all') {
            filename += '_' + cleanFileName(currentScenario);
        }
        filename += '.xlsx';
        
        console.log(`匯出檔案名稱: ${filename}`);
        
        // 匯出檔案
        XLSX.writeFile(workbook, filename);
        
        hideExportLoading();
        showToast(`Excel 檔案已匯出（${data.length} 筆資料）`, 'success');
        
    } catch (error) {
        console.error('客戶端匯出錯誤:', error);
        hideExportLoading();
        showAlertDialog('匯出錯誤', `客戶端匯出失敗：${error.message}`, 'error');
    }
}

// 清理Excel工作表名稱（移除特殊字符）
function cleanExcelSheetName(name) {
    if (!name) return 'Sheet1';
    
    // 移除Excel不支援的字符：: \ / ? * [ ]
    let cleanName = String(name).replace(/[\\\/\?\*\[\]:]/g, '_');
    
    // 移除前後空白
    cleanName = cleanName.trim();
    
    // 如果名稱為空，給予預設名稱
    if (!cleanName) {
        cleanName = 'Sheet1';
    }
    
    // 限制長度（Excel工作表名稱最長31個字符）
    if (cleanName.length > 31) {
        cleanName = cleanName.substring(0, 28) + '...';
    }
    
    // 確保名稱不以單引號開始或結束（Excel限制）
    if (cleanName.startsWith("'")) {
        cleanName = cleanName.substring(1);
    }
    if (cleanName.endsWith("'")) {
        cleanName = cleanName.substring(0, cleanName.length - 1);
    }
    
    return cleanName;
}

// 清理檔案名稱
function cleanFileName(name) {
    if (!name) return 'export';
    
    // 移除檔案名稱不支援的字符
    let cleanName = String(name).replace(/[<>:"|?*\\\/]/g, '_');
    
    // 移除前後空白
    cleanName = cleanName.trim();
    
    // 如果名稱為空，給予預設名稱
    if (!cleanName) {
        cleanName = 'export';
    }
    
    return cleanName;
}

// 客戶端匯出所有資料表
function exportAllSheetsClientSide() {
    try {
        console.log('開始客戶端匯出所有資料表...');
        
        if (!currentData || Object.keys(currentData).length === 0) {
            showAlertDialog('錯誤', '沒有資料可以匯出', 'error');
            return;
        }
        
        if (typeof XLSX === 'undefined') {
            showAlertDialog('錯誤', 'Excel匯出庫未載入，請重新整理頁面', 'error');
            return;
        }
        
        showExportLoading();
        
        const workbook = XLSX.utils.book_new();
        let totalSheets = 0;
        const usedSheetNames = new Set(); // 追蹤已使用的工作表名稱
        
        console.log('可用資料表:', Object.keys(currentData));
        
        // 遍歷所有資料表
        Object.keys(currentData).forEach(sheetName => {
            const sheetData = currentData[sheetName];
            console.log(`處理資料表: ${sheetName}`);
            
            if (!sheetData.data || sheetData.data.length === 0) {
                console.log(`跳過空資料表: ${sheetName}`);
                return;
            }
            
            let columns = sheetData.columns || Object.keys(sheetData.data[0] || {});
            
            // 應用欄位順序調整
            if (sheetName === 'branch_error' || sheetName === '分支錯誤') {
                const desiredOrder = ['SN', 'module', 'location', 'location_path', 'problem', 'has_wave'];
                const reorderedColumns = [];
                desiredOrder.forEach(col => {
                    if (columns.includes(col)) reorderedColumns.push(col);
                });
                columns.forEach(col => {
                    if (!desiredOrder.includes(col)) reorderedColumns.push(col);
                });
                columns = reorderedColumns;
            } else if (sheetName === 'version_diff' || sheetName === '版本檔案差異') {
                const snIndex = columns.indexOf('SN');
                if (snIndex > -1 && snIndex !== 0) {
                    columns.splice(snIndex, 1);
                    columns.unshift('SN');
                }
            }
            
            // 準備工作表資料
            const worksheetData = [columns];
            
            sheetData.data.forEach(row => {
                const rowData = columns.map(col => {
                    let value = row[col];
                    if (value === null || value === undefined) return '';
                    if (typeof value === 'string' && value.includes('<')) {
                        value = value.replace(/<[^>]*>/g, '');
                    }
                    if (typeof value === 'string' && value.length > 32767) {
                        value = value.substring(0, 32764) + '...';
                    }
                    return value;
                });
                worksheetData.push(rowData);
            });
            
            // 建立工作表
            const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
            
            // 設定欄寬
            const columnWidths = columns.map(col => {
                if (col === 'SN') return { wch: 8 };
                if (col === 'module') return { wch: 25 };
                if (col.includes('content')) return { wch: 50 };
                if (col.includes('path')) return { wch: 40 };
                return { wch: 15 };
            });
            worksheet['!cols'] = columnWidths;
            
            // 【關鍵修正】清理工作表名稱
            let displayName = getSheetDisplayName(sheetName);
            displayName = cleanExcelSheetName(displayName);
            
            // 確保工作表名稱唯一
            let finalSheetName = displayName;
            let counter = 1;
            while (usedSheetNames.has(finalSheetName)) {
                finalSheetName = `${displayName}_${counter}`;
                if (finalSheetName.length > 31) {
                    finalSheetName = `${displayName.substring(0, 28)}_${counter}`;
                }
                counter++;
            }
            
            usedSheetNames.add(finalSheetName);
            console.log(`最終工作表名稱: "${finalSheetName}"`);
            
            XLSX.utils.book_append_sheet(workbook, worksheet, finalSheetName);
            totalSheets++;
            
            console.log(`已加入工作表: ${finalSheetName} (${sheetData.data.length} 筆資料)`);
        });
        
        if (totalSheets === 0) {
            hideExportLoading();
            showAlertDialog('提示', '沒有有效的資料表可以匯出', 'warning');
            return;
        }
        
        // 匯出完整工作簿
        const filename = cleanFileName(`完整報表_${taskId}`) + '_' + new Date().toISOString().slice(0, 10) + '.xlsx';
        console.log(`匯出完整報表: ${filename}`);
        
        XLSX.writeFile(workbook, filename);
        
        hideExportLoading();
        showToast(`完整報表已匯出（${totalSheets} 個工作表）`, 'success');
        
    } catch (error) {
        console.error('客戶端完整匯出錯誤:', error);
        hideExportLoading();
        showAlertDialog('匯出錯誤', `完整報表匯出失敗：${error.message}`, 'error');
    }
}

// 顯示匯出載入中
function showExportLoading() {
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'exportLoading';
    loadingDiv.innerHTML = `
        <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; 
                    background: rgba(0,0,0,0.5); z-index: 9999; 
                    display: flex; align-items: center; justify-content: center;">
            <div style="background: white; padding: 30px; border-radius: 12px; 
                        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
                        display: flex; flex-direction: column; align-items: center;">
                <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: #2196F3; margin: 0 auto;"></i>
                <p style="margin-top: 15px; color: #333; text-align: center;">正在準備檔案...</p>
            </div>
        </div>
    `;
    document.body.appendChild(loadingDiv);
}

// 隱藏匯出載入中
function hideExportLoading() {
    const loadingDiv = document.getElementById('exportLoading');
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

// 匯出整個頁面為 HTML（保留 JS/CSS）- 完整離線版本
// 修復版 exportPageAsHTML 函數 - 替換你現有的
function exportPageAsHTML() {
    try {
        // 收集所有內嵌的 CSS
        let allCSS = '';
        
        // 收集所有樣式表
        const styleSheets = document.styleSheets;
        for (let i = 0; i < styleSheets.length; i++) {
            try {
                const rules = styleSheets[i].cssRules || styleSheets[i].rules;
                if (rules) {
                    for (let j = 0; j < rules.length; j++) {
                        allCSS += rules[j].cssText + '\n';
                    }
                }
            } catch (e) {
                // 跨域樣式表，使用 @import
                if (styleSheets[i].href) {
                    allCSS += `@import url("${styleSheets[i].href}");\n`;
                }
            }
        }
        
        // 獲取當前所有的必要 JavaScript 函數
        const jsCode = getRequiredOfflineFunctions();
        
        // 建立完整的離線 HTML
        const htmlContent = `
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>比對結果報表 - ${taskId} (離線完整版)</title>
    
    <!-- 外部資源 CDN -->
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    
    <!-- jQuery 和 jQuery UI (必須在 PivotTable 之前載入) -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jqueryui/1.12.1/jquery-ui.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/jqueryui/1.12.1/themes/base/jquery-ui.min.css">
    
    <!-- PivotTable.js -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/pivottable/2.23.0/pivot.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pivottable/2.23.0/pivot.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pivottable/2.23.0/pivot.zh.js"></script>
    
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <!-- SheetJS (XLSX) -->
    <script src="https://cdn.sheetjs.com/xlsx-latest/package/dist/xlsx.full.min.js"></script>
    
    <!-- 內嵌樣式 -->
    <style>
        ${allCSS}
        
        /* 離線模式樣式 */
        .offline-mode-notice {
            position: fixed;
            top: 10px;
            right: 10px;
            background: #FF9800;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 0.875rem;
            z-index: 1000;
            display: none;
        }
        
        @media print {
            .offline-mode-notice,
            .fab-container,
            .filter-panel {
                display: none !important;
            }
        }
    </style>
</head>
<body>
    <!-- 離線模式提示 -->
    <div class="offline-mode-notice" id="offlineModeNotice">
        <i class="fas fa-info-circle"></i> 離線模式
    </div>

    <!-- 主容器 -->
    <div class="container">
        <div class="page-header">
            <h1 class="page-title">
                <i class="fas fa-chart-line"></i> 比對結果報表
            </h1>
            <p class="page-subtitle">任務 ID: ${taskId}</p>
            <p class="page-subtitle">匯出時間: ${new Date().toLocaleString('zh-TW')}</p>
        </div>

        <!-- 步驟 1：資料統計 -->
        <div class="step-section">
            <div class="step-header">
                <div class="step-number">1</div>
                <div class="step-content">
                    <h2 class="step-title">資料統計</h2>
                    <p class="step-subtitle">查看資料的統計摘要</p>
                </div>
            </div>
            
            <div class="section-body">
                <div class="stats-grid" id="statsGrid"></div>
            </div>
        </div>

        <!-- 步驟 2：資料檢視 -->
        <div class="step-section">
            <div class="step-header">
                <div class="step-number">2</div>
                <div class="step-content">
                    <h2 class="step-title">資料檢視</h2>
                    <p class="step-subtitle">選擇資料表並查看詳細的比對結果</p>
                </div>
            </div>
            
            <div class="section-body">
                <!-- 資料表選擇與工具列 -->
                <div class="data-controls">
                    <div class="control-left">
                        <label class="form-label">
                            <i class="fas fa-table"></i> 資料表
                        </label>
                        <select class="form-input" id="sheetSelector"></select>
                        
                        <!-- 快速搜尋 -->
                        <div class="search-box">
                            <i class="fas fa-search"></i>
                            <input type="text" 
                                   class="search-input" 
                                   id="quickSearchInput" 
                                   placeholder="快速搜尋..." 
                                   autocomplete="off">
                            <span class="search-count" id="searchCount"></span>
                        </div>
                    </div>
                    
                    <div class="control-right">
                        <button class="btn-icon" onclick="togglePivotMode()" title="切換樞紐分析">
                            <i class="fas fa-chart-pie" id="pivotIcon"></i>
                        </button>
                        <button class="btn-icon" onclick="toggleFilterPanel()" title="篩選資料">
                            <i class="fas fa-filter"></i>
                        </button>
                    </div>
                </div>

                <div class="data-view-container">
                    <!-- 一般表格檢視 -->
                    <div id="tableView" class="table-view">
                        <div class="table-header-container">
                            <table class="data-table header-only">
                                <thead id="tableHead"></thead>
                            </table>
                        </div>
                        <div class="table-body-container">
                            <table class="data-table body-only">
                                <tbody id="tableBody"></tbody>
                            </table>
                        </div>
                    </div>
                    
                    <!-- 樞紐分析檢視 -->
                    <div id="pivotView" class="pivot-view hidden">
                        <div class="step-section">
                            <div class="step-header pivot-header">
                                <div class="step-number">3</div>
                                <div class="step-content">
                                    <h2 class="step-title">樞紐分析表</h2>
                                    <p class="step-subtitle">拖曳欄位來建立自訂的分析報表</p>
                                </div>
                            </div>
                            
                            <div class="section-body">
                                <div class="pivot-controls">
                                    <div class="pivot-controls-left"></div>
                                    <div class="pivot-controls-right">
                                        <button class="btn btn-outline btn-sm" onclick="togglePivotAreas()">
                                            <i class="fas fa-eye-slash" id="toggleAreasIcon"></i> 
                                            <span id="toggleAreasText">隱藏拖曳區</span>
                                        </button>
                                        <button class="btn btn-outline btn-sm" onclick="togglePivotFullscreen()">
                                            <i class="fas fa-expand" id="fullscreenIcon"></i> 
                                            <span id="fullscreenText">全螢幕</span>
                                        </button>
                                        <button class="btn btn-outline btn-sm" onclick="resetPivotTable()">
                                            <i class="fas fa-undo"></i> 重置
                                        </button>
                                    </div>
                                </div>
                                
                                <div id="pivotContainer"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 步驟 3：圖表分析 -->
        <div class="step-section">
            <div class="step-header">
                <div class="step-number">3</div>
                <div class="step-content">
                    <h2 class="step-title">圖表分析</h2>
                    <p class="step-subtitle">視覺化資料分析結果</p>
                </div>
            </div>
            
            <div class="section-body">
                <div class="charts-section">
                    <div class="chart-container">
                        <h3 class="chart-title">資料分布圖</h3>
                        <canvas id="distributionChart"></canvas>
                    </div>
                    <div class="chart-container">
                        <h3 class="chart-title">趨勢分析圖</h3>
                        <canvas id="trendChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 篩選器面板 -->
    <div class="filter-panel" id="filterPanel">
        <div class="filter-header">
            <h3>資料篩選器</h3>
            <button class="btn-icon" onclick="toggleFilterPanel()">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="filter-content" id="filterContent"></div>
        <div class="filter-actions">
            <button class="btn btn-primary" onclick="applyFilters()">套用篩選</button>
            <button class="btn btn-outline" onclick="clearFilters()">清除篩選</button>
        </div>
    </div>

    <!-- JavaScript 程式碼 -->
    <script>
        // 設定離線模式標記
        window.isOfflineMode = true;
        
        // 顯示離線模式提示
        setTimeout(() => {
            const notice = document.getElementById('offlineModeNotice');
            if (notice) {
                notice.style.display = 'block';
                setTimeout(() => {
                    notice.style.display = 'none';
                }, 5000);
            }
        }, 1000);
        
        // 內嵌資料
        const exportedData = ${JSON.stringify(currentData)};
        const exportedTaskId = '${taskId}';
        const exportedSheet = '${currentSheet}';
        
        // 內嵌所有函數
        ${jsCode}
        
        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            console.log('離線模式初始化開始...');
            
            // 設定全域變數
            currentData = exportedData;
            taskId = exportedTaskId;
            currentSheet = exportedSheet;
            
            // 初始化應用
            initializeOfflineApp();
        });
        
        // 離線模式初始化函數
        function initializeOfflineApp() {
            try {
                // 填充資料表選項
                const selector = document.getElementById('sheetSelector');
                if (selector && exportedData) {
                    selector.innerHTML = '';
                    
                    // 定義資料表順序
                    const sheetOrder = [
                        'revision_diff', 'branch_error', 'lost_project', 
                        'version_diff', '無法比對', '摘要'
                    ];
                    
                    const orderedSheets = [];
                    
                    // 按順序添加
                    sheetOrder.forEach(sheetName => {
                        if (exportedData[sheetName]) {
                            orderedSheets.push(sheetName);
                        }
                    });
                    
                    // 添加其他資料表
                    Object.keys(exportedData).forEach(sheetName => {
                        if (!orderedSheets.includes(sheetName)) {
                            orderedSheets.push(sheetName);
                        }
                    });
                    
                    // 生成選項
                    orderedSheets.forEach(sheetName => {
                        const option = document.createElement('option');
                        option.value = sheetName;
                        option.textContent = getSheetDisplayName(sheetName);
                        selector.appendChild(option);
                    });
                    
                    // 綁定事件
                    selector.addEventListener('change', function(e) {
                        if (e.target.value) {
                            currentSheet = e.target.value;
                            loadSheet(e.target.value);
                        }
                    });
                }
                
                // 初始化搜尋
                initializeSearch();
                
                // 載入初始資料
                if (exportedSheet && exportedData[exportedSheet]) {
                    loadSheet(exportedSheet);
                } else if (orderedSheets && orderedSheets.length > 0) {
                    loadSheet(orderedSheets[0]);
                }
                
                console.log('離線模式初始化完成');
                
            } catch (error) {
                console.error('離線模式初始化錯誤:', error);
                alert('初始化失敗: ' + error.message);
            }
        }
        
        // 覆寫某些需要網路的功能
        window.exportCurrentView = function(format) {
            alert('離線模式下無法使用此功能');
        };
        
        window.downloadFullReport = function() {
            alert('離線模式下無法下載完整報表');
        };
    </script>
</body>
</html>
        `;
        
        // 下載檔案
        const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report_${taskId}_offline_${new Date().toISOString().slice(0, 10)}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('HTML 檔案已匯出（包含完整離線功能）', 'success');
        
    } catch (error) {
        console.error('匯出 HTML 錯誤:', error);
        alert('匯出失敗：' + error.message);
    }
}

// 完整版 getRequiredOfflineFunctions 函數 - 替換你現有的
function getRequiredOfflineFunctions() {
    let code = `
        // 全域變數
        let currentData = null;
        let currentSheet = null;
        let pivotMode = false;
        let filters = {};
        let sortOrder = {};
        let searchTerm = '';
        let taskId = '';
        let pivotData = null;
        let pivotConfig = null;
        let pivotInitialData = null;
        let pivotInitialConfig = null;
        let areasVisible = true;
        let customFilterCurrentElement = null;
        let customFilterCurrentData = [];
        let pivotFilterStates = {};
        let currentFilterField = null;
        
        // 確保 jQuery 和 PivotTable 已載入
        if (typeof $ === 'undefined') {
            console.error('jQuery 未正確載入');
        }
        if (typeof $.pivotUtilities === 'undefined') {
            console.warn('PivotTable.js 未正確載入，樞紐分析功能可能不可用');
        }
                
        // ===== 自定義篩選器完整函數系統 =====

        function showCustomFilterModal(fieldName = '篩選選項') {
            // 確保彈出視窗存在
            if ($('#customFilterModal').length === 0) {
                createCustomFilterModal();
            }
            
            // 更新選項列表
            const optionsHTML = customFilterCurrentData.map((item) => \`
                <div class="filter-option" style="padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
                    <label style="display: flex; align-items: center; cursor: pointer;">
                        <input type="checkbox" value="\${item.value}" \${item.checked ? 'checked' : ''} 
                            style="margin-right: 10px; transform: scale(1.2);">
                        <span style="font-size: 14px; color: #333;">\${item.value}</span>
                    </label>
                </div>
            \`).join('');
            
            $('#customFilterOptions').html(optionsHTML);
            
            // 使用傳入的欄位名稱更新標題
            $('#customFilterTitle').text(\`\${fieldName}\`);
            
            $('#customFilterSearch').val('');
            $('#customFilterModal').css('display', 'flex');
            
            console.log(\`顯示 \${fieldName} 的篩選器，共 \${customFilterCurrentData.length} 個選項\`);
        }

        function createCustomFilterModal() {
            const modalHTML = \`
                <div id="customFilterModal" style="
                    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                    background: rgba(0, 0, 0, 0.7); z-index: 2147483647; display: none;
                    align-items: center; justify-content: center; font-family: Arial, sans-serif;
                ">
                    <div style="
                        background: white; border-radius: 12px; padding: 25px;
                        max-width: 500px; max-height: 80vh; overflow-y: auto;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin: 20px;
                        z-index: 2147483648; position: relative;
                    ">
                        <div style="
                            display: flex; justify-content: space-between; align-items: center;
                            margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #2196F3;
                        ">
                            <h3 id="customFilterTitle" style="margin: 0; color: #333; font-size: 20px;">篩選選項</h3>
                            <button id="customFilterClose" style="
                                background: #ff4444; color: white; border: none; border-radius: 50%;
                                width: 30px; height: 30px; cursor: pointer; font-size: 18px; font-weight: bold;
                            ">×</button>
                        </div>
                        
                        <div style="margin-bottom: 15px;">
                            <input type="text" id="customFilterSearch" placeholder="搜尋選項..." style="
                                width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 6px;
                                font-size: 14px; box-sizing: border-box;
                            ">
                        </div>
                        
                        <div id="customFilterOptions" style="
                            max-height: 300px; overflow-y: auto; border: 1px solid #eee;
                            border-radius: 6px; padding: 10px;
                        "></div>
                        
                        <div style="
                            display: flex; gap: 10px; margin-top: 20px; justify-content: flex-end;
                        ">
                            <button id="customFilterSelectAll" style="
                                background: #4CAF50; color: white; border: none; padding: 10px 15px;
                                border-radius: 6px; cursor: pointer; font-size: 14px;
                            ">全選</button>
                            <button id="customFilterClearAll" style="
                                background: #FF9800; color: white; border: none; padding: 10px 15px;
                                border-radius: 6px; cursor: pointer; font-size: 14px;
                            ">清除</button>
                            <button id="customFilterCancel" style="
                                background: #666; color: white; border: none; padding: 10px 15px;
                                border-radius: 6px; cursor: pointer; font-size: 14px;
                            ">取消</button>
                            <button id="customFilterApply" style="
                                background: #2196F3; color: white; border: none; padding: 10px 20px;
                                border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold;
                            ">確定</button>
                        </div>
                    </div>
                </div>
            \`;
            
            $('body').append(modalHTML);
            bindCustomFilterEvents();
        }

        function bindCustomFilterEvents() {
            // 關閉事件
            $('#customFilterClose, #customFilterCancel').click(function() {
                $('#customFilterModal').hide();
            });
            
            // 點擊遮罩關閉
            $('#customFilterModal').click(function(e) {
                if (e.target === this) {
                    $(this).hide();
                }
            });
            
            // 搜尋功能
            $('#customFilterSearch').on('input', function() {
                const searchTerm = $(this).val().toLowerCase();
                $('#customFilterOptions .filter-option').each(function() {
                    const text = $(this).find('span').text().toLowerCase();
                    $(this).toggle(text.includes(searchTerm));
                });
            });
            
            // 全選/清除
            $('#customFilterSelectAll').click(function() {
                $('#customFilterOptions input[type="checkbox"]:visible').prop('checked', true);
            });
            
            $('#customFilterClearAll').click(function() {
                $('#customFilterOptions input[type="checkbox"]:visible').prop('checked', false);
            });
            
            // 確定按鈕
            $('#customFilterApply').click(function() {
                applyCustomFilter();
            });
        }

        function applyCustomFilter() {
            if (!customFilterCurrentElement || !currentFilterField) {
                $('#customFilterModal').hide();
                return;
            }
            
            const fieldName = currentFilterField;
            console.log(\`套用 \${fieldName} 的篩選\`);
            
            // 建立狀態映射
            const desiredStates = new Map();
            const selectedValues = [];
            
            $('#customFilterOptions input[type="checkbox"]').each(function() {
                const value = $(this).val().trim();
                const checked = $(this).prop('checked');
                desiredStates.set(value, checked);
                
                if (checked) {
                    selectedValues.push(value);
                }
            });
            
            // 保存到全域篩選狀態
            if (!window.pivotFilterStates) {
                window.pivotFilterStates = {};
            }
            
            window.pivotFilterStates[fieldName] = {
                selectedValues: selectedValues,
                allValues: Array.from(desiredStates.keys()),
                timestamp: Date.now()
            };
            
            console.log(\`\${fieldName} 狀態已保存:\`, window.pivotFilterStates[fieldName]);
            console.log('套用篩選狀態:', Array.from(desiredStates.entries()));
            
            // 顯示原始篩選框
            const $filterBox = customFilterCurrentElement;
            $filterBox.show();
            
            // 同步狀態
            let updateCount = 0;
            $filterBox.find('input[type="checkbox"]').each(function() {
                const $cb = $(this);
                const $label = $cb.closest('label');
                const labelText = $label.text().trim();
                
                if (labelText && labelText !== 'Select All' && labelText !== '全選') {
                    if (desiredStates.has(labelText)) {
                        const targetState = desiredStates.get(labelText);
                        const currentState = $cb.prop('checked');
                        
                        if (currentState !== targetState) {
                            console.log(\`更新 \${labelText}: \${currentState} -> \${targetState}\`);
                            $cb[0].checked = targetState;
                            $cb.prop('checked', targetState);
                            $cb.trigger('change');
                            updateCount++;
                        }
                    }
                }
            });
            
            console.log(\`\${fieldName} 更新了 \${updateCount} 個選項\`);
            
            // 觸發更新
            setTimeout(() => {
                // 尋找 Apply 按鈕
                const $applyBtn = $filterBox.find('button').filter(function() {
                    const text = $(this).text().toLowerCase();
                    return text.includes('apply') || text.includes('ok');
                });
                
                if ($applyBtn.length > 0) {
                    console.log(\`\${fieldName} 點擊 Apply 按鈕\`);
                    $applyBtn.first().click();
                } else {
                    console.log(\`\${fieldName} 使用備用更新方法\`);
                    // 備用方法：觸發第一個 checkbox 的 change 事件
                    $filterBox.find('input[type="checkbox"]').first().trigger('change');
                }
                
                setTimeout(() => {
                    $filterBox.hide();
                    console.log(\`\${fieldName} 篩選套用完成\`);
                }, 100);
            }, 100);
            
            $('#customFilterModal').hide();
        }

        function closePivotFilterModal() {
            const modal = document.getElementById('pivotFilterModal');
            if (modal) {
                modal.classList.remove('show');
            }
            
            // 也關閉自定義篩選器
            $('#customFilterModal').hide();
            
            // 清空搜尋
            const searchInput = document.getElementById('pivotFilterSearch');
            if (searchInput) {
                searchInput.value = '';
            }
            
            // 清理當前參考（但保留狀態）
            currentPivotDropdown = null;
            currentFilterField = null;
            
            console.log('篩選彈出視窗已關閉');
        }

        // ===== 樞紐分析篩選器輔助函數 =====

        function filterPivotItems(searchTerm) {
            const items = document.querySelectorAll('.pivot-filter-item');
            const lowerSearchTerm = searchTerm.toLowerCase();
            
            items.forEach(item => {
                const label = item.querySelector('span').textContent.toLowerCase();
                item.style.display = label.includes(lowerSearchTerm) ? '' : 'none';
            });
        }

        function selectAllPivotFilters() {
            const checkboxes = document.querySelectorAll('#pivotFilterList input[type="checkbox"]');
            checkboxes.forEach(cb => {
                if (cb.parentElement.parentElement.style.display !== 'none') {
                    cb.checked = true;
                }
            });
        }

        function clearAllPivotFilters() {
            const checkboxes = document.querySelectorAll('#pivotFilterList input[type="checkbox"]');
            checkboxes.forEach(cb => {
                if (cb.parentElement.style.display !== 'none') {
                    cb.checked = false;
                }
            });
        }

        function applyPivotFilters() {
            console.log('applyPivotFilters 被調用（離線模式）');
            $('#pivotFilterModal').hide();
        }

        function escapeHtml(text) {
            if (typeof text !== 'string') {
                text = String(text);
            }
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
                    
        // ===== 添加所有缺失的函數定義 =====
        
        function updateClearButton(column) {
            const select = document.querySelector(\`select[data-column="\${column}"]\`);
            const clearBtn = document.querySelector(\`.clear-filter-btn[data-column="\${column}"]\`);
            
            if (select && clearBtn) {
                const hasSelection = select.selectedOptions.length > 0;
                clearBtn.style.display = hasSelection ? 'inline-flex' : 'none';
            }
        }
        
        function initializePivotFilterModal() {
            // 如果彈出視窗已存在，直接返回
            if (document.getElementById('pivotFilterModal')) {
                return;
            }
            
            // 創建彈出視窗 HTML
            const modalHtml = \`
                <div id="pivotFilterModal" class="pivot-filter-modal">
                    <div class="pivot-filter-content">
                        <div class="pivot-filter-header">
                            <h3 class="pivot-filter-title">篩選項目</h3>
                            <button class="pivot-filter-close" onclick="closePivotFilterModal()">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        <div class="pivot-filter-search">
                            <input type="text" id="pivotFilterSearch" placeholder="搜尋...">
                        </div>
                        <div class="pivot-filter-list" id="pivotFilterList">
                            <!-- 動態生成的篩選項目 -->
                        </div>
                        <div class="pivot-filter-footer">
                            <button class="pivot-filter-btn pivot-filter-btn-secondary" onclick="selectAllPivotFilters()">
                                全選
                            </button>
                            <button class="pivot-filter-btn pivot-filter-btn-secondary" onclick="clearAllPivotFilters()">
                                清除
                            </button>
                            <button class="pivot-filter-btn pivot-filter-btn-primary" onclick="applyPivotFilters()">
                                確定
                            </button>
                        </div>
                    </div>
                </div>
            \`;
            
            // 添加到頁面
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            // 點擊遮罩層關閉
            document.getElementById('pivotFilterModal').addEventListener('click', function(e) {
                if (e.target === this) {
                    closePivotFilterModal();
                }
            });
            
            // 搜尋功能
            document.getElementById('pivotFilterSearch').addEventListener('input', function(e) {
                filterPivotItems(e.target.value);
            });
        }
        
        function interceptPivotDropdowns() {
            console.log('設定篩選器攔截（離線模式）...');
            
            setTimeout(() => {
                // 清除舊事件
                $('.pvtTriangle').off('click.customFilter');
                
                // 為每個 Triangle 單獨綁定事件
                $('.pvtTriangle').each(function(triangleIndex) {
                    const $triangle = $(this);
                    const $container = $triangle.parent();
                    
                    $triangle.on('click.customFilter', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        console.log(\`Triangle \${triangleIndex} 被點擊\`);
                        
                        // 尋找對應的篩選框
                        let $specificFilterBox = $container.find('.pvtFilterBox').first();
                        
                        if ($specificFilterBox.length === 0) {
                            $specificFilterBox = $container.parent().find('.pvtFilterBox').eq(triangleIndex);
                        }
                        
                        if ($specificFilterBox.length === 0) {
                            const $allFilterBoxes = $('.pvtFilterBox');
                            if ($allFilterBoxes.length > triangleIndex) {
                                $specificFilterBox = $allFilterBoxes.eq(triangleIndex);
                            }
                        }
                        
                        if ($specificFilterBox && $specificFilterBox.length > 0 && $specificFilterBox.find('input[type="checkbox"]').length > 0) {
                            console.log(\`Triangle \${triangleIndex} 對應篩選框找到\`);
                            
                            let fieldName = \`欄位_\${triangleIndex}\`;
                            
                            // 方法1：嘗試從DOM結構獲取真實欄位名稱
                            const $parentContainer = $triangle.closest('.pvtAxisContainer, .pvtVals, .pvtRows, .pvtCols');
                            const $fieldLabel = $parentContainer.find('.pvtAttr, .pvtVal').eq(triangleIndex);
                            
                            if ($fieldLabel.length > 0) {
                                const actualFieldName = $fieldLabel.text().trim();
                                if (actualFieldName && actualFieldName !== '') {
                                    fieldName = actualFieldName;
                                    console.log(\`從DOM獲取到真實欄位名稱: \${fieldName}\`);
                                }
                            }
                            
                            // 方法2：如果方法1失敗，從篩選框附近的元素獲取
                            if (fieldName.startsWith('欄位_')) {
                                const $nearbyElements = $triangle.parent().find('*').addBack();
                                $nearbyElements.each(function() {
                                    const text = $(this).text().trim();
                                    // 跳過明顯的控制文字和數據值
                                    if (text && 
                                        text.length < 30 && 
                                        !text.includes('Select') && 
                                        !text.includes('全選') &&
                                        !text.match(/^\\\d+$/) && 
                                        !text.match(/^\\\d+\\\(\\\d+\\\)$/) &&
                                        !text.includes('(') &&
                                        text !== fieldName) {
                                        
                                        fieldName = text;
                                        console.log(\`從附近元素獲取到欄位名稱: \${fieldName}\`);
                                        return false; // 跳出 each 循環
                                    }
                                });
                            }
                            
                            // 方法3：作為最後手段，從篩選內容智能推斷
                            if (fieldName.startsWith('欄位_')) {
                                const firstCheckbox = $specificFilterBox.find('input[type="checkbox"]').first();
                                if (firstCheckbox.length > 0) {
                                    // 收集前幾個選項來做更智能的判斷
                                    const sampleLabels = [];
                                    $specificFilterBox.find('input[type="checkbox"]').slice(0, 5).each(function() {
                                        const label = $(this).closest('label').text().trim();
                                        if (label && label !== 'Select All' && label !== '全選') {
                                            sampleLabels.push(label);
                                        }
                                    });
                                    
                                    console.log(\`樣本標籤:\`, sampleLabels);
                                    
                                    // 根據樣本標籤的特徵來判斷欄位類型
                                    const allLabels = sampleLabels.join(' ');
                                    
                                    if (allLabels.includes('Master') || allLabels.includes('PreMP') || allLabels.includes('Wave')) {
                                        fieldName = '比對情境';
                                    } else if (sampleLabels.every(label => label.match(/^[a-zA-Z_]+[\\/\\\\]/))) {
                                        fieldName = '模組路徑';
                                    } else if (sampleLabels.every(label => label.match(/^\\\d+\\\(\\\d+\\\)$/))) {
                                        fieldName = 'Revision差異';
                                    } else if (sampleLabels.every(label => label === 'Y' || label === 'N')) {
                                        fieldName = '布林欄位';
                                    } else if (sampleLabels.every(label => label.includes('/'))) {
                                        fieldName = '路徑欄位';
                                    } else if (sampleLabels.some(label => label.includes('新增') || label.includes('刪除') || label.includes('修改'))) {
                                        fieldName = '狀態';
                                    } else {
                                        // 使用第一個較短的、看起來像欄位值的標籤
                                        const representativeLabel = sampleLabels.find(label => 
                                            label.length < 20 && 
                                            !label.includes('/') && 
                                            !label.match(/^\\\d+$/)
                                        ) || sampleLabels[0];
                                        
                                        if (representativeLabel) {
                                            if (representativeLabel.length <= 15) {
                                                fieldName = representativeLabel;
                                            } else {
                                                fieldName = representativeLabel.substring(0, 12) + '...';
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // 最終備案：使用索引
                            if (fieldName.startsWith('欄位_') || !fieldName) {
                                fieldName = \`欄位 \${triangleIndex + 1}\`;
                            }
                            
                            customFilterCurrentElement = $specificFilterBox;
                            currentFilterField = fieldName;
                            customFilterCurrentData = [];
                            
                            $specificFilterBox.find('input[type="checkbox"]').each(function() {
                                const $cb = $(this);
                                const $label = $cb.closest('label');
                                const labelText = $label.text().trim();
                                
                                if (labelText && labelText !== 'Select All' && labelText !== '全選') {
                                    customFilterCurrentData.push({
                                        value: labelText,
                                        checked: $cb.prop('checked')
                                    });
                                }
                            });
                            
                            console.log(\`\${fieldName} 的選項:\`, customFilterCurrentData);
                            showCustomFilterModal(fieldName);
                        } else {
                            console.log(\`Triangle \${triangleIndex} 找不到對應的篩選框\`);
                            alert('找不到篩選選項');
                        }
                        
                        return false;
                    });
                });
                
                console.log(\`已為 \${$('.pvtTriangle').length} 個 Triangle 設定攔截器\`);
                
            }, 500);
        }
        
        function formatMultiLineContent(value, compareValue, fileType) {
            if (!value) return value;
            if (!compareValue) return value;
            
            const lines = value.split('\\n');
            const compareLines = compareValue.split('\\n');
            
            const compareMap = {};
            compareLines.forEach(line => {
                if (line.startsWith('P_GIT_')) {
                    const gitId = line.split(';')[0];
                    compareMap[gitId] = line;
                } else if (line.includes(':')) {
                    const key = line.split(':')[0].trim();
                    compareMap[key] = line;
                } else {
                    compareMap[line.substring(0, 20)] = line;
                }
            });
            
            let formattedLines = [];
            
            lines.forEach((line) => {
                let formattedLine = line;
                
                if (line.startsWith('P_GIT_')) {
                    const gitId = line.split(';')[0];
                    const compareLine = compareMap[gitId] || '';
                    
                    if (compareLine) {
                        const parts1 = line.split(';');
                        const parts2 = compareLine.split(';');
                        
                        if (parts1.length >= 5 && parts2.length >= 5) {
                            let result = '';
                            for (let i = 0; i < parts1.length; i++) {
                                if (i > 0) result += ';';
                                
                                if ((i === 3 || i === 4) && parts1[i] !== parts2[i]) {
                                    result += \`<span class="highlight-red" style="color: #dc3545 !important; font-weight: 600 !important;">\${parts1[i]}</span>\`;
                                } else {
                                    result += parts1[i];
                                }
                            }
                            formattedLine = result;
                        }
                    }
                } else if (line.includes(':')) {
                    const key = line.split(':')[0].trim();
                    const compareLine = compareMap[key] || '';
                    
                    if (compareLine) {
                        const val1 = line.split(':')[1]?.trim() || '';
                        const val2 = compareLine.split(':')[1]?.trim() || '';
                        
                        if (val1 !== val2) {
                            formattedLine = \`\${key}: <span class="highlight-red" style="color: #dc3545 !important; font-weight: 600 !important;">\${val1}</span>\`;
                        }
                    }
                }
                
                formattedLines.push(formattedLine);
            });
            
            return formattedLines.join('<br>');
        }
        
        function formatFHashContent(value1, value2) {
            if (!value1 || !value2) return value1;
            
            const notFoundPattern = /F_HASH:\\s*\\(not found\\)/i;
            const hashPattern = /F_HASH:\\s*([a-f0-9]+)/i;
            
            const hasNotFound1 = notFoundPattern.test(value1);
            const hasNotFound2 = notFoundPattern.test(value2);
            
            if (hasNotFound1 || hasNotFound2) {
                if (hasNotFound1 && !hasNotFound2) {
                    return value1.replace('(not found)', '<span class="highlight-red" style="color: #dc3545 !important;">(not found)</span>');
                } else if (!hasNotFound1 && hasNotFound2) {
                    const match1 = value1.match(hashPattern);
                    if (match1) {
                        return value1.replace(match1[1], \`<span class="highlight-red" style="color: #dc3545 !important;">\${match1[1]}</span>\`);
                    }
                }
                return value1;
            }
            
            const match1 = value1.match(hashPattern);
            const match2 = value2.match(hashPattern);
            
            if (match1 && match2) {
                const hash1 = match1[1];
                const hash2 = match2[1];
                
                if (hash1 !== hash2) {
                    return value1.replace(hash1, \`<span class="highlight-red" style="color: #dc3545 !important;">\${hash1}</span>\`);
                }
            }
            
            return value1;
        }
        
        function formatColonContent(value1, value2) {
            if (!value1 || !value2) return value1;
            
            if (value1.startsWith('P_GIT_')) {
                return formatMultiLineContent(value1, value2);
            }
            
            const colonIndex1 = value1.indexOf(':');
            const colonIndex2 = value2.indexOf(':');
            
            if (colonIndex1 === -1 || colonIndex2 === -1) {
                return value1;
            }
            
            const key1 = value1.substring(0, colonIndex1).trim();
            const key2 = value2.substring(0, colonIndex2).trim();
            
            if (key1 !== key2) {
                return value1;
            }
            
            const val1 = value1.substring(colonIndex1 + 1).trim();
            const val2 = value2.substring(colonIndex2 + 1).trim();
            
            if (val1 !== val2) {
                return \`\${key1}: <span class="highlight-red" style="color: #dc3545 !important; font-weight: 600 !important;">\${val1}</span>\`;
            }
            
            return value1;
        }
        
        function enableTableFeatures() {
            console.log('表格功能已啟用（離線模式）');
        }
        
        function resetPivotTable() {
            if (!pivotData) {
                alert('沒有資料可重置');
                return;
            }
            
            try {
                const container = document.getElementById('pivotContainer');
                if (container && typeof $ !== 'undefined' && $.pivotUtilities) {
                    $(container).empty();
                    $(container).pivotUI(pivotData, {
                        rows: [],
                        cols: [],
                        vals: [],
                        aggregatorName: "Count",
                        rendererName: "Table"
                    });
                }
            } catch (error) {
                console.error('重置失敗:', error);
            }
        }
        
        function exportPivotTable() {
            alert('離線模式下無法匯出樞紐分析表');
        }
        
        function showConfirmDialog(title, message, onConfirm, onCancel) {
            if (confirm(message)) {
                if (onConfirm) onConfirm();
            } else {
                if (onCancel) onCancel();
            }
        }
        
        function showAlertDialog(title, message, type) {
            alert(message);
        }
        
        function showCenteredToast(message, type) {
            showToast(message, type);
        }
        
    `;
    
    // 只包含確實存在的函數
    const existingFunctions = [
        'getSheetDisplayName',
        'loadSheet', 
        'renderDataTable',
        'renderPivotTable',
        'updateStatistics',
        'updateTableStats',
        'generateFilters',
        'applyFilters',
        'clearFilters',
        'applyDataFilters',
        'togglePivotMode',
        'toggleFilterPanel',
        'initializeSearch',
        'highlightText',
        'rowMatchesSearch',
        'sortTable',
        'getColumnWidth',
        'debounce',
        'drawDataCharts',
        'showToast',
        'togglePivotFullscreen',
        'togglePivotAreas',
        'adjustPivotContainerSize'
    ];
    
    // 添加現有函數的定義
    existingFunctions.forEach(funcName => {
        if (window[funcName] && typeof window[funcName] === 'function') {
            try {
                code += window[funcName].toString() + '\n\n';
            } catch (error) {
                console.warn(`無法序列化函數: \${funcName}`, error);
            }
        }
    });
    
    // 最後添加所有函數的 window 綁定
    code += `
        // 綁定所有函數到 window 物件
        window.getSheetDisplayName = getSheetDisplayName;
        window.loadSheet = loadSheet;
        window.renderDataTable = renderDataTable;
        window.renderPivotTable = renderPivotTable;
        window.updateStatistics = updateStatistics;
        window.updateTableStats = updateTableStats;
        window.generateFilters = generateFilters;
        window.applyFilters = applyFilters;
        window.clearFilters = clearFilters;
        window.applyDataFilters = applyDataFilters;
        window.togglePivotMode = togglePivotMode;
        window.toggleFilterPanel = toggleFilterPanel;
        window.initializeSearch = initializeSearch;
        window.highlightText = highlightText;
        window.rowMatchesSearch = rowMatchesSearch;
        window.sortTable = sortTable;
        window.getColumnWidth = getColumnWidth;
        window.debounce = debounce;
        window.drawDataCharts = drawDataCharts;
        window.showToast = showToast;
        window.togglePivotFullscreen = togglePivotFullscreen;
        window.togglePivotAreas = togglePivotAreas;
        window.adjustPivotContainerSize = adjustPivotContainerSize;
        window.updateClearButton = updateClearButton;
        window.formatMultiLineContent = formatMultiLineContent;
        window.formatFHashContent = formatFHashContent;
        window.formatColonContent = formatColonContent;
        window.enableTableFeatures = enableTableFeatures;
        window.initializePivotFilterModal = initializePivotFilterModal;
        window.interceptPivotDropdowns = interceptPivotDropdowns;
        window.resetPivotTable = resetPivotTable;
        window.exportPivotTable = exportPivotTable;
        window.showConfirmDialog = showConfirmDialog;
        window.showAlertDialog = showAlertDialog;
        window.showCenteredToast = showCenteredToast;
        window.showCustomFilterModal = showCustomFilterModal;
        window.createCustomFilterModal = createCustomFilterModal;
        window.bindCustomFilterEvents = bindCustomFilterEvents;
        window.applyCustomFilter = applyCustomFilter;
        window.closePivotFilterModal = closePivotFilterModal;
        window.filterPivotItems = filterPivotItems;
        window.selectAllPivotFilters = selectAllPivotFilters;
        window.clearAllPivotFilters = clearAllPivotFilters;
        window.applyPivotFilters = applyPivotFilters;
        window.escapeHtml = escapeHtml;        
        console.log('所有函數已載入並綁定到 window');
    `;
    
    return code;
}

function getAllRequiredFunctions() {
    // 收集所有必要的函數定義
    const functions = [
        'getSheetDisplayName',
        'loadSheet',
        'renderDataTable',
        'renderPivotTable',
        'updateStatistics',
        'updateTableStats',
        'generateFilters',
        'applyFilters',
        'clearFilters',
        'applyDataFilters',
        'togglePivotMode',
        'toggleFilterPanel',
        'initializeSearch',
        'highlightText',
        'rowMatchesSearch',
        'formatFVersionContent',
        'formatFHashContent',
        'formatColonContent',
        'sortTable',
        'getColumnWidth',
        'debounce',
        'enableTableFeatures',
        'drawDataCharts',
        'updateClearButton',
        'resetPivotTable',
        'exportPivotTable',
        'exportPivotToExcel',
        'exportPivotToCSV',
        'exportPivotToHTML',
        'showToast',
        'showConfirmDialog',
        'showAlertDialog',
        'togglePivotFullscreen',
        'togglePivotAreas'
    ];
    
    let code = `
        // 全域變數
        let currentData = null;
        let currentSheet = null;
        let pivotMode = false;
        let filters = {};
        let sortOrder = {};
        let searchTerm = '';
        let taskId = '';
        let pivotData = null;
        let pivotConfig = null;
        let pivotInitialData = null;
        let pivotInitialConfig = null;
        let areasVisible = true;
        
        // 確保 jQuery 和 PivotTable 已載入
        if (typeof $ === 'undefined' || typeof $.pivotUtilities === 'undefined') {
            console.error('jQuery 或 PivotTable.js 未正確載入');
        }
        
    `;
    
    // 添加每個函數的定義
    functions.forEach(funcName => {
        if (window[funcName]) {
            code += window[funcName].toString() + '\n\n';
        }
    });
    
    // 在最後添加綁定到 window 的程式碼
    code += `
        // 綁定所有函數到 window 物件，讓 onclick 事件能找到
        window.getSheetDisplayName = getSheetDisplayName;
        window.loadSheet = loadSheet;
        window.renderDataTable = renderDataTable;
        window.renderPivotTable = renderPivotTable;
        window.updateStatistics = updateStatistics;
        window.updateTableStats = updateTableStats;
        window.generateFilters = generateFilters;
        window.applyFilters = applyFilters;
        window.clearFilters = clearFilters;
        window.applyDataFilters = applyDataFilters;
        window.togglePivotMode = togglePivotMode;
        window.toggleFilterPanel = toggleFilterPanel;
        window.initializeSearch = initializeSearch;
        window.highlightText = highlightText;
        window.rowMatchesSearch = rowMatchesSearch;
        window.formatFVersionContent = formatFVersionContent;
        window.formatFHashContent = formatFHashContent;
        window.formatColonContent = formatColonContent;
        window.sortTable = sortTable;
        window.getColumnWidth = getColumnWidth;
        window.debounce = debounce;
        window.enableTableFeatures = enableTableFeatures;
        window.drawDataCharts = drawDataCharts;
        window.updateClearButton = updateClearButton;
        window.resetPivotTable = resetPivotTable;
        window.exportPivotTable = exportPivotTable;
        window.exportPivotToExcel = exportPivotToExcel;
        window.exportPivotToCSV = exportPivotToCSV;
        window.exportPivotToHTML = exportPivotToHTML;
        window.showToast = showToast;
        window.showConfirmDialog = showConfirmDialog;
        window.showAlertDialog = showAlertDialog;
        window.togglePivotFullscreen = togglePivotFullscreen;
        window.togglePivotAreas = togglePivotAreas;
        
        // 確保初始化完成
        console.log('所有函數已載入並綁定到 window');
    `;
    
    return code;
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

// 修正 formatFVersionContent 函數 - 確保索引正確
function formatFVersionContent(value1, value2) {
    if (!value1 || !value1.startsWith('P_GIT_')) return value1;
    if (!value2 || !value2.startsWith('P_GIT_')) return value1;
    
    const parts1 = value1.split(';');
    const parts2 = value2.split(';');
    
    // P_GIT_001;realtek/bootcode;realtek/mac9q/master;72bbd9b;0007093
    // 索引: 0=P_GIT_001, 1=repo, 2=branch, 3=hash, 4=revision
    
    if (parts1.length < 5 || parts2.length < 5) return value1;
    
    let result = '';
    for (let i = 0; i < parts1.length; i++) {
        if (i > 0) result += ';';
        
        // 檢查 hash (索引3) 或 revision (索引4) 是否不同
        if (i === 3 || i === 4) {
            if (parts2[i] && parts1[i] !== parts2[i]) {
                // 使用內聯樣式和 class 確保紅色顯示
                result += `<span class="highlight-red" style="color: #dc3545 !important; font-weight: 600 !important;">${parts1[i]}</span>`;
            } else {
                result += parts1[i];
            }
        } else {
            result += parts1[i];
        }
    }
    
    return result;
}

// 格式化 F_HASH 內容 - 只標記不同的 hash 值
function formatFHashContent(value1, value2) {
    if (!value1 || !value2) return value1;
    
    // 處理 F_HASH: (not found) 的情況
    const notFoundPattern = /F_HASH:\s*\(not found\)/i;
    const hashPattern = /F_HASH:\s*([a-f0-9]+)/i;
    
    const hasNotFound1 = notFoundPattern.test(value1);
    const hasNotFound2 = notFoundPattern.test(value2);
    
    if (hasNotFound1 || hasNotFound2) {
        if (hasNotFound1 && !hasNotFound2) {
            return value1.replace('(not found)', '<span class="highlight-red" style="color: #dc3545 !important;">(not found)</span>');
        } else if (!hasNotFound1 && hasNotFound2) {
            const match1 = value1.match(hashPattern);
            if (match1) {
                return value1.replace(match1[1], `<span class="highlight-red" style="color: #dc3545 !important;">${match1[1]}</span>`);
            }
        }
        return value1;
    }
    
    // 正常的 hash 比較
    const match1 = value1.match(hashPattern);
    const match2 = value2.match(hashPattern);
    
    if (match1 && match2) {
        const hash1 = match1[1];
        const hash2 = match2[1];
        
        if (hash1 !== hash2) {
            return value1.replace(hash1, `<span class="highlight-red" style="color: #dc3545 !important;">${hash1}</span>`);
        }
    }
    
    return value1;
}

// 格式化包含冒號的內容 - 只標記不同的值
function formatColonContent(value1, value2) {
    if (!value1 || !value2) return value1;
    
    // 特別處理 P_GIT_ 格式
    if (value1.startsWith('P_GIT_')) {
        return formatFVersionContent(value1, value2);
    }
    
    const colonIndex1 = value1.indexOf(':');
    const colonIndex2 = value2.indexOf(':');
    
    if (colonIndex1 === -1 || colonIndex2 === -1) {
        return value1;
    }
    
    const key1 = value1.substring(0, colonIndex1).trim();
    const key2 = value2.substring(0, colonIndex2).trim();
    
    if (key1 !== key2) {
        return value1;
    }
    
    const val1 = value1.substring(colonIndex1 + 1).trim();
    const val2 = value2.substring(colonIndex2 + 1).trim();
    
    if (val1 !== val2) {
        // 使用內聯樣式確保紅色顯示
        return `${key1}: <span class="highlight-red" style="color: #dc3545 !important; font-weight: 600 !important;">${val1}</span>`;
    }
    
    return value1;
}

// 自定義確認對話框
function showConfirmDialog(title, message, onConfirm, onCancel) {
    // 創建對話框元素
    const dialogHtml = `
        <div class="custom-dialog-overlay">
            <div class="custom-dialog">
                <div class="dialog-header">
                    <i class="fas fa-question-circle"></i>
                    <h3>${title}</h3>
                </div>
                <div class="dialog-body">
                    <p>${message}</p>
                </div>
                <div class="dialog-footer">
                    <button class="btn btn-outline btn-sm" id="dialogCancel">
                        <i class="fas fa-times"></i> 取消
                    </button>
                    <button class="btn btn-primary btn-sm" id="dialogConfirm">
                        <i class="fas fa-check"></i> 確定
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // 添加到頁面 - 檢查是否在全螢幕模式
    const dialogElement = document.createElement('div');
    dialogElement.innerHTML = dialogHtml;
    
    // 如果在全螢幕模式，附加到全螢幕元素內
    const fullscreenElement = document.fullscreenElement;
    if (fullscreenElement) {
        fullscreenElement.appendChild(dialogElement);
    } else {
        document.body.appendChild(dialogElement);
    }
    
    // 添加動畫類
    setTimeout(() => {
        dialogElement.querySelector('.custom-dialog-overlay').classList.add('show');
        dialogElement.querySelector('.custom-dialog').classList.add('show');
    }, 10);
    
    // 綁定事件
    const confirmBtn = document.getElementById('dialogConfirm');
    const cancelBtn = document.getElementById('dialogCancel');
    const overlay = dialogElement.querySelector('.custom-dialog-overlay');
    
    const closeDialog = () => {
        overlay.classList.remove('show');
        dialogElement.querySelector('.custom-dialog').classList.remove('show');
        setTimeout(() => {
            if (fullscreenElement && dialogElement.parentNode === fullscreenElement) {
                fullscreenElement.removeChild(dialogElement);
            } else {
                document.body.removeChild(dialogElement);
            }
        }, 300);
    };
    
    confirmBtn.addEventListener('click', () => {
        closeDialog();
        if (onConfirm) onConfirm();
    });
    
    cancelBtn.addEventListener('click', () => {
        closeDialog();
        if (onCancel) onCancel();
    });
    
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeDialog();
            if (onCancel) onCancel();
        }
    });
}

// 自定義提示對話框（替代 alert）
function showAlertDialog(title, message, type = 'info') {
    const iconMap = {
        'info': 'fa-info-circle',
        'warning': 'fa-exclamation-triangle',
        'error': 'fa-times-circle',
        'success': 'fa-check-circle'
    };
    
    const colorMap = {
        'info': '#2196F3',
        'warning': '#FF9800',
        'error': '#F44336',
        'success': '#4CAF50'
    };
    
    const dialogHtml = `
        <div class="custom-dialog-overlay">
            <div class="custom-dialog alert-dialog">
                <div class="dialog-header" style="color: ${colorMap[type]}">
                    <i class="fas ${iconMap[type]}"></i>
                    <h3>${title}</h3>
                </div>
                <div class="dialog-body">
                    <p>${message}</p>
                </div>
                <div class="dialog-footer">
                    <button class="btn btn-primary btn-sm" id="dialogOk">
                        <i class="fas fa-check"></i> 確定
                    </button>
                </div>
            </div>
        </div>
    `;
    
    const dialogElement = document.createElement('div');
    dialogElement.innerHTML = dialogHtml;
    
    // 檢查是否在全螢幕模式
    const fullscreenElement = document.fullscreenElement;
    if (fullscreenElement) {
        fullscreenElement.appendChild(dialogElement);
    } else {
        document.body.appendChild(dialogElement);
    }
    
    setTimeout(() => {
        dialogElement.querySelector('.custom-dialog-overlay').classList.add('show');
        dialogElement.querySelector('.custom-dialog').classList.add('show');
    }, 10);
    
    const okBtn = document.getElementById('dialogOk');
    const overlay = dialogElement.querySelector('.custom-dialog-overlay');
    
    const closeDialog = () => {
        overlay.classList.remove('show');
        dialogElement.querySelector('.custom-dialog').classList.remove('show');
        setTimeout(() => {
            if (fullscreenElement && dialogElement.parentNode === fullscreenElement) {
                fullscreenElement.removeChild(dialogElement);
            } else {
                document.body.removeChild(dialogElement);
            }
        }, 300);
    };
    
    okBtn.addEventListener('click', closeDialog);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeDialog();
    });
}

// 全螢幕功能
function togglePivotFullscreen() {
    const pivotView = document.getElementById('pivotView');
    const icon = document.getElementById('fullscreenIcon');
    const text = document.getElementById('fullscreenText');
    
    // 檢查元素是否存在
    if (!pivotView || !icon || !text) {
        console.error('找不到必要的元素');
        return;
    }
    
    if (!document.fullscreenElement) {
        // 進入全螢幕
        pivotView.requestFullscreen().then(() => {
            pivotView.classList.add('fullscreen');
            icon.classList.remove('fa-expand');
            icon.classList.add('fa-compress');
            text.textContent = '退出全螢幕';
            
            // 全螢幕後重新調整樞紐分析表大小
            setTimeout(() => {
                try {
                    // 觸發 window resize 事件
                    window.dispatchEvent(new Event('resize'));
                    
                    // 調用統一的大小調整函數
                    adjustPivotContainerSize();
                    
                } catch (error) {
                    console.error('調整全螢幕大小時發生錯誤:', error);
                }
            }, 200);
            
        }).catch(err => {
            console.error('無法進入全螢幕:', err);
            if (typeof showAlertDialog === 'function') {
                showAlertDialog('錯誤', '無法進入全螢幕模式', 'error');
            } else {
                alert('無法進入全螢幕模式');
            }
        });
    } else {
        // 退出全螢幕
        document.exitFullscreen().then(() => {
            pivotView.classList.remove('fullscreen');
            icon.classList.remove('fa-compress');
            icon.classList.add('fa-expand');
            text.textContent = '全螢幕';
            
            // 退出全螢幕後調整大小
            setTimeout(() => {
                adjustPivotContainerSize();
            }, 200);
            
        }).catch(err => {
            console.error('退出全螢幕時發生錯誤:', err);
        });
    }
}

// 監聽全螢幕變化事件（用戶按 ESC 退出時）
document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement) {
        const pivotView = document.getElementById('pivotView');
        const icon = document.getElementById('fullscreenIcon');
        const text = document.getElementById('fullscreenText');
        
        pivotView.classList.remove('fullscreen');
        icon.classList.remove('fa-compress');
        icon.classList.add('fa-expand');
        text.textContent = '全螢幕';
    }
});

// 切換拖曳區域顯示/隱藏
let areasVisible = true;
function togglePivotAreas() {
    const icon = document.getElementById('toggleAreasIcon');
    const text = document.getElementById('toggleAreasText');
    const pivotContainer = document.getElementById('pivotContainer');
    
    areasVisible = !areasVisible;
    
    if (areasVisible) {
        // 顯示拖曳區域和控制區
        $('.pvtUnused, .pvtRows, .pvtCols, .pvtVals').show();
        $('.pvtRenderer, .pvtAggregator, .pvtAttrDropdown').parent().show();
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
        text.textContent = '隱藏拖曳區';
        pivotContainer.classList.remove('areas-hidden');
        
        // 恢復原始樣式
        if (document.fullscreenElement) {
            setTimeout(() => {
                adjustPivotContainerSize();
            }, 150);
        }
        
    } else {
        // 隱藏拖曳區域和控制區
        $('.pvtUnused, .pvtRows, .pvtCols, .pvtVals').hide();
        $('.pvtRenderer, .pvtAggregator, .pvtAttrDropdown').parent().hide();
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
        text.textContent = '顯示拖曳區';
        pivotContainer.classList.add('areas-hidden');
        
        // 隱藏拖曳區後立即調整佈局
        setTimeout(() => {
            adjustPivotContainerSize();
            
            // 【額外修復】強制重新佈局樞紐分析表
            if (document.fullscreenElement) {
                const pvtUi = pivotContainer.querySelector('.pvtUi');
                const pvtRendererArea = pivotContainer.querySelector('.pvtRendererArea');
                const pvtTable = pivotContainer.querySelector('.pvtTable');
                
                if (pvtUi) {
                    pvtUi.style.width = '100vw';
                    pvtUi.style.maxWidth = '100vw';
                    pvtUi.style.margin = '0';
                    pvtUi.style.padding = '0';
                }
                
                if (pvtRendererArea) {
                    pvtRendererArea.style.width = '100%';
                    pvtRendererArea.style.maxWidth = '100%';
                }
                
                if (pvtTable) {
                    pvtTable.style.width = '100%';
                    pvtTable.style.maxWidth = '100%';
                    pvtTable.style.minWidth = '100%';
                    
                    // 強制重新渲染表格
                    const originalDisplay = pvtTable.style.display;
                    pvtTable.style.display = 'none';
                    setTimeout(() => {
                        pvtTable.style.display = originalDisplay || '';
                        
                        // 再次確保所有單元格正確佈局
                        const cells = pvtTable.querySelectorAll('td, th');
                        cells.forEach(cell => {
                            cell.style.maxWidth = 'none';
                            cell.style.whiteSpace = 'nowrap';
                        });
                    }, 20);
                }
                
                // 觸發視窗 resize 事件
                setTimeout(() => {
                    window.dispatchEvent(new Event('resize'));
                }, 200);
            }
            
        }, 150);
    }
    
    console.log(`拖曳區域 ${areasVisible ? '顯示' : '隱藏'}，全屏模式: ${!!document.fullscreenElement}`);
}

// 增強版 adjustPivotContainerSize 函數 - 替換你現有的
function adjustPivotContainerSize() {
    const pivotContainer = document.getElementById('pivotContainer');
    const pivotView = document.getElementById('pivotView');
    
    if (!pivotContainer || !pivotView) return;
    
    try {
        if (document.fullscreenElement) {
            // 全屏模式下的調整
            const stepHeader = pivotView.querySelector('.step-header');
            const pivotControls = pivotView.querySelector('.pivot-controls');
            const instructions = pivotView.querySelector('.pivot-instructions');
            
            // 計算已使用的高度
            let usedHeight = 0;
            
            if (stepHeader) {
                usedHeight += stepHeader.offsetHeight || 0;
            }
            
            if (pivotControls) {
                usedHeight += pivotControls.offsetHeight || 0;
            }
            
            if (instructions && window.getComputedStyle(instructions).display !== 'none') {
                usedHeight += instructions.offsetHeight || 0;
            }
            
            // 如果隱藏了拖曳區，需要額外考慮節省的空間
            let savedSpace = 0;
            if (!areasVisible) {
                // 估算隱藏拖曳區節省的空間
                const hiddenElements = $('.pvtUnused, .pvtRows, .pvtCols, .pvtVals');
                hiddenElements.each(function() {
                    savedSpace += $(this).outerHeight(true) || 0;
                });
                
                // 額外添加一些空間補償
                savedSpace += 50;
            }
            
            // 計算可用高度
            const availableHeight = Math.max(
                window.innerHeight - usedHeight + savedSpace - 40, // 40px 緩衝
                400 // 最小高度
            );
            
            // 設定容器高度和寬度
            pivotContainer.style.height = `${availableHeight}px`;
            pivotContainer.style.maxHeight = `${availableHeight}px`;
            
            // 【關鍵修復】強制設定橫向填滿
            if (!areasVisible) {
                // 隱藏拖曳區時，強制使用全螢幕寬度
                pivotContainer.style.width = '100vw';
                pivotContainer.style.maxWidth = '100vw';
                pivotContainer.style.margin = '0';
                pivotContainer.style.padding = '0';
                pivotContainer.style.boxSizing = 'border-box';
                
                // 【加強】立即設定父容器寬度
                const sectionBody = pivotContainer.closest('.section-body');
                if (sectionBody) {
                    sectionBody.style.width = '100vw';
                    sectionBody.style.maxWidth = '100vw';
                    sectionBody.style.margin = '0';
                    sectionBody.style.padding = '0';
                }
                
                // 強制設定樞紐分析表的寬度
                setTimeout(() => {
                    const pvtUi = pivotContainer.querySelector('.pvtUi');
                    if (pvtUi) {
                        pvtUi.style.width = '100vw !important';
                        pvtUi.style.maxWidth = '100vw !important';
                        pvtUi.style.minWidth = '100vw !important';
                        pvtUi.style.margin = '0';
                        pvtUi.style.padding = '0';
                    }
                    
                    const pvtRendererArea = pivotContainer.querySelector('.pvtRendererArea');
                    if (pvtRendererArea) {
                        pvtRendererArea.style.width = '100vw';
                        pvtRendererArea.style.maxWidth = '100vw';
                        pvtRendererArea.style.minWidth = '100vw';
                        pvtRendererArea.style.overflowX = 'auto';
                        pvtRendererArea.style.overflowY = 'auto';
                        pvtRendererArea.style.maxHeight = `${availableHeight - 50}px`;
                    }
                    
                    const pvtTable = pivotContainer.querySelector('.pvtTable');
                    if (pvtTable) {
                        pvtTable.style.width = '100%';
                        pvtTable.style.maxWidth = 'none';
                        pvtTable.style.minWidth = '100%';
                        pvtTable.style.tableLayout = 'auto';
                        
                        // 【新增】強制表格使用所有可用寬度
                        pvtTable.style.display = 'table';
                        pvtTable.style.borderCollapse = 'collapse';
                    }
                    
                    // 【加強】確保表格單元格使用完整寬度
                    const allCells = pivotContainer.querySelectorAll('.pvtTable td, .pvtTable th');
                    const totalCells = allCells.length;
                    if (totalCells > 0) {
                        // 計算每個單元格的基礎寬度
                        const cellWidth = Math.max(100, Math.floor(window.innerWidth / 10));
                        
                        allCells.forEach((cell, index) => {
                            cell.style.minWidth = cellWidth + 'px';
                            cell.style.maxWidth = 'none';
                            cell.style.whiteSpace = 'nowrap';
                            cell.style.overflow = 'hidden';
                            cell.style.textOverflow = 'ellipsis';
                            cell.style.padding = '12px 20px';
                        });
                    }
                    
                    // 【新增】觸發表格重新渲染
                    if (pvtTable) {
                        const originalDisplay = pvtTable.style.display;
                        pvtTable.style.display = 'none';
                        setTimeout(() => {
                            pvtTable.style.display = originalDisplay || 'table';
                        }, 50);
                    }
                    
                }, 100);
            } else {
                // 【修復】顯示拖曳區時，恢復正常寬度
                pivotContainer.style.width = '';
                pivotContainer.style.maxWidth = '';
                
                const sectionBody = pivotContainer.closest('.section-body');
                if (sectionBody) {
                    sectionBody.style.width = '';
                    sectionBody.style.maxWidth = '';
                    sectionBody.style.margin = '';
                    sectionBody.style.padding = '';
                }
            }
            
            console.log(`調整樞紐容器大小: 使用高度=${usedHeight}, 節省空間=${savedSpace}, 可用高度=${availableHeight}, 隱藏拖曳區=${!areasVisible}`);
            
        } else {
            // 非全屏模式下的調整
            if (!areasVisible) {
                // 隱藏拖曳區時，給樞紐表更多空間
                pivotContainer.style.height = '700px';
                pivotContainer.style.maxHeight = '700px';
                pivotContainer.style.width = '100%';
                pivotContainer.style.maxWidth = '100%';
            } else {
                // 顯示拖曳區時，恢復正常高度
                pivotContainer.style.height = '600px';
                pivotContainer.style.maxHeight = '600px';
                pivotContainer.style.width = '';
                pivotContainer.style.maxWidth = '';
            }
        }
        
        // 觸發重新佈局
        setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
            
            // 【額外修復】強制重新渲染樞紐分析表
            if (!areasVisible && document.fullscreenElement) {
                const pvtTable = pivotContainer.querySelector('.pvtTable');
                if (pvtTable) {
                    // 觸發表格重新計算
                    pvtTable.style.display = 'none';
                    setTimeout(() => {
                        pvtTable.style.display = '';
                    }, 10);
                }
            }
        }, 100);
        
    } catch (error) {
        console.error('調整樞紐容器大小時發生錯誤:', error);
    }
}

// 顯示情境載入中
function showScenarioLoading() {
    const scenarioTabs = document.querySelectorAll('.scenario-tab');
    scenarioTabs.forEach(tab => {
        tab.disabled = true;
        tab.style.opacity = '0.6';
    });
}

// 隱藏情境載入中
function hideScenarioLoading() {
    const scenarioTabs = document.querySelectorAll('.scenario-tab');
    scenarioTabs.forEach(tab => {
        tab.disabled = false;
        tab.style.opacity = '1';
    });
}

// 修正樞紐分析表下拉選單位置
function fixPivotDropdownPosition() {
    // 使用 MutationObserver 監控 DOM 變化
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                // 檢查是否有新的下拉選單出現
                $('.pvtFilterBox:visible').each(function() {
                    const $filterBox = $(this);
                    const $dropdown = $filterBox.closest('.pvtDropdown');
                    
                    if ($dropdown.length) {
                        // 獲取下拉按鈕的位置
                        const dropdownOffset = $dropdown.offset();
                        const dropdownHeight = $dropdown.outerHeight();
                        const dropdownWidth = $dropdown.outerWidth();
                        
                        // 計算視窗邊界
                        const windowHeight = $(window).height();
                        const windowWidth = $(window).width();
                        const scrollTop = $(window).scrollTop();
                        
                        // 設定篩選框的位置
                        let top = dropdownOffset.top - scrollTop + dropdownHeight + 5;
                        let left = dropdownOffset.left;
                        
                        // 檢查是否超出下方邊界
                        const filterBoxHeight = $filterBox.outerHeight();
                        if (top + filterBoxHeight > windowHeight) {
                            // 顯示在上方
                            top = dropdownOffset.top - scrollTop - filterBoxHeight - 5;
                        }
                        
                        // 檢查是否超出右邊界
                        const filterBoxWidth = $filterBox.outerWidth();
                        if (left + filterBoxWidth > windowWidth) {
                            left = windowWidth - filterBoxWidth - 10;
                        }
                        
                        $filterBox.css({
                            position: 'fixed',
                            top: top + 'px',
                            left: left + 'px',
                            'z-index': 999999,
                            'max-height': '300px',
                            'overflow-y': 'auto'
                        });
                    }
                });
            }
        });
    });
    
    // 開始觀察
    const config = { childList: true, subtree: true };
    const targetNode = document.getElementById('pivotContainer');
    if (targetNode) {
        observer.observe(targetNode, config);
    }
    
    // 點擊其他地方關閉下拉選單
    $(document).on('click', function(e) {
        if (!$(e.target).closest('.pvtDropdown').length) {
            $('.pvtFilterBox').hide();
        }
    });
}

// 初始化樞紐分析表篩選器彈出視窗
function initializePivotFilterModal() {
    // 如果彈出視窗已存在，直接返回
    if (document.getElementById('pivotFilterModal')) {
        return;
    }
    
    // 創建彈出視窗 HTML
    const modalHtml = `
        <div id="pivotFilterModal" class="pivot-filter-modal">
            <div class="pivot-filter-content">
                <div class="pivot-filter-header">
                    <h3 class="pivot-filter-title">篩選項目</h3>
                    <button class="pivot-filter-close" onclick="closePivotFilterModal()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="pivot-filter-search">
                    <input type="text" id="pivotFilterSearch" placeholder="搜尋...">
                </div>
                <div class="pivot-filter-list" id="pivotFilterList">
                    <!-- 動態生成的篩選項目 -->
                </div>
                <div class="pivot-filter-footer">
                    <button class="pivot-filter-btn pivot-filter-btn-secondary" onclick="selectAllPivotFilters()">
                        全選
                    </button>
                    <button class="pivot-filter-btn pivot-filter-btn-secondary" onclick="clearAllPivotFilters()">
                        清除
                    </button>
                    <button class="pivot-filter-btn pivot-filter-btn-primary" onclick="applyPivotFilters()">
                        確定
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // 添加到頁面
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // 點擊遮罩層關閉
    document.getElementById('pivotFilterModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closePivotFilterModal();
        }
    });
    
    // 搜尋功能
    document.getElementById('pivotFilterSearch').addEventListener('input', function(e) {
        filterPivotItems(e.target.value);
    });
}

// 改進的攔截函數，確保記錄正確的篩選框參考
// 替換你的 interceptPivotDropdowns 函數（修復版）
function interceptPivotDropdowns() {
    console.log('設定篩選器攔截（修復版）...');
    
    setTimeout(() => {
        // 清除舊事件
        $('.pvtTriangle').off('click.customFilter');
        
        // 為每個 Triangle 單獨綁定事件
        $('.pvtTriangle').each(function(triangleIndex) {
            const $triangle = $(this);
            const $container = $triangle.parent(); // 獲取父容器
            
            $triangle.on('click.customFilter', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                console.log(`Triangle ${triangleIndex} 被點擊`);
                
                // 尋找這個 Triangle 對應的特定篩選框
                let $specificFilterBox = null;
                
                // 方法1: 在同一容器中尋找
                $specificFilterBox = $container.find('.pvtFilterBox').first();
                
                // 方法2: 如果方法1找不到，在父容器中尋找
                if ($specificFilterBox.length === 0) {
                    $specificFilterBox = $container.parent().find('.pvtFilterBox').eq(triangleIndex);
                }
                
                // 方法3: 如果還是找不到，按索引匹配
                if ($specificFilterBox.length === 0) {
                    const $allFilterBoxes = $('.pvtFilterBox');
                    if ($allFilterBoxes.length > triangleIndex) {
                        $specificFilterBox = $allFilterBoxes.eq(triangleIndex);
                    }
                }
                
                // 方法4: 最後備案，找第一個有內容的篩選框
                if ($specificFilterBox.length === 0 || $specificFilterBox.find('input[type="checkbox"]').length === 0) {
                    $('.pvtFilterBox').each(function(index) {
                        const $box = $(this);
                        if ($box.find('input[type="checkbox"]').length > 0) {
                            console.log(`使用備案篩選框 ${index}`);
                            $specificFilterBox = $box;
                            return false;
                        }
                    });
                }
                
                if ($specificFilterBox && $specificFilterBox.length > 0 && $specificFilterBox.find('input[type="checkbox"]').length > 0) {
                    console.log(`Triangle ${triangleIndex} 對應篩選框找到，checkbox 數量: ${$specificFilterBox.find('input[type="checkbox"]').length}`);
                    
                    let fieldName = `欄位_${triangleIndex}`;

                    // 方法1：嘗試從DOM結構獲取真實欄位名稱
                    const $parentContainer = $triangle.closest('.pvtAxisContainer, .pvtVals, .pvtRows, .pvtCols');
                    const $fieldLabel = $parentContainer.find('.pvtAttr, .pvtVal').eq(triangleIndex);

                    if ($fieldLabel.length > 0) {
                        const actualFieldName = $fieldLabel.text().trim();
                        if (actualFieldName && actualFieldName !== '') {
                            fieldName = actualFieldName;
                            console.log(`從DOM獲取到真實欄位名稱: ${fieldName}`);
                        }
                    }

                    // 方法2：如果方法1失敗，從篩選框附近的元素獲取
                    if (fieldName.startsWith('欄位_')) {
                        const $nearbyElements = $triangle.parent().find('*').addBack();
                        $nearbyElements.each(function() {
                            const text = $(this).text().trim();
                            // 跳過明顯的控制文字和數據值
                            if (text && 
                                text.length < 30 && 
                                !text.includes('Select') && 
                                !text.includes('全選') &&
                                !text.match(/^\d+$/) && 
                                !text.match(/^\d+\(\d+\)$/) &&
                                !text.includes('(') &&
                                text !== fieldName) {
                                
                                fieldName = text;
                                console.log(`從附近元素獲取到欄位名稱: ${fieldName}`);
                                return false; // 跳出 each 循環
                            }
                        });
                    }

                    // 方法3：作為最後手段，從篩選內容智能推斷
                    if (fieldName.startsWith('欄位_')) {
                        const firstCheckbox = $specificFilterBox.find('input[type="checkbox"]').first();
                        if (firstCheckbox.length > 0) {
                            const firstLabel = firstCheckbox.closest('label').text().trim();
                            if (firstLabel && firstLabel !== 'Select All' && firstLabel !== '全選') {
                                
                                // 收集前幾個選項來做更智能的判斷
                                const sampleLabels = [];
                                $specificFilterBox.find('input[type="checkbox"]').slice(0, 5).each(function() {
                                    const label = $(this).closest('label').text().trim();
                                    if (label && label !== 'Select All' && label !== '全選') {
                                        sampleLabels.push(label);
                                    }
                                });
                                
                                console.log(`樣本標籤:`, sampleLabels);
                                
                                // 根據樣本標籤的特徵來判斷欄位類型
                                const allLabels = sampleLabels.join(' ');
                                
                                if (allLabels.includes('Master') || allLabels.includes('PreMP') || allLabels.includes('Wave')) {
                                    fieldName = '比對情境';
                                } else if (sampleLabels.every(label => label.match(/^[a-zA-Z_]+[\/\\]/))) {
                                    fieldName = '模組路徑';
                                } else if (sampleLabels.every(label => label.match(/^\d+\(\d+\)$/))) {
                                    fieldName = 'Revision差異';
                                } else if (sampleLabels.every(label => label === 'Y' || label === 'N')) {
                                    fieldName = '布林欄位';
                                } else if (sampleLabels.every(label => label.includes('/'))) {
                                    fieldName = '路徑欄位';
                                } else if (sampleLabels.some(label => label.includes('新增') || label.includes('刪除') || label.includes('修改'))) {
                                    fieldName = '狀態';
                                } else {
                                    // 使用第一個較短的、看起來像欄位值的標籤
                                    const representativeLabel = sampleLabels.find(label => 
                                        label.length < 20 && 
                                        !label.includes('/') && 
                                        !label.match(/^\d+$/)
                                    ) || sampleLabels[0];
                                    
                                    if (representativeLabel) {
                                        if (representativeLabel.length <= 15) {
                                            fieldName = representativeLabel;
                                        } else {
                                            fieldName = representativeLabel.substring(0, 12) + '...';
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // 最終備案：使用索引
                    if (fieldName.startsWith('欄位_') || !fieldName) {
                        fieldName = `欄位 ${triangleIndex + 1}`;
                    }
                    
                    console.log(`欄位名稱: ${fieldName}`);
                    
                    // 設定全域變數
                    customFilterCurrentElement = $specificFilterBox;
                    currentFilterField = fieldName; // 設定當前欄位
                    customFilterCurrentData = [];
                    
                    // 收集這個特定篩選框的選項
                    $specificFilterBox.find('input[type="checkbox"]').each(function() {
                        const $cb = $(this);
                        const $label = $cb.closest('label');
                        const labelText = $label.text().trim();
                        
                        if (labelText && labelText !== 'Select All' && labelText !== '全選') {
                            customFilterCurrentData.push({
                                value: labelText,
                                checked: $cb.prop('checked')
                            });
                        }
                    });
                    
                    console.log(`${fieldName} 的選項:`, customFilterCurrentData);
                    
                    // 顯示自定義篩選器
                    showCustomFilterModal(fieldName);
                } else {
                    console.log(`Triangle ${triangleIndex} 找不到對應的篩選框`);
                    alert('找不到篩選選項');
                }
                
                return false;
            });
        });
        
        console.log(`已為 ${$('.pvtTriangle').length} 個 Triangle 設定攔截器`);
        
    }, 500);
}

function showCustomFilterModal(fieldName = '篩選選項') {
    // 確保彈出視窗存在
    if ($('#customFilterModal').length === 0) {
        createCustomFilterModal();
    }
    
    // 檢查是否在全屏模式
    const modal = document.getElementById('customFilterModal');
    const fullscreenElement = document.fullscreenElement;
    
    if (fullscreenElement) {
        // 全屏模式：附加到全屏元素內，並使用最高 z-index
        if (modal.parentNode !== fullscreenElement) {
            fullscreenElement.appendChild(modal);
        }
        modal.style.zIndex = '2147483647';
        modal.style.position = 'absolute'; // 在全屏內使用 absolute
    } else {
        // 正常模式：附加到 body
        if (modal.parentNode !== document.body) {
            document.body.appendChild(modal);
        }
        modal.style.position = 'fixed';
    }
    
    // 更新選項列表
    const optionsHTML = customFilterCurrentData.map((item) => `
        <div class="filter-option" style="padding: 8px 0; border-bottom: 1px solid #f0f0f0;">
            <label style="display: flex; align-items: center; cursor: pointer;">
                <input type="checkbox" value="${item.value}" ${item.checked ? 'checked' : ''} 
                       style="margin-right: 10px; transform: scale(1.2);">
                <span style="font-size: 14px; color: #333;">${item.value}</span>
            </label>
        </div>
    `).join('');
    
    $('#customFilterOptions').html(optionsHTML);
    
    // 使用傳入的欄位名稱更新標題
    $('#customFilterTitle').text(`${fieldName}`);
    
    $('#customFilterSearch').val('');
    $('#customFilterModal').css('display', 'flex');
    
    console.log(`顯示 ${fieldName} 的篩選器，共 ${customFilterCurrentData.length} 個選項`);
}

function createCustomFilterModal() {
    const modalHTML = `
        <div id="customFilterModal" style="
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.7); z-index: 999999; display: none;
            align-items: center; justify-content: center; font-family: Arial, sans-serif;
        ">
            <div style="
                background: white; border-radius: 12px; padding: 25px;
                max-width: 500px; max-height: 80vh; overflow-y: auto;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin: 20px;
            ">
                <div style="
                    display: flex; justify-content: space-between; align-items: center;
                    margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #2196F3;
                ">
                    <h3 id="customFilterTitle" style="margin: 0; color: #333; font-size: 20px;">篩選選項</h3>
                    <button id="customFilterClose" style="
                        background: #ff4444; color: white; border: none; border-radius: 50%;
                        width: 30px; height: 30px; cursor: pointer; font-size: 18px; font-weight: bold;
                    ">×</button>
                </div>
                
                <div style="margin-bottom: 15px;">
                    <input type="text" id="customFilterSearch" placeholder="搜尋選項..." style="
                        width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 6px;
                        font-size: 14px; box-sizing: border-box;
                    ">
                </div>
                
                <div id="customFilterOptions" style="
                    max-height: 300px; overflow-y: auto; border: 1px solid #eee;
                    border-radius: 6px; padding: 10px;
                "></div>
                
                <div style="
                    display: flex; gap: 10px; margin-top: 20px; justify-content: flex-end;
                ">
                    <button id="customFilterSelectAll" style="
                        background: #4CAF50; color: white; border: none; padding: 10px 15px;
                        border-radius: 6px; cursor: pointer; font-size: 14px;
                    ">全選</button>
                    <button id="customFilterClearAll" style="
                        background: #FF9800; color: white; border: none; padding: 10px 15px;
                        border-radius: 6px; cursor: pointer; font-size: 14px;
                    ">清除</button>
                    <button id="customFilterCancel" style="
                        background: #666; color: white; border: none; padding: 10px 15px;
                        border-radius: 6px; cursor: pointer; font-size: 14px;
                    ">取消</button>
                    <button id="customFilterApply" style="
                        background: #2196F3; color: white; border: none; padding: 10px 20px;
                        border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold;
                    ">確定</button>
                </div>
            </div>
        </div>
    `;
    
    $('body').append(modalHTML);
    bindCustomFilterEvents();
}

function bindCustomFilterEvents() {
    // 關閉事件
    $('#customFilterClose, #customFilterCancel').click(function() {
        $('#customFilterModal').hide();
    });
    
    // 點擊遮罩關閉
    $('#customFilterModal').click(function(e) {
        if (e.target === this) {
            $(this).hide();
        }
    });
    
    // 搜尋功能
    $('#customFilterSearch').on('input', function() {
        const searchTerm = $(this).val().toLowerCase();
        $('#customFilterOptions .filter-option').each(function() {
            const text = $(this).find('span').text().toLowerCase();
            $(this).toggle(text.includes(searchTerm));
        });
    });
    
    // 全選/清除
    $('#customFilterSelectAll').click(function() {
        $('#customFilterOptions input[type="checkbox"]:visible').prop('checked', true);
    });
    
    $('#customFilterClearAll').click(function() {
        $('#customFilterOptions input[type="checkbox"]:visible').prop('checked', false);
    });
    
    // 確定按鈕
    $('#customFilterApply').click(function() {
        applyCustomFilter();
    });
}

function applyCustomFilter() {
    if (!customFilterCurrentElement || !currentFilterField) {
        $('#customFilterModal').hide();
        return;
    }
    
    const fieldName = currentFilterField;
    console.log(`套用 ${fieldName} 的篩選`);
    
    // 建立狀態映射
    const desiredStates = new Map();
    const selectedValues = [];
    
    $('#customFilterOptions input[type="checkbox"]').each(function() {
        const value = $(this).val().trim();
        const checked = $(this).prop('checked');
        desiredStates.set(value, checked);
        
        if (checked) {
            selectedValues.push(value);
        }
    });
    
    // 保存到全域篩選狀態（恢復原有功能）
    if (!window.pivotFilterStates) {
        window.pivotFilterStates = {};
    }
    
    window.pivotFilterStates[fieldName] = {
        selectedValues: selectedValues,
        allValues: Array.from(desiredStates.keys()),
        timestamp: Date.now()
    };
    
    console.log(`${fieldName} 狀態已保存:`, window.pivotFilterStates[fieldName]);
    console.log('套用篩選狀態:', Array.from(desiredStates.entries()));
    
    // 顯示原始篩選框
    const $filterBox = customFilterCurrentElement;
    $filterBox.show();
    
    // 同步狀態
    let updateCount = 0;
    $filterBox.find('input[type="checkbox"]').each(function() {
        const $cb = $(this);
        const $label = $cb.closest('label');
        const labelText = $label.text().trim();
        
        if (labelText && labelText !== 'Select All' && labelText !== '全選') {
            if (desiredStates.has(labelText)) {
                const targetState = desiredStates.get(labelText);
                const currentState = $cb.prop('checked');
                
                if (currentState !== targetState) {
                    console.log(`更新 ${labelText}: ${currentState} -> ${targetState}`);
                    $cb[0].checked = targetState;
                    $cb.prop('checked', targetState);
                    $cb.trigger('change');
                    updateCount++;
                }
            }
        }
    });
    
    console.log(`${fieldName} 更新了 ${updateCount} 個選項`);
    
    // 觸發更新
    setTimeout(() => {
        // 尋找 Apply 按鈕
        const $applyBtn = $filterBox.find('button').filter(function() {
            const text = $(this).text().toLowerCase();
            return text.includes('apply') || text.includes('ok');
        });
        
        if ($applyBtn.length > 0) {
            console.log(`${fieldName} 點擊 Apply 按鈕`);
            $applyBtn.first().click();
        } else {
            console.log(`${fieldName} 使用備用更新方法`);
            // 備用方法：觸發第一個 checkbox 的 change 事件
            $filterBox.find('input[type="checkbox"]').first().trigger('change');
        }
        
        setTimeout(() => {
            $filterBox.hide();
            console.log(`${fieldName} 篩選套用完成`);
        }, 100);
    }, 100);
    
    $('#customFilterModal').hide();
}

function collectCorrectFieldValues($filterBox, attrName) {
    const values = [];
    const seenValues = new Set(); // 防止重複
    
    console.log(`開始收集欄位 "${attrName}" 的值...`);
    
    // 方法1：從篩選框的 label 中收集
    $filterBox.find('label').each(function(index) {
        const $label = $(this);
        const $checkbox = $label.find('input[type="checkbox"]');
        const labelText = $label.text().trim();
        
        // 跳過控制項目（如 Select All）
        if (labelText && 
            labelText !== 'Select All' && 
            labelText !== '全選' && 
            labelText !== 'selectAll' &&
            !seenValues.has(labelText)) {
            
            seenValues.add(labelText);
            
            values.push({
                value: labelText,
                label: labelText,
                checked: $checkbox.prop('checked'),
                index: index
            });
            
            console.log(`  收集值 ${index}: "${labelText}" (checked: ${$checkbox.prop('checked')})`);
        }
    });
    
    console.log(`方法1收集到 ${values.length} 個值`);
    
    // 方法2：如果方法1沒收集到值，嘗試從資料中直接收集
    if (values.length === 0) {
        console.log('方法1無結果，嘗試從樞紐資料收集...');
        
        if (window.pivotData && Array.isArray(window.pivotData)) {
            const uniqueValues = new Set();
            
            window.pivotData.forEach(row => {
                const fieldValue = row[attrName];
                if (fieldValue !== null && fieldValue !== undefined && fieldValue !== '') {
                    const strValue = String(fieldValue);
                    if (!uniqueValues.has(strValue)) {
                        uniqueValues.add(strValue);
                        values.push({
                            value: strValue,
                            label: strValue,
                            checked: true, // 預設全選
                            index: values.length
                        });
                    }
                }
            });
            
            console.log(`方法2從樞紐資料收集到 ${values.length} 個值`);
        }
    }
    
    // 方法3：最後備案 - 從篩選框的所有文字內容收集
    if (values.length === 0) {
        console.log('方法2也無結果，使用備案方法...');
        
        $filterBox.find('*').each(function() {
            const text = $(this).text().trim();
            if (text && 
                text.length < 100 && // 避免長文字
                !text.includes('Select') &&
                !text.includes('全選') &&
                !seenValues.has(text)) {
                
                seenValues.add(text);
                values.push({
                    value: text,
                    label: text,
                    checked: true,
                    index: values.length
                });
            }
        });
        
        console.log(`方法3收集到 ${values.length} 個值`);
    }
    
    // 如果還是沒有值，創建預設值
    if (values.length === 0) {
        console.warn(`欄位 "${attrName}" 沒有收集到任何值，創建預設值`);
        values.push({
            value: '無資料',
            label: '無資料',
            checked: true,
            index: 0
        });
    }
    
    return values;
}

// 修改 showPivotFilterModal，加入全選檢查
function showPivotFilterModal(attrName, values) {
    const modal = document.getElementById('pivotFilterModal');
    const list = document.getElementById('pivotFilterList');
    const title = modal.querySelector('.pivot-filter-title');
    const searchInput = document.getElementById('pivotFilterSearch');
    
    // 設定當前篩選的欄位
    currentFilterField = attrName;
    
    // 設定標題
    title.textContent = `篩選 - ${attrName}`;
    
    // 清空搜尋
    searchInput.value = '';
    
    console.log(`=== 顯示篩選彈出視窗 ===`);
    console.log(`欄位: ${attrName}`);
    console.log(`值數量: ${values.length}`);
    
    // 【關鍵修復】載入該欄位之前保存的狀態
    const savedState = pivotFilterStates[attrName];
    console.log(`載入 ${attrName} 的保存狀態:`, savedState);
    
    // 處理值並應用保存的狀態
    const processedValues = values.map((item, index) => {
        const value = String(item.value || item.label || item || `item_${index}`);
        const label = String(item.label || item.value || item || `項目 ${index + 1}`);
        
        // 【關鍵】檢查是否有保存的狀態
        let checked = true; // 預設選中
        
        if (savedState && savedState.selectedValues) {
            // 如果有保存狀態，使用保存的選中狀態
            checked = savedState.selectedValues.includes(value);
        } else {
            // 如果沒有保存狀態，使用原始狀態
            checked = item.checked !== undefined ? item.checked : true;
        }
        
        return {
            value: value,
            label: label,
            checked: checked,
            index: index
        };
    });
    
    // 生成篩選項目HTML
    list.innerHTML = processedValues.map((item, index) => `
        <div class="pivot-filter-item" data-original-index="${item.index}">
            <label>
                <input type="checkbox" 
                       value="${escapeHtml(item.value)}" 
                       data-label="${escapeHtml(item.label)}"
                       data-index="${index}"
                       ${item.checked ? 'checked' : ''}>
                <span>${escapeHtml(item.label)}</span>
            </label>
        </div>
    `).join('');
    
    // 顯示統計
    const updateStats = () => {
        const total = list.querySelectorAll('input[type="checkbox"]').length;
        const checked = list.querySelectorAll('input[type="checkbox"]:checked').length;
        console.log(`${attrName} 篩選視窗統計: ${checked}/${total} 已選中`);
    };
    
    list.addEventListener('change', updateStats);
    updateStats();
    
    // 顯示彈出視窗
    modal.classList.add('show');
    setTimeout(() => searchInput.focus(), 100);
}

function collectValuesFromDOM(attrName) {
    if (!currentPivotDropdown) return [];
    
    const $filterBox = currentPivotDropdown.find('.pvtFilterBox');
    const values = [];
    
    $filterBox.find('label').each(function(index) {
        const $label = $(this);
        const $checkbox = $label.find('input[type="checkbox"]');
        const text = $label.text().trim();
        
        if (text && text !== 'Select All' && text !== '全選') {
            values.push({
                value: text, // 使用文字作為值
                label: text,
                checked: $checkbox.prop('checked'),
                index: index
            });
        }
    });
    
    console.log(`從DOM收集到 ${values.length} 個值:`, values);
    return values;
}

// 關閉彈出視窗
function closePivotFilterModal() {
    const modal = document.getElementById('pivotFilterModal');
    modal.classList.remove('show');
    
    // 清空搜尋
    const searchInput = document.getElementById('pivotFilterSearch');
    if (searchInput) {
        searchInput.value = '';
    }
    
    // 清理當前參考（但保留狀態）
    currentPivotDropdown = null;
    currentFilterField = null;
    
    console.log('篩選彈出視窗已關閉');
}

// 篩選項目
function filterPivotItems(searchTerm) {
    const items = document.querySelectorAll('.pivot-filter-item');
    const lowerSearchTerm = searchTerm.toLowerCase();
    
    items.forEach(item => {
        const label = item.querySelector('span').textContent.toLowerCase();
        item.style.display = label.includes(lowerSearchTerm) ? '' : 'none';
    });
}

// 全選
function selectAllPivotFilters() {
    const checkboxes = document.querySelectorAll('#pivotFilterList input[type="checkbox"]');
    checkboxes.forEach(cb => {
        if (cb.parentElement.parentElement.style.display !== 'none') {
            cb.checked = true;
        }
    });
}

// 清除
function clearAllPivotFilters() {
    const checkboxes = document.querySelectorAll('#pivotFilterList input[type="checkbox"]');
    checkboxes.forEach(cb => {
        if (cb.parentElement.style.display !== 'none') {
            cb.checked = false;
        }
    });
}

// 修正版 applyPivotFilters - 確保正確同步狀態
function applyPivotFilters() {
    if (!currentPivotDropdown || !currentFilterField) {
        console.error('沒有當前的篩選框參考或欄位名稱');
        closePivotFilterModal();
        return;
    }
    
    const fieldName = currentFilterField;
    const $dropdown = currentPivotDropdown;
    const $filterBox = $dropdown.find('.pvtFilterBox');
    
    // 確保篩選框是可見的
    $filterBox.show();
    
    // 獲取彈出視窗中的選擇狀態
    const modalCheckboxes = document.querySelectorAll('#pivotFilterList input[type="checkbox"]');
    
    console.log(`=== 套用 ${fieldName} 篩選 ===`);
    console.log('彈出視窗 checkbox 數量:', modalCheckboxes.length);
    
    // 【關鍵】收集並保存當前欄位的選中狀態
    const selectedValues = [];
    const allValues = [];
    
    modalCheckboxes.forEach((modalCb) => {
        const value = modalCb.getAttribute('data-label') || modalCb.value;
        allValues.push(value);
        
        if (modalCb.checked) {
            selectedValues.push(value);
        }
    });
    
    // 【重要】保存該欄位的篩選狀態
    pivotFilterStates[fieldName] = {
        selectedValues: [...selectedValues], // 深拷貝
        allValues: [...allValues],
        timestamp: Date.now()
    };
    
    console.log(`保存 ${fieldName} 的篩選狀態:`, pivotFilterStates[fieldName]);
    console.log('選中的值:', selectedValues);
    
    // 在原始篩選框中應用選擇
    let syncedCount = 0;
    $filterBox.find('input[type="checkbox"]').each(function() {
        const $originalCb = $(this);
        const $label = $originalCb.closest('label');
        const labelText = $label.text().trim();
        
        // 精確匹配文字內容
        const shouldBeChecked = selectedValues.includes(labelText);
        
        if ($originalCb.prop('checked') !== shouldBeChecked) {
            $originalCb.prop('checked', shouldBeChecked);
            console.log(`  更新 "${labelText}": ${shouldBeChecked}`);
        }
        
        if (shouldBeChecked) {
            syncedCount++;
        }
    });
    
    console.log(`${fieldName} 成功同步 ${syncedCount} 個選項`);
    
    // 關閉彈出視窗
    closePivotFilterModal();
    
    // 觸發樞紐分析表更新
    setTimeout(() => {
        const $applyBtn = $filterBox.find('button').filter(function() {
            const btnText = $(this).text().trim().toLowerCase();
            return btnText === 'apply' || btnText === '套用' || btnText === 'ok';
        });
        
        if ($applyBtn.length > 0) {
            console.log(`點擊 ${fieldName} 的 Apply 按鈕`);
            $applyBtn[0].click();
        } else {
            console.log(`${fieldName} 找不到Apply按鈕，點擊第一個按鈕`);
            $filterBox.find('button').first().click();
        }
        
        // 隱藏篩選框
        setTimeout(() => {
            $filterBox.hide();
        }, 100);
    }, 100);
}

function escapeHtml(text) {
    if (typeof text !== 'string') {
        text = String(text);
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 強制更新樞紐分析表（包含篩選）
function forceRefreshPivotWithFilter() {
    console.log('執行強制更新...');
    
    try {
        const $container = $('#pivotContainer');
        
        // 方法1：觸發任意一個 checkbox 的 change 事件
        const $anyCheckbox = $('.pvtFilterBox input[type="checkbox"]').first();
        if ($anyCheckbox.length > 0) {
            console.log('觸發 checkbox change 事件');
            $anyCheckbox.trigger('change');
        }
        
        // 方法2：切換渲染器
        setTimeout(() => {
            const $renderer = $('.pvtRenderer');
            if ($renderer.length > 0) {
                const currentVal = $renderer.val();
                console.log('切換渲染器來強制更新');
                
                // 找一個不同的渲染器
                const options = $renderer.find('option');
                let differentVal = currentVal;
                
                options.each(function() {
                    if ($(this).val() !== currentVal) {
                        differentVal = $(this).val();
                        return false;
                    }
                });
                
                // 切換並立即切回
                $renderer.val(differentVal).trigger('change');
                setTimeout(() => {
                    $renderer.val(currentVal).trigger('change');
                }, 50);
            }
        }, 100);
        
    } catch (error) {
        console.error('強制更新失敗:', error);
    }
}

// 檢查是否有可見的資料
function hasVisibleData($table) {
    const visibleRows = $table.find('tbody tr:visible');
    return visibleRows.length > 0;
}

// 強制重新整理樞紐分析表
function forceRefreshPivot() {
    try {
        const $container = $('#pivotContainer');
        const pivotUIOptions = $container.data("pivotUIOptions");
        
        if (!pivotUIOptions || !pivotUIOptions.data) {
            console.error('無法獲取樞紐分析表配置');
            return;
        }
        
        console.log('執行強制重新整理...');
        
        // 保存當前配置
        const currentConfig = {
            rows: pivotUIOptions.rows || [],
            cols: pivotUIOptions.cols || [],
            vals: pivotUIOptions.vals || [],
            aggregatorName: pivotUIOptions.aggregatorName || "Count",
            rendererName: pivotUIOptions.rendererName || "Table"
        };
        
        // 清空並重新渲染
        $container.empty();
        
        // 重新初始化，保持原有配置
        $container.pivotUI(pivotUIOptions.data, $.extend({}, pivotUIOptions, currentConfig));
        
        // 重新綁定事件
        setTimeout(() => {
            interceptPivotDropdowns();
            
            // 如果拖曳區是隱藏的，重新隱藏
            if (!areasVisible) {
                $('.pvtUnused, .pvtRows, .pvtCols, .pvtVals').hide();
                $('.pvtRenderer, .pvtAggregator, .pvtAttrDropdown').parent().hide();
            }
        }, 200);
        
    } catch (error) {
        console.error('強制重新整理失敗:', error);
    }
}

function renderPivotTable(sheetData) {
    const container = document.getElementById('pivotContainer');
    container.innerHTML = '';
    
    if (!sheetData || !sheetData.data || sheetData.data.length === 0) {
        container.innerHTML = `
            <div class="no-data-message">
                <i class="fas fa-inbox"></i>
                <h3>沒有資料可供分析</h3>
                <p>請先選擇包含資料的工作表</p>
            </div>
        `;
        return;
    }
    
    try {
        // 確保資料是正確的陣列格式
        let processedData = [];
        
        // 檢查資料格式並處理
        if (Array.isArray(sheetData.data)) {
            processedData = sheetData.data.map((row, index) => {
                // 確保每一行都是物件格式
                if (typeof row === 'object' && row !== null) {
                    // 移除可能造成問題的特殊欄位
                    const cleanRow = {};
                    for (let key in row) {
                        // 跳過可能有問題的欄位
                        if (key === '_id' || key === '__v' || key === '$$hashKey') {
                            continue;
                        }
                        
                        // 處理特殊值
                        let value = row[key];
                        
                        // 處理 null、undefined
                        if (value === null || value === undefined) {
                            cleanRow[key] = '';
                        }
                        // 處理陣列和物件（轉為字串）
                        else if (typeof value === 'object') {
                            cleanRow[key] = JSON.stringify(value);
                        }
                        // 處理布林值
                        else if (typeof value === 'boolean') {
                            cleanRow[key] = value ? 'Y' : 'N';
                        }
                        // 處理數字和字串
                        else {
                            cleanRow[key] = String(value);
                        }
                    }
                    return cleanRow;
                } else {
                    console.warn(`第 ${index + 1} 行資料格式不正確:`, row);
                    return null;
                }
            }).filter(row => row !== null); // 移除無效的行
        } else {
            console.error('資料不是陣列格式:', sheetData.data);
            throw new Error('資料格式錯誤：預期為陣列');
        }
        
        // 檢查處理後的資料
        if (processedData.length === 0) {
            container.innerHTML = `
                <div class="no-data-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>資料處理失敗</h3>
                    <p>無法正確解析資料格式</p>
                </div>
            `;
            return;
        }
        
        console.log('處理後的資料筆數:', processedData.length);
        console.log('資料範例:', processedData[0]);
        
        // 儲存原始資料和配置
        pivotData = processedData;
        pivotInitialData = JSON.parse(JSON.stringify(processedData)); // 深拷貝
        
        // 定義初始配置（移除 filter 屬性）
        pivotInitialConfig = {
            rows: [],
            cols: [],
            vals: [],
            aggregatorName: "Count",
            rendererName: "Table",
            unusedAttrsVertical: true,
            renderers: $.pivotUtilities.renderers,
            aggregators: $.pivotUtilities.aggregators,
            derivedAttributes: {},
            hiddenAttributes: [],
            localeStrings: {
                renderError: "結果計算錯誤",
                computeError: "資料計算錯誤",
                uiRenderError: "介面繪製錯誤",
                selectAll: "全選",
                selectNone: "取消全選",
                tooMany: "(太多項目無法顯示)",
                filterResults: "篩選結果",
                totals: "總計",
                vs: "vs",
                by: "by",
                aggregators: {
                    "Count": "計數",
                    "Count Unique Values": "計數唯一值",
                    "List Unique Values": "列出唯一值",
                    "Sum": "總和",
                    "Integer Sum": "整數總和",
                    "Average": "平均",
                    "Median": "中位數",
                    "Sample Variance": "樣本變異數",
                    "Sample Standard Deviation": "樣本標準差",
                    "Minimum": "最小值",
                    "Maximum": "最大值",
                    "First": "第一個",
                    "Last": "最後一個",
                    "Sum over Sum": "總和比例",
                    "Sum as Fraction of Total": "總和佔比",
                    "Sum as Fraction of Rows": "列總和佔比",
                    "Sum as Fraction of Columns": "欄總和佔比",
                    "Count as Fraction of Total": "計數佔比",
                    "Count as Fraction of Rows": "列計數佔比",
                    "Count as Fraction of Columns": "欄計數佔比"
                },
                renderers: {
                    "Table": "表格",
                    "Table Barchart": "表格長條圖",
                    "Heatmap": "熱圖",
                    "Row Heatmap": "列熱圖",
                    "Col Heatmap": "欄熱圖"
                }
            },
            onRefresh: function(config) {
                pivotConfig = config;
                console.log('樞紐分析表已更新');
            }
        };
        
        // 渲染樞紐分析表
        $(container).pivotUI(processedData, pivotInitialConfig);
        
        // 初始化彈出視窗
        initializePivotFilterModal();
        
        // 延遲初始化攔截，確保 DOM 已完全載入
        setTimeout(() => {
            interceptPivotDropdowns();
        }, 500);

        // 設定攔截器
        setTimeout(() => {
            interceptPivotDropdowns();
        }, 500);

    } catch (error) {
        console.error('樞紐分析錯誤詳情:', error);
        console.error('錯誤堆疊:', error.stack);
        
        // 顯示詳細的錯誤訊息
        container.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>樞紐分析表載入失敗</h3>
                <p>${error.message || '未知錯誤'}</p>
                <div class="action-buttons">
                    <button class="btn btn-refresh" onclick="location.reload()">
                        <i class="fas fa-sync-alt"></i> 重新整理頁面
                    </button>
                </div>
            </div>
        `;
    }
}

// 取得後端對應的資料表名稱（英文）
function getBackendSheetName(displaySheetName) {
    const sheetMapping = {
        // 中文顯示名稱 -> 後端實際名稱
        'Revision 差異': 'revision_diff',
        '分支錯誤': 'branch_error', 
        '新增/刪除專案': 'lost_project',
        '版本檔案差異': 'version_diff',
        '無法比對的模組': '無法比對',
        '比對摘要': '摘要',
        '所有情境摘要': 'all_scenarios',
        'Master vs PreMP': 'master_vs_premp',
        'PreMP vs Wave': 'premp_vs_wave',
        'Wave vs Backup': 'wave_vs_backup'
    };
    
    // 如果有對應的映射，使用映射值；否則直接使用原值
    return sheetMapping[displaySheetName] || displaySheetName;
}

// 檢查當前資料表的實際名稱
function getCurrentSheetBackendName() {
    // 優先使用原始的 key 名稱（通常是英文）
    if (currentData && currentSheet && currentData[currentSheet]) {
        return currentSheet;
    }
    
    // 如果找不到，嘗試映射
    return getBackendSheetName(getSheetDisplayName(currentSheet));
}

// 從URL參數初始化情境設定
function initializeScenarioFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    const scenarioParam = urlParams.get('scenario');
    
    if (scenarioParam) {
        console.log('從URL讀取到情境:', scenarioParam);
        currentScenario = scenarioParam;
    } else {
        console.log('URL中沒有情境參數，使用預設值');
        currentScenario = 'all';
    }
    
    console.log('初始化情境設定:', currentScenario);
}

// 將函數綁定到 window
window.closePivotFilterModal = closePivotFilterModal;
window.selectAllPivotFilters = selectAllPivotFilters;
window.clearAllPivotFilters = clearAllPivotFilters;
window.applyPivotFilters = applyPivotFilters;

// 匯出函數
window.togglePivotMode = togglePivotMode;
window.applyFilters = applyFilters;
window.clearFilters = clearFilters;
window.toggleFilterPanel = toggleFilterPanel;
window.exportCurrentView = exportCurrentView;
window.downloadFullReport = downloadFullReport;
window.exportPageAsHTML = exportPageAsHTML;
window.togglePivotFullscreen = togglePivotFullscreen;
window.togglePivotAreas = togglePivotAreas;
window.showCustomFilterModal = showCustomFilterModal;
window.createCustomFilterModal = createCustomFilterModal;
window.bindCustomFilterEvents = bindCustomFilterEvents;
window.applyCustomFilter = applyCustomFilter;
window.adjustPivotContainerSize = adjustPivotContainerSize;
window.exportToExcelClientSide = exportToExcelClientSide;
window.exportAllSheetsClientSide = exportAllSheetsClientSide;
window.cleanExcelSheetName = cleanExcelSheetName;
window.cleanFileName = cleanFileName;
