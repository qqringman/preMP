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
                <div class="no-data-message">
                    <i class="fas fa-inbox"></i>
                    <h3>暫無資料可顯示</h3>
                    <p>此任務可能還在處理中，或尚未產生報表。</p>
                    <button class="btn-refresh">
                        <span>重新整理</span>
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
                        <button class="btn-refresh" onclick="location.reload()">
                            <span>重試</span>
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
            
            // 移除固定寬度設定
            // td.style.width = getColumnWidth(col);
            // td.style.minWidth = getColumnWidth(col);
            
            // 根據欄位類型添加 class
            td.classList.add('path-cell');

            // 根據欄位類型處理顯示
            if (col === 'path' || col.toLowerCase().includes('path')) {
                td.classList.add('path-cell');
                
                if (value && value.length > 80) {  // 從 50 改為 80
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
                // 內容比較欄位處理
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
                        
                        // 根據檔案類型處理
                        const fileType = row['file_type'] || '';
                        let formattedValue = String(value);
                        
                        // 檢查是否包含多行（換行符）
                        if (value.includes('\n')) {
                            // 處理多行內容
                            formattedValue = formatMultiLineContent(value, compareValue, fileType);
                        } else {
                            // 單行處理（原有邏輯）
                            if (value.includes('F_HASH:')) {
                                if (compareValue) {
                                    formattedValue = formatFHashContent(value, compareValue);
                                }
                            } else if (fileType.toLowerCase() === 'f_version.txt' && value.startsWith('P_GIT_')) {
                                if (compareValue && compareValue.startsWith('P_GIT_')) {
                                    formattedValue = formatFVersionContent(value, compareValue);
                                }
                            } else if (value.includes(':') && !value.includes('F_HASH:')) {
                                if (compareValue && compareValue.includes(':')) {
                                    formattedValue = formatColonContent(value, compareValue);
                                }
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
            
            // 設定 data-sheet 屬性以應用特定樣式
            if (tableView && currentSheet) {
                tableView.setAttribute('data-sheet', currentSheet);
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

function formatMultiLineContent(value, compareValue, fileType) {
    const lines = value.split('\n');
    const compareLines = compareValue ? compareValue.split('\n') : [];
    
    let formattedLines = [];
    
    lines.forEach((line, index) => {
        const compareLine = compareLines[index] || '';
        let formattedLine = line;
        
        if (line.startsWith('P_GIT_')) {
            // F_Version.txt 格式
            formattedLine = formatFVersionContent(line, compareLine);
        } else if (line.includes('F_HASH:')) {
            // F_HASH 格式
            formattedLine = formatFHashContent(line, compareLine);
        } else if (line.includes(':')) {
            // key:value 格式
            formattedLine = formatColonContent(line, compareLine);
        }
        
        formattedLines.push(formattedLine);
    });
    
    // 用 <br> 連接所有行
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

// 修改 renderPivotTable 函數
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

// 顯示提示訊息
function showToast(message, type = 'info') {
    // 創建提示元素
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-info-circle'}"></i>
        <span>${message}</span>
    `;
    
    // 添加到頁面
    document.body.appendChild(toast);
    
    // 顯示動畫
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // 3秒後移除
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// 匯出函數
window.resetPivotTable = resetPivotTable;
window.exportPivotTable = exportPivotTable;

// 切換樞紐分析模式
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
        }
    ];
    
    // 根據資料表類型調整統計
    if (currentSheet === 'revision_diff') {
        // 計算不同版號的數量（實際上就是總筆數，因為每一筆都代表版號不同）
        const differentRevisions = sheetData.data.length;
        
        // 計算唯一模組數
        const uniqueModules = new Set(sheetData.data.map(row => row.module).filter(m => m));
        
        // 計算 has_wave 的統計
        const hasWaveY = sheetData.data.filter(row => row.has_wave === 'Y').length;
        const hasWaveN = sheetData.data.filter(row => row.has_wave === 'N').length;
        
        // 加入不同版號統計
        stats.push({
            label: '不同版號',
            value: differentRevisions,
            icon: 'fa-code-branch',
            color: 'warning'
        });
        
        // 加入模組數統計
        stats.push({
            label: '模組數',
            value: uniqueModules.size,
            icon: 'fa-cube',
            color: 'purple'
        });
        
        // 加入 has_wave 統計
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
        // 比對摘要的統計邏輯（保持不變）
        let totalSuccess = 0;
        let totalFailed = 0;
        
        sheetData.data.forEach(row => {
            const scenario = row['比對情境'] || row['scenario'] || '';
            if (scenario === '總計' || scenario.toLowerCase() === 'total') {
                return;
            }
            
            const successCount = parseInt(row['成功模組數'] || row['success_count'] || 0);
            const failedCount = parseInt(row['失敗模組數'] || row['failed_count'] || 0);
            
            if (!isNaN(successCount)) {
                totalSuccess += successCount;
            }
            if (!isNaN(failedCount)) {
                totalFailed += failedCount;
            }
        });
        
        stats[0].value = sheetData.data.filter(row => {
            const scenario = row['比對情境'] || row['scenario'] || '';
            return scenario !== '總計' && scenario.toLowerCase() !== 'total';
        }).length;
        
        stats.push({
            label: '成功模組',
            value: totalSuccess,
            icon: 'fa-check-circle',
            color: 'success'
        });
        
        if (totalFailed > 0) {
            stats.push({
                label: '失敗模組',
                value: totalFailed,
                icon: 'fa-times-circle',
                color: 'danger'
            });
        }
    } else if (currentSheet === 'version_diff' || currentSheet === '版本檔案差異') {
        // 版本檔案差異的統計邏輯（保持不變）
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
                <div class="stat-value">${stat.value.toLocaleString()}</div>
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
async function exportCurrentView(format) {
    if (!currentData || !currentSheet) {
        alert('請先選擇資料表');
        return;
    }
    
    try {
        if (format === 'excel') {
            showExportLoading();
            
            // 從後端獲取原始 Excel 檔案，只保留當前資料表
            const response = await fetch(`/api/export-excel-single/${taskId}/${currentSheet}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error('無法獲取 Excel 檔案');
            }
            
            // 獲取檔案 blob
            const blob = await response.blob();
            
            // 下載檔案
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${currentSheet}_${new Date().toISOString().slice(0, 10)}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            hideExportLoading();
            showToast('Excel 檔案已匯出', 'success');
        }
    } catch (error) {
        console.error('匯出錯誤:', error);
        hideExportLoading();
        alert('匯出失敗：' + error.message);
    }
}

// 下載完整報表
async function downloadFullReport() {
    try {
        // 直接下載原始的完整 Excel 檔案
        window.location.href = `/api/export-excel/${taskId}`;
    } catch (error) {
        console.error('下載完整報表錯誤:', error);
        alert('下載失敗：' + error.message);
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
        
        // 獲取當前所有的 JavaScript 函數
        const jsCode = getAllRequiredFunctions();
        
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
        
        /* 額外的離線模式樣式 */
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
        
        /* 確保離線模式下的響應式設計 */
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
                                        <button class="btn btn-primary btn-sm" onclick="exportPivotTable()">
                                            <i class="fas fa-file-excel"></i> 匯出
                                        </button>
                                    </div>
                                </div>
                                
                                <div class="pivot-instructions">
                                    <i class="fas fa-info-circle"> 拖曳欄位到不同區域來建立樞紐分析表</i>
                                    <ul>
                                        <li>拖曳欄位到列或欄區域來分組資料</li>
                                        <li>選擇不同的彙總函數（總和、平均、計數等）</li>
                                        <li>使用篩選器來過濾資料</li>
                                        <li>點擊表格標題來排序</li>
                                    </ul>
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

    <!-- 浮動按鈕 -->
    <div class="fab-container">
        <button class="fab-filter" onclick="toggleFilterPanel()" title="資料篩選器" id="fabFilter">
            <i class="fas fa-filter"></i>
        </button>
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
    if (!value2) return value1;  // 如果沒有比較值，返回原值
    
    const parts1 = value1.split(';');
    const parts2 = value2.split(';');
    
    // P_GIT_001;realtek/bootcode;realtek/mac7p_64/master;2ef5076;1005445
    // 索引: 0=P_GIT_001, 1=repo, 2=branch, 3=hash, 4=revision
    
    if (parts1.length < 5) return value1;
    
    let result = '';
    for (let i = 0; i < parts1.length; i++) {
        if (i > 0) result += ';';
        
        // 索引 3 是 git hash，索引 4 是 revision number
        if (i === 3 || i === 4) {
            // 確保比較的部分存在且不同
            if (parts2[i] && parts1[i] !== parts2[i]) {
                // 使用 inline style 確保顏色顯示
                result += `<span style="color: #dc3545; font-weight: 600; background-color: rgba(220, 53, 69, 0.1); padding: 0 2px; border-radius: 2px;">${parts1[i]}</span>`;
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
    // 處理 F_HASH: (not found) 的情況
    const notFoundPattern = /F_HASH:\s*\(not found\)/i;
    const hashPattern = /F_HASH:\s*([a-f0-9]+)/i;
    
    // 檢查是否包含 (not found)
    const hasNotFound1 = notFoundPattern.test(value1);
    const hasNotFound2 = notFoundPattern.test(value2);
    
    // 如果其中一個是 (not found)，另一個不是，則標記紅色
    if (hasNotFound1 || hasNotFound2) {
        if (hasNotFound1 && !hasNotFound2) {
            // value1 是 (not found)，標記為紅色
            return value1.replace('(not found)', '<span class="highlight-red">(not found)</span>');
        } else if (!hasNotFound1 && hasNotFound2) {
            // value2 是 (not found)，value1 有 hash 值，標記 hash 為紅色
            const match1 = value1.match(hashPattern);
            if (match1) {
                return value1.replace(match1[1], `<span class="highlight-red">${match1[1]}</span>`);
            }
        } else if (hasNotFound1 && hasNotFound2) {
            // 兩個都是 (not found)，不標記
            return value1;
        }
    }
    
    // 正常的 hash 比較
    const match1 = value1.match(hashPattern);
    const match2 = value2.match(hashPattern);
    
    if (match1 && match2) {
        const hash1 = match1[1];
        const hash2 = match2[1];
        
        if (hash1 !== hash2) {
            return value1.replace(hash1, `<span class="highlight-red">${hash1}</span>`);
        }
    }
    
    return value1;
}

// 格式化包含冒號的內容 - 只標記不同的值
function formatColonContent(value1, value2) {
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
        return `${key1}: <span class="highlight-red">${val1}</span>`;
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
                    
                    // 強制重新計算樞紐分析表大小
                    const pivotContainer = document.getElementById('pivotContainer');
                    if (!pivotContainer) {
                        console.warn('找不到 pivotContainer');
                        return;
                    }
                    
                    // 直接使用已知存在的 pivotView
                    const stepHeader = pivotView.querySelector('.step-header');
                    const pivotControls = pivotView.querySelector('.pivot-controls');
                    const instructions = pivotView.querySelector('.pivot-instructions');
                    
                    // 計算已使用高度
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
                    
                    // 設定容器高度 (留 20px 緩衝)
                    const availableHeight = Math.max(window.innerHeight - usedHeight - 20, 300); // 最小高度 300px
                    
                    pivotContainer.style.height = `${availableHeight}px`;
                    pivotContainer.style.maxHeight = `${availableHeight}px`;
                    
                    // 如果有樞紐分析表實例，強制重新渲染
                    if (window.$ && typeof window.$.fn.pivotUI === 'function') {
                        const $container = window.$('#pivotContainer');
                        const pivotOptions = $container.data("pivotUIOptions");
                        
                        if (pivotOptions && pivotOptions.data) {
                            // 暫存當前配置
                            const currentConfig = {
                                rows: pivotOptions.rows || [],
                                cols: pivotOptions.cols || [],
                                vals: pivotOptions.vals || [],
                                aggregatorName: pivotOptions.aggregatorName || "Count",
                                rendererName: pivotOptions.rendererName || "Table"
                            };
                            
                            // 重新初始化
                            $container.empty();
                            $container.pivotUI(pivotOptions.data, Object.assign({}, pivotOptions, currentConfig));
                        }
                    }
                } catch (error) {
                    console.error('調整全螢幕大小時發生錯誤:', error);
                }
            }, 150); // 稍微延長等待時間
            
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
            
            // 退出全螢幕後恢復原始高度
            const pivotContainer = document.getElementById('pivotContainer');
            if (pivotContainer) {
                pivotContainer.style.height = '600px';
                pivotContainer.style.maxHeight = '600px';
            }
            
            // 退出全螢幕後也觸發 resize
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
            }, 100);
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
    } else {
        // 隱藏拖曳區域和控制區
        $('.pvtUnused, .pvtRows, .pvtCols, .pvtVals').hide();
        $('.pvtRenderer, .pvtAggregator, .pvtAttrDropdown').parent().hide();
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
        text.textContent = '顯示拖曳區';
        pivotContainer.classList.add('areas-hidden');
    }
}

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