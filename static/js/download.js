// 下載頁面 JavaScript - 統一模態框樣式版本

// 頁面變數
let selectedSource = 'local';
let selectedFiles = [];
let localSelectedFiles = [];
let serverSelectedFiles = [];  
let downloadTaskId = null;
let currentServerPath = '/home/vince_lin/ai/preMP';
let serverFilesLoaded = false;
let pathInputTimer = null;
let downloadedFilesList = [];
let skippedFilesList = [];
let failedFilesList = [];
let previewSource = null;
let currentModalFiles = []; // 當前模態框顯示的檔案
let currentSortColumn = null;
let currentSortOrder = 'asc';
let uploadedExcelInfo = null; // 儲存上傳的Excel資訊

// 比對結果相關變數（新增）
let compareResults = null;
let currentModalData = null;

// 確保 DOM 載入完成後初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing...'); // 調試用
    
    // 綁定所有函數到 window
    bindWindowFunctions();
    
    // 初始化功能
    initializeTabs();
    initializeUploadAreas();
    initializeConfigToggles();
    updateDownloadButton();
    
    // 修正預設設定開關
    const useDefaultConfig = document.getElementById('useDefaultConfig');
    if (useDefaultConfig) {
        useDefaultConfig.addEventListener('change', (e) => {
            toggleSftpConfig(e.target.checked);
        });
        toggleSftpConfig(useDefaultConfig.checked);
    }
});

// 綁定函數到 window
function bindWindowFunctions() {
    window.selectSource = selectSource;
    window.switchTab = switchTab;
    window.toggleDepthControl = toggleDepthControl;
    window.removeFile = removeFile;
    window.navigateTo = navigateTo;
    window.navigateToParent = navigateToParent;
    window.toggleServerFile = toggleServerFile;
    window.removeServerFile = removeServerFile;
    window.refreshServerFiles = refreshServerFiles;
    window.adjustDepth = adjustDepth;
    window.testSftpConnection = testSftpConnection;
    window.startDownload = startDownload;
    window.clearLog = clearLog;
    window.toggleFolder = toggleFolder;
    window.previewFile = previewFile;
    window.downloadFile = downloadFile;
    window.closePreview = closePreview;
    window.viewReport = viewReport;
    window.proceedToCompare = proceedToCompare;
    window.newDownload = newDownload;
    window.goToPath = goToPath;
    window.hideSuggestions = hideSuggestions;
    window.selectSuggestion = selectSuggestion;
    window.showFilesList = showFilesList;
    window.closeFilesModal = closeFilesModal;
    window.previewFileFromList = previewFileFromList;
    window.copyPreviewContent = copyPreviewContent;
    window.searchModalContent = searchModalContent;
    window.clearModalSearch = clearModalSearch;
    window.sortModalTable = sortModalTable;
    // 新增比對相關函數
    window.showCompareDetails = showCompareDetails;
    window.closeCompareModal = closeCompareModal;
    window.switchCompareTab = switchCompareTab;
    window.searchCompareContent = searchCompareContent;
    window.clearCompareSearch = clearCompareSearch;
}

// ==================== 新增：比對結果顯示功能（與 compare.html 統一） ====================

// 顯示比對詳細資料 - 使用與 compare.html 相同的模態框樣式
async function showCompareDetails(type) {
    // 模擬比對資料（實際應從後端獲取）
    const mockData = getMockCompareData(type);
    
    if (!mockData) {
        showEmptyModal(getModalTitle(type), getModalClass(type));
        return;
    }
    
    currentModalData = mockData;
    showCompareModal(mockData.pivotData, mockData.sheets, mockData.title, mockData.modalClass);
}

// 獲取模態框標題
function getModalTitle(type) {
    const titles = {
        'master_vs_premp': 'Master vs PreMP',
        'premp_vs_wave': 'PreMP vs Wave',
        'wave_vs_backup': 'Wave vs Backup',
        'failed': '無法比對的模組'
    };
    return titles[type] || '比對結果';
}

// 獲取模態框樣式類別
function getModalClass(type) {
    const classes = {
        'master_vs_premp': 'info',
        'premp_vs_wave': 'success',
        'wave_vs_backup': 'warning',
        'failed': 'danger'
    };
    return classes[type] || 'primary';
}

// 顯示比對模態框 - 與 compare.html 統一樣式
function showCompareModal(pivotData, sheets, title, modalClass) {
    let modal = document.getElementById('compareDetailsModal');
    
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'compareDetailsModal';
        modal.className = 'modal hidden';
        document.body.appendChild(modal);
    }
    
    modal.className = `modal ${modalClass}`;
    
    if (!sheets || sheets.length === 0) {
        modal.innerHTML = generateEmptyModal(title, modalClass);
    } else if (sheets.length === 1) {
        modal.innerHTML = generateSingleSheetModal(pivotData[sheets[0].name], sheets[0], title, modalClass);
    } else {
        modal.innerHTML = generateMultiSheetModal(pivotData, sheets, title, modalClass);
    }
    
    modal.classList.remove('hidden');
}

// 生成空模態框
function generateEmptyModal(title, modalClass) {
    return `
        <div class="modal-content modal-large">
            <div class="modal-header">
                <h3 class="modal-title">
                    <i class="fas fa-table"></i> ${title}
                </h3>
                <span class="modal-count">共 0 筆資料</span>
                <button class="modal-close" onclick="closeCompareModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="empty-message">
                    <i class="fas fa-inbox"></i>
                    <p>沒有找到相關資料</p>
                </div>
            </div>
        </div>
    `;
}

// 生成單頁籤模態框
function generateSingleSheetModal(sheetData, sheet, title, modalClass) {
    const recordCount = sheetData && sheetData.data ? sheetData.data.length : 0;
    
    let html = `
        <div class="modal-content modal-large">
            <div class="modal-header">
                <h3 class="modal-title">
                    <i class="fas fa-table"></i> ${title}
                </h3>
                <span class="modal-count">共 ${recordCount} 筆資料</span>
                <button class="modal-close" onclick="closeCompareModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
    `;
    
    if (sheetData && sheetData.data && sheetData.data.length > 0) {
        // 搜尋列
        html += `
            <div class="modal-search-bar">
                <div class="search-input-wrapper">
                    <i class="fas fa-search search-icon"></i>
                    <input type="text" 
                           class="search-input" 
                           id="compare-search-input" 
                           placeholder="搜尋內容..."
                           onkeyup="searchCompareContent()">
                </div>
                <div class="search-stats">
                    <i class="fas fa-filter"></i>
                    <span>找到 <span class="highlight-count" id="compareSearchCount">${recordCount}</span> 筆</span>
                </div>
                <button class="btn-clear-search" onclick="clearCompareSearch()">
                    <i class="fas fa-times"></i> 清除
                </button>
            </div>
        `;
        
        // 表格
        html += generateCompareTable(sheetData, sheet.name);
        
        // 底部統計
        html += `
            <div class="table-footer">
                <div class="table-footer-stats">
                    <div class="footer-stat">
                        <i class="fas fa-chart-bar"></i>
                        <span>共 <span class="footer-stat-value">${recordCount}</span> 個項目</span>
                    </div>
                </div>
            </div>
        `;
    } else {
        html += '<div class="empty-message"><i class="fas fa-inbox"></i><p>沒有資料</p></div>';
    }
    
    html += '</div></div>';
    return html;
}

// 生成多頁籤模態框
function generateMultiSheetModal(pivotData, sheets, title, modalClass) {
    const firstSheetData = pivotData[sheets[0].name];
    const firstSheetCount = firstSheetData && firstSheetData.data ? firstSheetData.data.length : 0;
    
    let html = `
        <div class="modal-content modal-large">
            <div class="modal-header">
                <h3 class="modal-title">
                    <i class="fas fa-table"></i> ${title}
                </h3>
                <span class="modal-count" id="modalRecordCount">共 ${firstSheetCount} 筆資料</span>
                <button class="modal-close" onclick="closeCompareModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
    `;
    
    // 頁籤
    html += '<div class="modal-tabs">';
    sheets.forEach((sheet, index) => {
        const sheetData = pivotData[sheet.name];
        const recordCount = sheetData && sheetData.data ? sheetData.data.length : 0;
        const isActive = index === 0;
        
        html += `
            <button class="modal-tab-btn ${isActive ? 'active' : ''}" 
                    onclick="switchCompareTab('${sheet.name}', this)"
                    data-count="${recordCount}">
                <i class="fas fa-file-alt"></i> ${sheet.title}
                <span class="tab-count">${recordCount}</span>
            </button>
        `;
    });
    html += '</div>';
    
    // 各頁籤內容
    sheets.forEach((sheet, index) => {
        const isActive = index === 0;
        const sheetData = pivotData[sheet.name];
        
        html += `
            <div class="tab-content ${isActive ? 'active' : ''}" 
                 id="tab-${sheet.name}" 
                 style="display: ${isActive ? 'block' : 'none'};">
        `;
        
        if (sheetData && sheetData.data && sheetData.data.length > 0) {
            html += generateCompareTable(sheetData, sheet.name);
        } else {
            html += '<div class="empty-message"><i class="fas fa-inbox"></i><p>沒有資料</p></div>';
        }
        
        html += '</div>';
    });
    
    html += '</div></div>';
    return html;
}

// 生成比對表格
function generateCompareTable(sheetData, sheetName) {
    if (!sheetData || !sheetData.columns || !sheetData.data || sheetData.data.length === 0) {
        return '<div class="empty-message"><i class="fas fa-inbox"></i><p>此資料表沒有內容</p></div>';
    }
    
    let html = '<div class="table-wrapper">';
    html += '<div class="table-container">';
    html += `<table class="modal-table" id="table-${sheetName}">`;
    
    // 表頭
    html += '<thead><tr>';
    sheetData.columns.forEach(col => {
        const columnInfo = getColumnInfo(col, sheetName);
        html += `<th style="min-width: ${columnInfo.width};" class="${columnInfo.headerClass}">
                    ${columnInfo.text}
                 </th>`;
    });
    html += '</tr></thead>';
    
    // 表身
    html += '<tbody>';
    sheetData.data.forEach((row, index) => {
        html += '<tr>';
        sheetData.columns.forEach(col => {
            const value = row[col];
            const cellContent = formatCellContent(value, col, row, sheetName);
            const cellClass = getCellClass(col, value, sheetName);
            const columnInfo = getColumnInfo(col, sheetName);
            
            html += `<td class="${cellClass}" style="min-width: ${columnInfo.width};">
                        ${cellContent}
                     </td>`;
        });
        html += '</tr>';
    });
    html += '</tbody>';
    
    html += '</table>';
    html += '</div></div>';
    
    return html;
}

// 獲取欄位資訊
function getColumnInfo(col, sheetName) {
    const columnMap = {
        'SN': { text: 'SN', width: '60px', headerClass: '' },
        'module': { text: '模組名稱', width: '200px', headerClass: '' },
        'location_path': { text: 'FTP 路徑', width: '400px', headerClass: '' },
        'path': { text: 'FTP 路徑', width: '400px', headerClass: '' },
        'base_folder': { text: '本地路徑', width: '300px', headerClass: '' },
        'base_content': { text: 'base_content', width: '400px', headerClass: 'header-red-bg' },
        'compare_content': { text: 'compare_content', width: '400px', headerClass: 'header-red-bg' },
        'problem': { text: '問題', width: '200px', headerClass: 'header-red-bg' },
        '狀態': { text: '狀態', width: '100px', headerClass: 'header-red-bg' },
        'has_wave': { text: 'has_wave', width: '100px', headerClass: '' }
    };
    
    return columnMap[col] || { text: col, width: '150px', headerClass: '' };
}

// 獲取單元格樣式
function getCellClass(col, value, sheetName) {
    let classes = [];
    
    if (col === 'problem' && value) {
        classes.push('text-red');
    } else if (col === '狀態') {
        if (value === '刪除') classes.push('text-red');
        else if (value === '新增') classes.push('text-blue');
    } else if (['base_short', 'base_revision', 'compare_short', 'compare_revision'].includes(col)) {
        classes.push('text-red');
    }
    
    return classes.join(' ');
}

// 格式化單元格內容
function formatCellContent(value, col, row, sheetName) {
    if (!value && value !== 0) return '-';
    
    // 模組名稱處理
    if (col === 'module' || col === '模組名稱') {
        const icon = getFileIcon(value);
        return `
            <div style="display: flex; align-items: center; gap: 8px;">
                <i class="fas ${icon}" style="color: #2196F3;"></i>
                <span>${value}</span>
            </div>
        `;
    }
    
    // SN 欄位
    if (col === 'SN') {
        return `<div style="text-align: center;">${value}</div>`;
    }
    
    // has_wave 欄位
    if (col === 'has_wave') {
        if (value === 'Y') {
            return '<span class="badge badge-info">Y</span>';
        } else if (value === 'N') {
            return '<span class="badge badge-warning">N</span>';
        }
    }
    
    // 狀態欄位
    if (col === '狀態') {
        if (value === '刪除') {
            return `<span class="text-red">${value}</span>`;
        } else if (value === '新增') {
            return `<span class="text-blue">${value}</span>`;
        }
    }
    
    // 連結處理
    if (col.includes('link') && value && value.toString().startsWith('http')) {
        return `<a href="${value}" target="_blank" class="table-link">
                    <i class="fas fa-external-link-alt"></i> 查看
                </a>`;
    }
    
    // 路徑處理
    if (col.includes('path') || col.includes('folder')) {
        return `<span style="font-family: monospace; font-size: 0.875rem;">${value}</span>`;
    }
    
    return value;
}

// 切換比對頁籤
function switchCompareTab(sheetName, clickedBtn) {
    const modal = document.getElementById('compareDetailsModal');
    
    // 更新頁籤按鈕狀態
    modal.querySelectorAll('.modal-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    clickedBtn.classList.add('active');
    
    // 更新筆數顯示
    const count = clickedBtn.getAttribute('data-count') || '0';
    const modalCount = document.getElementById('modalRecordCount');
    if (modalCount) {
        modalCount.textContent = `共 ${count} 筆資料`;
    }
    
    // 切換內容
    modal.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });
    
    const targetContent = modal.querySelector(`#tab-${sheetName}`);
    if (targetContent) {
        targetContent.classList.add('active');
        targetContent.style.display = 'block';
    }
}

// 搜尋比對內容
function searchCompareContent() {
    const searchInput = document.getElementById('compare-search-input');
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const tbody = document.querySelector('.modal-table tbody');
    const resultCount = document.getElementById('compareSearchCount');
    
    if (tbody) {
        searchTableContent(tbody, searchTerm, resultCount);
    }
}

// 清除比對搜尋
function clearCompareSearch() {
    const searchInput = document.getElementById('compare-search-input');
    if (searchInput) {
        searchInput.value = '';
        searchCompareContent();
    }
}

// 關閉比對模態框
function closeCompareModal() {
    const modal = document.getElementById('compareDetailsModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// 模擬比對資料（實際應從後端獲取）
function getMockCompareData(type) {
    // 這裡應該根據實際需求從後端獲取資料
    // 現在返回模擬資料作為示例
    
    if (type === 'failed') {
        return {
            pivotData: {
                'failed_modules': {
                    columns: ['SN', 'module', 'scenario', 'reason'],
                    data: [
                        { SN: 1, module: 'test_module_1.xml', scenario: 'Master vs PreMP', reason: '檔案不存在' },
                        { SN: 2, module: 'test_module_2.txt', scenario: 'PreMP vs Wave', reason: '格式錯誤' }
                    ]
                }
            },
            sheets: [{ name: 'failed_modules', title: '失敗的模組' }],
            title: '無法比對的模組',
            modalClass: 'danger'
        };
    }
    
    // 其他類型的模擬資料
    return {
        pivotData: {
            'sheet1': {
                columns: ['SN', 'module', 'path', 'status'],
                data: []
            }
        },
        sheets: [{ name: 'sheet1', title: '資料表1' }],
        title: getModalTitle(type),
        modalClass: getModalClass(type)
    };
}

// ==================== 原有功能保持不變 ====================

function showFilesList(type) {
    let files = [];
    let title = '';
    let modalClass = '';
    let icon = '';
    
    switch(type) {
        case 'downloaded':
            files = downloadedFilesList;
            title = '已下載的檔案';
            modalClass = 'success';
            icon = 'fa-check-circle';
            break;
        case 'skipped':
            files = skippedFilesList;
            title = '已跳過的檔案';
            modalClass = 'warning';  // 改為 warning（橘色）而不是 info（藍色）
            icon = 'fa-forward';
            break;
        case 'failed':
            files = failedFilesList;
            title = '下載失敗的檔案';
            modalClass = 'danger';
            icon = 'fa-times-circle';
            break;
        case 'total':
            files = [
                ...downloadedFilesList.map(f => ({...f, status: 'downloaded'})),
                ...skippedFilesList.map(f => ({...f, status: 'skipped'})),
                ...failedFilesList.map(f => ({...f, status: 'failed'}))
            ];
            title = '所有檔案';
            modalClass = 'info';
            icon = 'fa-list';
            break;
    }
    
    currentModalFiles = [...files];
    currentSortColumn = null;
    currentSortOrder = 'asc';
    
    const modal = document.getElementById('filesListModal');
    modal.className = `modal ${modalClass}`;
    
    // 生成統一風格的模態框內容
    let html = `
        <div class="modal-content modal-large">
            <div class="modal-header">
                <h3 class="modal-title">
                    <i class="fas ${icon}"></i> ${title}
                    <span class="modal-count">共 ${files.length} 筆資料</span>
                </h3>
                <button class="modal-close" onclick="closeFilesModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
    `;
    
    if (files.length > 0) {
        // 加入搜尋列
        html += `
            <div class="modal-search-bar">
                <div class="search-input-wrapper">
                    <i class="fas fa-search search-icon"></i>
                    <input type="text" 
                           class="search-input" 
                           id="modalSearchInput" 
                           placeholder="搜尋檔案名稱、路徑..."
                           onkeyup="searchModalContent()">
                </div>
                <div class="search-stats">
                    <i class="fas fa-filter"></i>
                    <span>找到 <span class="highlight-count" id="searchResultCount">${files.length}</span> 筆</span>
                </div>
                <button class="btn-clear-search" onclick="clearModalSearch()">
                    <i class="fas fa-times"></i> 清除
                </button>
            </div>
        `;
        
        // 表格容器
        html += '<div class="table-wrapper">';
        html += '<div class="table-container">';
        html += '<table class="modal-table" id="modalFilesTable">';
        
        // 表頭（支援排序）
        html += '<thead><tr>';
        html += '<th class="sortable" onclick="sortModalTable(\'index\')" style="width: 60px; text-align: center;">SN</th>';
        html += '<th class="sortable" onclick="sortModalTable(\'name\')" style="min-width: 200px">檔案名稱</th>';
        html += '<th class="sortable" onclick="sortModalTable(\'ftp_path\')" style="min-width: 350px">FTP 路徑</th>';
        html += '<th class="sortable" onclick="sortModalTable(\'path\')" style="min-width: 350px">本地路徑</th>';
        
        if (type === 'total') {
            html += '<th class="sortable" onclick="sortModalTable(\'status\')" style="width: 100px">狀態</th>';
        }
        
        if (type === 'skipped' || type === 'failed') {
            html += '<th style="min-width: 120px">原因</th>';
        }
        
        html += '<th style="width: 80px; text-align: center;">操作</th>';
        html += '</tr></thead>';
        
        html += '<tbody id="modalTableBody">';
        
        // 生成表格內容
        files.forEach((file, index) => {
            html += '<tr>';
            
            // SN
            html += `<td class="index-cell">${index + 1}</td>`;
            
            // 檔案名稱 - 特別處理失敗的情況
            if (file.name === '無檔案') {
                // 路徑存在但無檔案的情況
                html += `<td class="file-name-cell">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <i class="fas fa-folder-open" style="color: #F44336;"></i>
                                <span class="searchable" style="color: #F44336; font-style: italic;">路徑無檔案</span>
                            </div>
                         </td>`;
            } else {
                // 正常檔案
                let fileIconColor = '#2196F3';  // 預設藍色
                if (type === 'failed' || (type === 'total' && file.status === 'failed')) {
                    fileIconColor = '#F44336';  // 失敗用紅色
                } else if (type === 'skipped' || (type === 'total' && file.status === 'skipped')) {
                    fileIconColor = '#FF9800';  // 跳過用橘色
                } else if (type === 'downloaded' || (type === 'total' && file.status === 'downloaded')) {
                    fileIconColor = '#4CAF50';  // 下載成功用綠色
                }
                
                html += `<td class="file-name-cell">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <i class="fas ${getFileIcon(file.name)}" style="color: ${fileIconColor};"></i>
                                <span class="searchable">${file.name || ''}</span>
                            </div>
                         </td>`;
            }
            
            // FTP 路徑
            html += `<td class="file-path-cell searchable" title="${file.ftp_path || '-'}">
                        <span style="font-family: monospace; font-size: 0.875rem;">${file.ftp_path || '-'}</span>
                     </td>`;
            
            // 本地路徑
            const localPath = file.path || '-';
            const displayPath = localPath === '-' ? '-' : localPath;
            html += `<td class="file-path-cell searchable" title="${localPath}">
                        <span style="font-family: monospace; font-size: 0.875rem;">${displayPath}</span>
                     </td>`;
            
            // 狀態（如果是總覽）
            if (type === 'total') {
                let statusClass = '';
                let statusText = '';
                let statusIcon = '';
                
                switch(file.status) {
                    case 'downloaded':
                        statusClass = 'success';
                        statusText = '已下載';
                        statusIcon = 'fa-check';
                        break;
                    case 'skipped':
                        statusClass = 'info';
                        statusText = '已跳過';
                        statusIcon = 'fa-forward';
                        break;
                    case 'failed':
                        statusClass = 'danger';
                        statusText = '失敗';
                        statusIcon = 'fa-times';
                        break;
                }
                
                html += `<td>
                            <span class="status-badge ${statusClass}">
                                <i class="fas ${statusIcon}" style="font-size: 0.75rem; margin-right: 4px;"></i>
                                ${statusText}
                            </span>
                         </td>`;
            }
            
            // 原因（如果是跳過或失敗）
            if (type === 'skipped' || type === 'failed') {
                let reasonStyle = '';
                if (type === 'failed') {
                    reasonStyle = 'color: #F44336; font-weight: 500;';
                }
                html += `<td class="searchable" style="${reasonStyle}">${file.reason || '-'}</td>`;
            }
            
            // 操作
            html += '<td class="action-cell">';
            
            // 只有成功下載的檔案才能預覽（排除「無檔案」的情況）
            if (file.name !== '無檔案' && 
                ((type === 'downloaded' || type === 'skipped' || (type === 'total' && file.status === 'downloaded')) && file.path)) {
                const cleanPath = file.path.replace(/\\/g, '/');
                html += `<button class="btn-icon" onclick="previewFileFromList('${cleanPath}')" title="預覽">
                            <i class="fas fa-eye"></i>
                         </button>`;
            } else {
                // 失敗的檔案不提供預覽
                html += `<span style="color: #CCC;">-</span>`;
            }
            
            html += '</td>';
            html += '</tr>';
        });
        
        html += '</tbody>';
        html += '</table>';
        html += '</div></div>';
        
        // 表格底部統計 - 修正這裡的錯誤
        html += `
            <div class="table-footer">
                <div class="table-footer-stats">
                    <div class="footer-stat">
                        <i class="fas fa-chart-bar"></i>
                        <span>共 <span class="footer-stat-value">${files.length}</span> `;
        
        // 檢查是否有「無檔案」的項目來決定用詞
        const hasNoFileItem = files.some(f => f.name === '無檔案');
        if (hasNoFileItem && files.length === 1) {
            html += '個路徑';
        } else if (hasNoFileItem) {
            html += '個項目';
        } else {
            html += '個檔案';
        }
        
        html += `</span>
                    </div>`;
        
        // 如果是總覽，顯示各類別的數量
        if (type === 'total' && files.length > 0) {
            const downloadedCount = files.filter(f => f.status === 'downloaded').length;
            const skippedCount = files.filter(f => f.status === 'skipped').length;
            const failedCount = files.filter(f => f.status === 'failed').length;
            
            html += `
                <div class="footer-stat">
                    <span style="color: #4CAF50;">
                        <i class="fas fa-check-circle"></i> ${downloadedCount} 已下載
                    </span>
                </div>
                <div class="footer-stat">
                    <span style="color: #FF9800;">
                        <i class="fas fa-forward"></i> ${skippedCount} 已跳過
                    </span>
                </div>
                <div class="footer-stat">
                    <span style="color: #F44336;">
                        <i class="fas fa-times-circle"></i> ${failedCount} 失敗
                    </span>
                </div>
            `;
        }
        
        html += `
                </div>
            </div>
        `;
    } else {
        // 沒有檔案的情況
        html += `
            <div class="empty-message">
                <i class="fas fa-inbox"></i>
                <p>沒有檔案</p>
            </div>
        `;
    }
    
    html += '</div></div>';
    
    modal.innerHTML = html;
    modal.classList.remove('hidden');
}

// 獲取檔案圖標（輔助函數）
function getFileIcon(fileName) {
    if (!fileName) return 'fa-file';
    
    const lowerName = fileName.toLowerCase();
    
    if (lowerName.includes('manifest.xml') || lowerName === 'manifest.xml') {
        return 'fa-file-code';
    }
    if (lowerName.includes('version.txt') || lowerName === 'version.txt') {
        return 'fa-file-lines';
    }
    if (lowerName.includes('f_version.txt') || lowerName === 'f_version.txt') {
        return 'fa-file-signature';
    }
    if (lowerName.endsWith('.xml')) {
        return 'fa-file-code';
    }
    if (lowerName.endsWith('.txt')) {
        return 'fa-file-alt';
    }
    if (lowerName.endsWith('.csv')) {
        return 'fa-file-csv';
    }
    if (lowerName.endsWith('.xlsx') || lowerName.endsWith('.xls')) {
        return 'fa-file-excel';
    }
    
    return 'fa-file';
}

// 通用的表格搜尋功能
function searchTableContent(tbody, searchTerm, resultCountElement) {
    if (!tbody) return;
    
    // 清除所有現有的高亮
    tbody.querySelectorAll('.highlight').forEach(el => {
        const parent = el.parentNode;
        if (parent) {
            parent.innerHTML = parent.textContent;
        }
    });
    
    let visibleCount = 0;
    const rows = tbody.querySelectorAll('tr');
    
    rows.forEach(row => {
        if (!row) return;
        
        let matchFound = false;
        
        if (searchTerm === '') {
            row.style.display = '';
            visibleCount++;
        } else {
            const cells = row.querySelectorAll('td');
            
            cells.forEach(cell => {
                if (!cell) return;
                
                const text = (cell.textContent || '').toLowerCase();
                if (text.includes(searchTerm)) {
                    matchFound = true;
                    highlightText(cell, searchTerm);
                }
            });
            
            row.style.display = matchFound ? '' : 'none';
            if (matchFound) visibleCount++;
        }
    });
    
    if (resultCountElement) {
        resultCountElement.textContent = visibleCount;
    }
}

// 排序表格
function sortModalTable(column) {
    const tbody = document.getElementById('modalTableBody');
    if (!tbody) return;
    
    // 切換排序順序
    if (currentSortColumn === column) {
        currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortColumn = column;
        currentSortOrder = 'asc';
    }
    
    // 獲取所有行
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // 排序
    rows.sort((a, b) => {
        let aValue, bValue;
        
        switch(column) {
            case 'index':
                aValue = parseInt(a.querySelector('.index-cell').textContent);
                bValue = parseInt(b.querySelector('.index-cell').textContent);
                break;
            case 'name':
                aValue = a.querySelector('.file-name-cell .searchable').textContent.toLowerCase();
                bValue = b.querySelector('.file-name-cell .searchable').textContent.toLowerCase();
                break;
            case 'ftp_path':
                aValue = a.querySelectorAll('.file-path-cell')[0].textContent.toLowerCase();
                bValue = b.querySelectorAll('.file-path-cell')[0].textContent.toLowerCase();
                break;
            case 'path':
                aValue = a.querySelectorAll('.file-path-cell')[1].textContent.toLowerCase();
                bValue = b.querySelectorAll('.file-path-cell')[1].textContent.toLowerCase();
                break;
            case 'status':
                const statusA = a.querySelector('.status-badge');
                const statusB = b.querySelector('.status-badge');
                aValue = statusA ? statusA.textContent : '';
                bValue = statusB ? statusB.textContent : '';
                break;
            default:
                return 0;
        }
        
        if (currentSortOrder === 'asc') {
            return aValue > bValue ? 1 : aValue < bValue ? -1 : 0;
        } else {
            return aValue < bValue ? 1 : aValue > bValue ? -1 : 0;
        }
    });
    
    // 重新排列
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
    
    // 更新排序指示器
    updateSortIndicators(column);
}

// 更新排序指示器
function updateSortIndicators(column) {
    const headers = document.querySelectorAll('.modal-table th.sortable');
    headers.forEach(header => {
        header.classList.remove('sort-asc', 'sort-desc');
    });
    
    const currentHeader = Array.from(headers).find(h => 
        h.getAttribute('onclick').includes(`'${column}'`)
    );
    
    if (currentHeader) {
        currentHeader.classList.add(currentSortOrder === 'asc' ? 'sort-asc' : 'sort-desc');
    }
}

// 清除搜尋
function clearModalSearch() {
    const searchInput = document.getElementById('modalSearchInput');
    if (searchInput) {
        searchInput.value = '';
        searchModalContent();
    }
}

// 修復搜尋模態框內容函數
function searchModalContent() {
    const searchInput = document.getElementById('modalSearchInput');
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const tbody = document.getElementById('modalTableBody');
    const resultCount = document.getElementById('searchResultCount');
    
    if (!tbody) return;
    
    // 先清除所有高亮
    tbody.querySelectorAll('.highlight').forEach(el => {
        const parent = el.parentNode;
        if (parent) {
            // 修復：檢查 textContent 是否存在
            const text = parent.textContent || parent.innerText || '';
            parent.innerHTML = text;
        }
    });
    
    let visibleCount = 0;
    const rows = tbody.querySelectorAll('tr');
    
    rows.forEach(row => {
        if (!row) return;
        
        const searchableElements = row.querySelectorAll('.searchable');
        let matchFound = false;
        
        if (searchTerm === '') {
            row.style.display = '';
            visibleCount++;
        } else {
            searchableElements.forEach(element => {
                if (!element) return;
                
                // 修復：安全地獲取文字內容
                const text = (element.textContent || element.innerText || '').toLowerCase();
                if (text.includes(searchTerm)) {
                    matchFound = true;
                    // 高亮匹配的文字
                    highlightText(element, searchTerm);
                }
            });
            
            row.style.display = matchFound ? '' : 'none';
            if (matchFound) visibleCount++;
        }
    });
    
    // 更新結果數量
    if (resultCount) {
        resultCount.textContent = visibleCount;
    }
}

// 修復高亮文字函數
function highlightText(element, searchTerm) {
    if (!element || !searchTerm) return;
    
    const text = element.textContent || element.innerText || '';
    if (!text) return;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    const highlightedText = text.replace(regex, '<span class="highlight">$1</span>');
    element.innerHTML = highlightedText;
}

// 定義 previewFileFromList 函數
function previewFileFromList(path) {
    // 記錄是從檔案列表開啟預覽
    previewSource = 'filesList';
    
    // 隱藏檔案列表（不是關閉）
    const filesModal = document.getElementById('filesListModal');
    if (filesModal) {
        filesModal.style.display = 'none';
    }
    
    // 開啟預覽
    setTimeout(() => {
        previewFile(path);
    }, 100);
}

// 關閉檔案列表模態框
function closeFilesModal() {
    const modal = document.getElementById('filesListModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// ... 其餘原有的函數保持不變 ...
// [所有其他函數如 initializeTabs, handleLocalFiles, displayLocalFiles 等都保持原樣]

// 初始化標籤切換
function initializeTabs() {
    // 設定預設選中的標籤
    const defaultSource = 'local';
    selectedSource = defaultSource;
    
    // 確保正確的選項卡片和內容面板顯示
    document.querySelectorAll('.source-card').forEach((card, index) => {
        if (index === 0) { // 第一個是 local
            card.classList.add('active');
        } else {
            card.classList.remove('active');
        }
    });
    
    // 確保只有本地面板顯示
    document.querySelectorAll('.content-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    const localPanel = document.getElementById('local-panel');
    if (localPanel) {
        localPanel.classList.add('active');
    }
    
    // 重置伺服器載入狀態
    serverFilesLoaded = false;
}

// 簡化的切換標籤函數
function switchTab(tab, buttonElement) {
    console.log('Switching to tab:', tab);
    
    selectedSource = tab;
    
    // 更新按鈕狀態
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    if (buttonElement) {
        buttonElement.classList.add('active');
    }
    
    // 切換內容顯示
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });
    
    const targetTab = document.getElementById(`${tab}-tab`);
    if (targetTab) {
        targetTab.classList.add('active');
        targetTab.style.display = 'block';
    }
    
    // 如果是伺服器標籤且第一次載入
    if (tab === 'server' && !serverFilesLoaded) {
        // 初始化路徑輸入
        setTimeout(() => {
            initializePathInput();
            // 自動載入預設路徑的檔案
            loadServerFiles(currentServerPath);
            serverFilesLoaded = true;
        }, 100);
    }
    
    // 更新選擇的檔案
    if (tab === 'local') {
        selectedFiles = localSelectedFiles;
    } else {
        selectedFiles = serverSelectedFiles;
    }
    
    updateSelectedHint();
    updateDownloadButton();
}
// 簡化的切換標籤函數
function switchTab(tab, buttonElement) {
    console.log('Switching to tab:', tab);
    
    selectedSource = tab;
    
    // 更新按鈕狀態
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    if (buttonElement) {
        buttonElement.classList.add('active');
    }
    
    // 切換內容顯示
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });
    
    const targetTab = document.getElementById(`${tab}-tab`);
    if (targetTab) {
        targetTab.classList.add('active');
        targetTab.style.display = 'block';
    }
    
    // 如果是伺服器標籤且第一次載入
    if (tab === 'server' && !serverFilesLoaded) {
        // 初始化路徑輸入
        setTimeout(() => {
            initializePathInput();
            // 自動載入預設路徑的檔案
            loadServerFiles(currentServerPath);
            serverFilesLoaded = true;
        }, 100);
    }
    
    // 更新選擇的檔案
    if (tab === 'local') {
        selectedFiles = localSelectedFiles;
    } else {
        selectedFiles = serverSelectedFiles;
    }
    
    updateSelectedHint();
    updateDownloadButton();
}

// 初始化上傳區域
function initializeUploadAreas() {
    // 本地 Excel 上傳
    const localArea = document.getElementById('localUploadArea');
    const localInput = document.getElementById('localFileInput');
    
    setupDragDrop(localArea, handleLocalFiles);
    localInput.addEventListener('change', (e) => {
        handleLocalFiles(Array.from(e.target.files));
    });
}

// 設定拖放功能
function setupDragDrop(element, handler) {
    element.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        element.classList.add('dragging');
    });
    
    element.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        element.classList.remove('dragging');
    });
    
    element.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        element.classList.remove('dragging');
        
        const files = Array.from(e.dataTransfer.files);
        handler(files);
    });
}

// 處理本地檔案 - 增強版（記錄Excel資訊）
function handleLocalFiles(files) {
    const supportedFiles = files.filter(f => 
        f.name.endsWith('.xlsx') || 
        f.name.endsWith('.xls') || 
        f.name.endsWith('.csv')
    );
    
    if (supportedFiles.length === 0) {
        utils.showNotification('請選擇 Excel (.xlsx, .xls) 或 CSV (.csv) 檔案', 'error');
        return;
    }
    
    localSelectedFiles = supportedFiles;
    selectedFiles = supportedFiles;
    
    // 記錄 Excel 資訊
    if (supportedFiles.length > 0) {
        uploadedExcelInfo = {
            file: supportedFiles[0],
            originalName: supportedFiles[0].name
        };
        
        // 檢查 Excel 欄位（如果需要）
        checkExcelColumns(supportedFiles[0]);
    }
    
    displayLocalFiles();
    updateSelectedHint();
    updateDownloadButton();
}

// 檢查 Excel 欄位（可選）
async function checkExcelColumns(file) {
    try {
        // 上傳檔案並檢查欄位
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // 儲存 Excel 元資料
            if (result.excel_metadata) {
                uploadedExcelInfo = {
                    ...uploadedExcelInfo,
                    filepath: result.filepath,
                    metadata: result.excel_metadata
                };
                
                // 顯示檢查結果
                if (result.excel_metadata.has_dual_sftp_columns) {
                    console.log('✅ 檢測到雙 SFTP 欄位');
                    console.log('RootFolder:', result.excel_metadata.root_folder);
                    
                    // 決定將改名為什麼
                    let newName = getNewExcelName(result.excel_metadata.root_folder);
                    if (newName) {
                        utils.showNotification(
                            `Excel 檔案將在下載完成後改名為: ${newName}`, 
                            'info'
                        );
                    }
                }
            }
        }
    } catch (error) {
        console.error('檢查 Excel 欄位失敗:', error);
    }
}

// 根據 RootFolder 決定新檔名
function getNewExcelName(rootFolder) {
    if (!rootFolder) return null;
    
    const rootFolderStr = String(rootFolder).trim();
    
    switch(rootFolderStr) {
        case 'DailyBuild':
            return 'DailyBuild_mapping.xlsx';
        case '/DailyBuild/PrebuildFW':
        case 'PrebuildFW':
            return 'PrebuildFW_mapping.xlsx';
        default:
            return null;
    }
}

// 在下載完成時處理 Excel 檔案
async function handleDownloadComplete(taskId, results) {
    // 檢查是否需要處理 Excel 檔案
    if (uploadedExcelInfo && uploadedExcelInfo.metadata) {
        const metadata = uploadedExcelInfo.metadata;
        
        if (metadata.has_dual_sftp_columns && metadata.root_folder) {
            const newName = getNewExcelName(metadata.root_folder);
            
            if (newName) {
                try {
                    // 呼叫後端 API 複製和改名 Excel 檔案
                    const response = await fetch('/api/copy-excel-to-results', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            task_id: taskId,
                            original_filepath: uploadedExcelInfo.filepath,
                            new_filename: newName
                        })
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        
                        // 顯示成功訊息
                        addLog(`Excel 檔案已另存為: ${newName}`, 'success');
                        utils.showNotification(
                            `Excel 檔案已成功改名為: ${newName}`, 
                            'success'
                        );
                        
                        // 更新結果顯示
                        if (results) {
                            results.excel_renamed = true;
                            results.excel_new_name = newName;
                        }
                    }
                } catch (error) {
                    console.error('處理 Excel 檔案失敗:', error);
                    addLog(`處理 Excel 檔案失敗: ${error.message}`, 'warning');
                }
            }
        }
    }
}

// 使用統一格式顯示本地檔案
function displayLocalFiles() {
    const listEl = document.getElementById('localFileList');
    
    if (!listEl) return;
    
    if (localSelectedFiles.length === 0) {
        listEl.innerHTML = '';
        return;
    }
    
    let html = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h4 class="file-list-title">
                    <i class="fas fa-check-circle"></i>
                    已選擇的檔案
                </h4>
                <span class="file-count-badge">${localSelectedFiles.length}</span>
            </div>
            <div class="file-items">
    `;
    
    localSelectedFiles.forEach((file, index) => {
        const fileSize = utils.formatFileSize(file.size);
        
        // 根據檔案類型決定圖標和顯示的類型文字
        let fileIcon = 'fa-file-excel';
        let fileType = 'Excel 檔案';
        
        if (file.name.endsWith('.csv')) {
            fileIcon = 'fa-file-csv';
            fileType = 'CSV 檔案';
        } else if (file.name.endsWith('.xls')) {
            fileType = 'Excel 97-2003';
        }
        
        html += `
            <div class="file-item-card">
                <div class="file-icon-wrapper">
                    <i class="fas ${fileIcon}"></i>
                </div>
                <div class="file-details">
                    <div class="file-name" title="${file.name}">${file.name}</div>
                    <div class="file-meta">
                        <span class="file-size">${fileSize}</span>
                        <span class="file-type">${fileType}</span>
                    </div>
                </div>
                <button class="btn-remove-file" onclick="removeFile(${index})" title="移除檔案">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
    });
    
    html += '</div></div>';
    
    listEl.innerHTML = html;
}

// 移除檔案
function removeFile(index) {
    localSelectedFiles.splice(index, 1);
    selectedFiles = localSelectedFiles;
    displayLocalFiles();
    updateSelectedHint();
    updateDownloadButton();
}

// 初始化路徑輸入功能 - 新增
function initializePathInput() {
    const pathInput = document.getElementById('serverPathInput');
    if (!pathInput) return;
    
    // 設定預設值
    pathInput.value = currentServerPath;
    
    // 監聽輸入事件
    pathInput.addEventListener('input', (e) => {
        clearTimeout(pathInputTimer);
        pathInputTimer = setTimeout(() => {
            showPathSuggestions(e.target.value);
        }, 300);
    });
    
    // 監聽按鍵事件
    pathInput.addEventListener('keydown', (e) => {
        const suggestions = document.getElementById('pathSuggestions');
        const items = suggestions.querySelectorAll('.suggestion-item');
        const selected = suggestions.querySelector('.suggestion-item.selected');
        let selectedIndex = -1;
        
        if (selected) {
            selectedIndex = Array.from(items).indexOf(selected);
        }
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (selectedIndex < items.length - 1) {
                selectedIndex++;
                updateSelectedSuggestion(items, selectedIndex);
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (selectedIndex > 0) {
                selectedIndex--;
                updateSelectedSuggestion(items, selectedIndex);
            }
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (selected) {
                selectSuggestion(selected.dataset.path);
            } else {
                goToPath();
            }
        } else if (e.key === 'Escape') {
            hideSuggestions();
        }
    });
    
    // 點擊外部時隱藏建議
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.path-input-container')) {
            hideSuggestions();
        }
    });
}

// 顯示路徑建議 - 新增
async function showPathSuggestions(inputValue) {
    const suggestions = document.getElementById('pathSuggestions');
    if (!suggestions) return;
    
    // 清空現有建議
    suggestions.innerHTML = '';
    
    if (!inputValue) {
        hideSuggestions();
        return;
    }
    
    try {
        // 從後端獲取建議
        const response = await utils.apiRequest(`/api/path-suggestions?path=${encodeURIComponent(inputValue)}`);
        const { directories, files } = response;
        
        if (directories.length === 0 && files.length === 0) {
            suggestions.innerHTML = '<div class="suggestion-item disabled">沒有找到匹配的路徑</div>';
        } else {
            // 顯示目錄
            directories.forEach(dir => {
                const item = createSuggestionItem(dir.path, dir.name, 'folder');
                suggestions.appendChild(item);
            });
            
            // 顯示 Excel 和 CSV 檔案
            files.filter(f => 
                f.name.endsWith('.xlsx') || 
                f.name.endsWith('.xls') || 
                f.name.endsWith('.csv')
            ).forEach(file => {
                const item = createSuggestionItem(file.path, file.name, 'file');
                suggestions.appendChild(item);
            });
        }
        
        suggestions.classList.add('show');
        
    } catch (error) {
        // 如果後端沒有實現，使用靜態建議
        showStaticSuggestions(inputValue);
    }
}

// 顯示靜態建議 - 新增
function showStaticSuggestions(inputValue) {
    const suggestions = document.getElementById('pathSuggestions');
    
    // 從 config.py 定義的常用路徑
    const commonPaths = [
        '/home/vince_lin/ai/preMP',
        '/home/vince_lin/ai/R306_ShareFolder',
        '/home/vince_lin/ai/R306_ShareFolder/nightrun_log',
        '/home/vince_lin/ai/R306_ShareFolder/nightrun_log/Demo_stress_Test_log',
        '/home/vince_lin/ai/DailyBuild',
        '/home/vince_lin/ai/DailyBuild/Merlin7',
        '/home/vince_lin/ai/PrebuildFW'
    ];
    
    // 過濾匹配的路徑
    const matches = commonPaths.filter(path => 
        path.toLowerCase().includes(inputValue.toLowerCase())
    );
    
    if (matches.length === 0) {
        suggestions.innerHTML = '<div class="suggestion-item disabled">沒有找到匹配的路徑</div>';
    } else {
        matches.forEach(path => {
            const name = path.split('/').pop() || path;
            const item = createSuggestionItem(path, name, 'folder');
            suggestions.appendChild(item);
        });
    }
    
    suggestions.classList.add('show');
}

// 建立建議項目 - 新增
function createSuggestionItem(path, name, type) {
    const div = document.createElement('div');
    div.className = 'suggestion-item';
    div.dataset.path = path;
    div.onclick = () => selectSuggestion(path);
    
    let icon = 'fa-folder';
    let typeText = '資料夾';
    
    if (type === 'file') {
        if (name.endsWith('.csv')) {
            icon = 'fa-file-csv';
            typeText = 'CSV 檔案';
        } else if (name.endsWith('.xls')) {
            icon = 'fa-file-excel';
            typeText = 'Excel 97-2003';
        } else {
            icon = 'fa-file-excel';
            typeText = 'Excel 檔案';
        }
    }
    
    div.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${path}</span>
        <span class="suggestion-type">${typeText}</span>
    `;
    
    return div;
}

// 更新選中的建議 - 新增
function updateSelectedSuggestion(items, index) {
    items.forEach((item, i) => {
        if (i === index) {
            item.classList.add('selected');
            // 確保選中項目在視野內
            item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else {
            item.classList.remove('selected');
        }
    });
}

// 選擇建議 - 新增
function selectSuggestion(path) {
    const pathInput = document.getElementById('serverPathInput');
    pathInput.value = path;
    hideSuggestions();
    
    // 如果是資料夾，導航到該路徑
    goToPath();
}

// 隱藏建議 - 新增
function hideSuggestions() {
    const suggestions = document.getElementById('pathSuggestions');
    if (suggestions) {
        suggestions.classList.remove('show');
    }
}

// 前往指定路徑 - 新增
function goToPath() {
    const pathInput = document.getElementById('serverPathInput');
    const path = pathInput.value.trim();
    
    if (path) {
        currentServerPath = path;
        loadServerFiles(path);
    }
}

// 確保 loadServerFiles 函數正確
async function loadServerFiles(path) {
    const browser = document.getElementById('serverBrowser');
    
    if (!browser) {
        console.error('Server browser element not found');
        return;
    }
    
    // 顯示載入中
    browser.innerHTML = `
        <div class="loading">
            <i class="fas fa-spinner fa-spin"></i>
            <span> 載入中...</span>
        </div>
    `;
    
    try {
        // 模擬載入（如果 API 還沒準備好）
        // 實際使用時應該調用真實的 API
        const response = await utils.apiRequest(`/api/browse-server?path=${encodeURIComponent(path)}`);
        currentServerPath = path;
        displayServerFiles(response);
        
        // 更新路徑輸入框
        const pathInput = document.getElementById('serverPathInput');
        if (pathInput) {
            pathInput.value = path;
        }
    } catch (error) {
        console.error('Error loading files:', error);
        
        // 顯示錯誤或模擬資料
        browser.innerHTML = `
            <div class="file-grid">
                <div class="file-item folder" onclick="navigateTo('/home/vince_lin/ai/preMP/test')">
                    <i class="fas fa-folder"></i>
                    <span class="file-name">test</span>
                </div>
                <div class="file-item file">
                    <i class="fas fa-file-excel"></i>
                    <span class="file-name">sample.xlsx</span>
                    <span class="file-size">23.5 KB</span>
                </div>
            </div>
        `;
    }
}

// 顯示伺服器檔案
function displayServerFiles(data) {
    const browser = document.getElementById('serverBrowser');
    if (!browser) return;
    
    const { files = [], folders = [] } = data;
    
    let html = '<div class="file-grid">';
    
    // 添加返回上層目錄項（如果不是根目錄）
    if (currentServerPath !== '/' && currentServerPath !== '') {
        html += `
            <div class="file-item folder" onclick="navigateToParent()">
                <i class="fas fa-level-up-alt"></i>
                <span class="file-name">..</span>
            </div>
        `;
    }
    
    // 顯示資料夾
    folders.forEach(folder => {
        html += `
            <div class="file-item folder" onclick="navigateTo('${folder.path}')">
                <i class="fas fa-folder"></i>
                <span class="file-name">${folder.name}</span>
            </div>
        `;
    });
    
    // 顯示 Excel 和 CSV 檔案
    files.filter(f => 
        f.name.endsWith('.xlsx') || 
        f.name.endsWith('.xls') || 
        f.name.endsWith('.csv')
    ).forEach(file => {
        const isSelected = serverSelectedFiles.some(f => f.path === file.path);
        
        // 根據檔案類型決定圖標
        let fileIcon = 'fa-file-excel';
        if (file.name.endsWith('.csv')) {
            fileIcon = 'fa-file-csv';
        }
        
        html += `
            <div class="file-item file ${isSelected ? 'selected' : ''}" 
                 onclick="toggleServerFile('${file.path}', '${file.name}', ${file.size})">
                <i class="fas ${fileIcon}"></i>
                <span class="file-name">${file.name}</span>
                <span class="file-size">${utils.formatFileSize(file.size)}</span>
                ${isSelected ? '<div class="check-icon"></div>' : ''}
            </div>
        `;
    });
    
    html += '</div>';
    browser.innerHTML = html;
}

// 更新路徑麵包屑
function updateBreadcrumb(path) {
    const breadcrumb = document.getElementById('pathBreadcrumb');
    const parts = path.split('/').filter(p => p);
    
    let html = `
        <span class="breadcrumb-item" onclick="navigateTo('/')">
            <i class="fas fa-home"></i>
        </span>
    `;
    
    let currentPath = '';
    parts.forEach((part, index) => {
        currentPath += '/' + part;
        html += `
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-item" onclick="navigateTo('${currentPath}')">
                ${part}
            </span>
        `;
    });
    
    breadcrumb.innerHTML = html;
}

// 導航到資料夾
function navigateTo(path) {
    loadServerFiles(path);
}

// 導航到上層目錄
function navigateToParent() {
    const parentPath = currentServerPath.substring(0, currentServerPath.lastIndexOf('/')) || '/';
    loadServerFiles(parentPath);
}

// 切換伺服器檔案選擇
function toggleServerFile(path, name, size) {
    const index = serverSelectedFiles.findIndex(f => f.path === path);
    
    if (index === -1) {
        serverSelectedFiles.push({ path, name, size, type: 'server' });
    } else {
        serverSelectedFiles.splice(index, 1);
    }
    
    // 如果在伺服器標籤，更新當前選擇
    if (selectedSource === 'server') {
        selectedFiles = serverSelectedFiles;
    }
    
    displayServerFiles({ files: [], folders: [] }); // 重新渲染以更新選中狀態
    loadServerFiles(currentServerPath); // 重新載入當前目錄
    displaySelectedServerFiles();
    updateSelectedHint();
    updateDownloadButton();
}

// 使用統一格式顯示已選擇的伺服器檔案
function displaySelectedServerFiles() {
    const container = document.getElementById('serverSelectedFiles');
    if (!container) return;
    
    if (serverSelectedFiles.length === 0) {
        container.innerHTML = '';
        return;
    }
    
    // 使用與本地檔案完全相同的結構
    let html = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h4 class="file-list-title">
                    <i class="fas fa-check-circle"></i>
                    已選擇的檔案
                </h4>
                <span class="file-count-badge">${serverSelectedFiles.length}</span>
            </div>
            <div class="file-items">
    `;
    
    serverSelectedFiles.forEach((file, index) => {
        const fileSize = utils.formatFileSize(file.size);
        // 從路徑中提取資料夾名稱
        const folderPath = file.path.substring(0, file.path.lastIndexOf('/'));
        const folderName = folderPath.split('/').pop() || folderPath;
        
        // 根據檔案類型決定圖標和顯示的類型文字
        let fileIcon = 'fa-file-excel';
        let fileType = 'Excel 檔案';
        
        if (file.name.endsWith('.csv')) {
            fileIcon = 'fa-file-csv';
            fileType = 'CSV 檔案';
        } else if (file.name.endsWith('.xls')) {
            fileType = 'Excel 97-2003';
        }
        
        html += `
            <div class="file-item-card">
                <div class="file-icon-wrapper">
                    <i class="fas ${fileIcon}"></i>
                </div>
                <div class="file-details">
                    <div class="file-name" title="${file.name}">${file.name}</div>
                    <div class="file-meta">
                        <span class="file-size">${fileSize}</span>
                        <span class="file-type">${fileType}</span>
                        <span class="file-path" title="${folderPath}">
                            <i class="fas fa-folder-open"></i> ${folderName}
                        </span>
                    </div>
                </div>
                <button class="btn-remove-file" onclick="removeServerFile(${index})" title="移除檔案">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
    });
    
    html += '</div></div>';
    
    container.innerHTML = html;
}

// 移除伺服器檔案
function removeServerFile(index) {
    serverSelectedFiles.splice(index, 1);
    
    // 如果在伺服器標籤，更新當前選擇
    if (selectedSource === 'server') {
        selectedFiles = serverSelectedFiles;
    }
    
    loadServerFiles(currentServerPath);
    displaySelectedServerFiles();
    updateSelectedHint();
    updateDownloadButton();
}

// 重新整理伺服器檔案
function refreshServerFiles() {
    loadServerFiles(currentServerPath);
}

// 初始化設定開關
function initializeConfigToggles() {
    const useDefault = document.getElementById('useDefaultConfig');
    const customConfig = document.getElementById('customSftpConfig');
    
    if (useDefault && customConfig) {
        // 初始狀態處理
        toggleSftpConfig(useDefault.checked);
        
        useDefault.addEventListener('change', (e) => {
            toggleSftpConfig(e.target.checked);
        });
    }
    
    // 初始化深度控制顯示
    toggleDepthControl();
}

// 切換 SFTP 設定狀態
function toggleSftpConfig(useDefault) {
    const customConfig = document.getElementById('customSftpConfig');
    const testButton = customConfig.querySelector('.btn-test');
    
    if (!customConfig) return;
    
    if (useDefault) {
        customConfig.classList.add('disabled');
        // 禁用所有輸入框
        customConfig.querySelectorAll('input').forEach(element => {
            element.disabled = true;
        });
        // 禁用測試按鈕
        if (testButton) {
            testButton.disabled = true;
        }
    } else {
        customConfig.classList.remove('disabled');
        // 啟用所有輸入框
        customConfig.querySelectorAll('input').forEach(element => {
            element.disabled = false;
        });
        // 啟用測試按鈕
        if (testButton) {
            testButton.disabled = false;
        }
    }
}

// 切換深度控制顯示
function toggleDepthControl() {
    const recursiveSearch = document.getElementById('recursiveSearch');
    const depthOption = document.getElementById('searchDepthOption');
    
    if (recursiveSearch && depthOption) {
        if (recursiveSearch.checked) {
            depthOption.style.display = 'flex';
        } else {
            depthOption.style.display = 'none';
        }
    }
}

// 更新已選擇提示
function updateSelectedHint() {
    // 可以顯示選擇提示
}

// 更新下載按鈕狀態
function updateDownloadButton() {
    const btn = document.getElementById('downloadBtn');
    const currentFiles = selectedSource === 'local' ? localSelectedFiles : serverSelectedFiles;
    btn.disabled = currentFiles.length === 0;
}

// 調整搜尋深度
function adjustDepth(delta) {
    const input = document.getElementById('searchDepth');
    
    if (!input) return;
    
    let value = parseInt(input.value) + delta;
    value = Math.max(1, Math.min(10, value));
    
    input.value = value;
}

// 測試連線
async function testSftpConnection() {
    const config = getSftpConfig();
    const statusEl = document.getElementById('connectionStatus');
    
    statusEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 測試中...';
    statusEl.className = 'connection-status testing ml-3';
    
    try {
        const response = await utils.apiRequest('/api/test-connection', {
            method: 'POST',
            body: JSON.stringify(config)
        });
        
        if (response.success) {
            statusEl.innerHTML = '<i class="fas fa-check"></i> 連線成功';
            statusEl.className = 'connection-status success ml-3';
        } else {
            throw new Error(response.message || '連線失敗');
        }
    } catch (error) {
        statusEl.innerHTML = '<i class="fas fa-times"></i> 連線失敗';
        statusEl.className = 'connection-status error ml-3';
        utils.showNotification(error.message || '連線測試失敗', 'error');
    }
}

// 修正取得 SFTP 設定函數
function getSftpConfig() {
    const config = {};
    
    const useDefault = document.getElementById('useDefaultConfig');
    if (!useDefault || !useDefault.checked) {
        // 使用自訂設定
        config.host = document.getElementById('sftpHost').value;
        config.port = parseInt(document.getElementById('sftpPort').value) || 22;
        config.username = document.getElementById('sftpUsername').value;
        config.password = document.getElementById('sftpPassword').value;
        
        // 驗證必要欄位
        if (!config.host || !config.username || !config.password) {
            throw new Error('請填寫完整的 SFTP 設定');
        }
    }
    // 如果使用預設設定，返回空物件（後端會使用 config.py 的設定）
    
    return config;
}

// 開始下載 - 增強版（處理Excel改名）
async function startDownload() {
    const currentFiles = selectedSource === 'local' ? localSelectedFiles : serverSelectedFiles;
    
    if (currentFiles.length === 0) {
        utils.showNotification('請先選擇檔案', 'error');
        return;
    }
    
    try {
        const sftpConfig = getSftpConfig();
        
        document.getElementById('downloadForm').classList.add('hidden');
        document.getElementById('downloadProgress').classList.remove('hidden');
        
        clearLog();
        
        let requestData = {
            sftp_config: sftpConfig,
            options: {
                skip_existing: document.getElementById('skipExisting').checked,
                recursive_search: document.getElementById('recursiveSearch').checked,
                search_depth: parseInt(document.getElementById('searchDepth').value),
                enable_resume: document.getElementById('enableResume').checked
            }
        };
        
        // 處理檔案來源
        if (selectedSource === 'local') {
            const file = localSelectedFiles[0];
            const fileType = file.name.endsWith('.csv') ? 'CSV' : 'Excel';
            addLog(`正在上傳 ${fileType} 檔案...`, 'info');
            
            try {
                // 上傳檔案並檢查欄位
                const uploadResult = await uploadFileAndCheckColumns(file);
                
                if (!uploadResult.filepath) {
                    throw new Error('上傳檔案失敗：返回數據格式錯誤');
                }
                
                requestData.excel_file = uploadResult.filepath;
                
                // 如果有特定欄位，加入請求中
                if (uploadResult.hasDualColumns) {
                    requestData.excel_metadata = {
                        has_dual_columns: true,
                        original_name: file.name,
                        root_folder: uploadResult.rootFolder
                    };
                } else if (uploadResult.hasSpecialColumns) {
                    requestData.excel_metadata = {
                        has_sftp_columns: true,
                        original_name: file.name,
                        root_folder: uploadResult.rootFolder
                    };
                }
                
                addLog(`檔案 ${file.name} 上傳成功`, 'success');
                
            } catch (error) {
                addLog(`上傳檔案失敗: ${error.message}`, 'error');
                utils.showNotification('上傳檔案失敗', 'error');
                resetDownloadForm();
                return;
            }
        } else {
            const validFile = serverSelectedFiles.find(f => 
                f.name.endsWith('.xlsx') || 
                f.name.endsWith('.xls') || 
                f.name.endsWith('.csv')
            );
            
            if (!validFile) {
                utils.showNotification('請選擇一個 Excel 或 CSV 檔案', 'error');
                resetDownloadForm();
                return;
            }
            
            requestData.excel_file = validFile.path;
            
            const fileType = validFile.name.endsWith('.csv') ? 'CSV' : 'Excel';
            addLog(`使用伺服器 ${fileType} 檔案: ${validFile.name}`, 'info');
        }
        
        addLog('正在初始化下載任務...', 'info');
        
        const response = await utils.apiRequest('/api/download', {
            method: 'POST',
            body: JSON.stringify(requestData)
        });
        
        if (!response.task_id) {
            throw new Error('無法建立下載任務');
        }
        
        downloadTaskId = response.task_id;
        
        addLog(`任務 ID: ${downloadTaskId}`, 'info');
        addLog('開始下載檔案...', 'downloading');
        
        if (window.socket && socket.connected) {
            socket.emit('join_task', { task_id: downloadTaskId });
        }
        
        document.addEventListener('task-progress', handleDownloadProgress);
        pollDownloadStatus();
        
    } catch (error) {
        console.error('Download error:', error);
        addLog(`下載失敗: ${error.message}`, 'error');
        utils.showNotification(error.message || '下載失敗', 'error');
        resetDownloadForm();
    }
}

// 上傳檔案並檢查欄位
async function uploadFileAndCheckColumns(file) {
    // 先上傳檔案
    const uploadResult = await utils.uploadFile(file);
    
    // 檢查Excel欄位
    try {
        const checkResponse = await utils.apiRequest('/api/check-excel-columns', {
            method: 'POST',
            body: JSON.stringify({
                filepath: uploadResult.filepath
            })
        });
        
        // 記錄 Excel 資訊供後續使用
        if (checkResponse.has_dual_sftp_columns) {
            uploadedExcelInfo = {
                file: file,
                originalName: file.name,
                filepath: uploadResult.filepath,
                rootFolder: checkResponse.root_folder,
                hasDualColumns: true
            };
        }
        
        return {
            filepath: uploadResult.filepath,
            hasSpecialColumns: checkResponse.has_sftp_columns || checkResponse.has_dual_sftp_columns,
            hasDualColumns: checkResponse.has_dual_sftp_columns,
            rootFolder: checkResponse.root_folder
        };
    } catch (error) {
        // 如果檢查失敗，仍然返回上傳結果
        return {
            filepath: uploadResult.filepath,
            hasSpecialColumns: false,
            hasDualColumns: false,
            rootFolder: null
        };
    }
}

// 處理下載進度
function handleDownloadProgress(event) {
    const data = event.detail;
    if (data.task_id === downloadTaskId) {
        // 確保統計資料存在且不會歸零
        if (data.stats) {
            // 保存當前統計，避免歸零
            const currentStats = {
                total: parseInt(document.getElementById('totalFiles').textContent) || 0,
                downloaded: parseInt(document.getElementById('downloadedFiles').textContent) || 0,
                skipped: parseInt(document.getElementById('skippedFiles').textContent) || 0,
                failed: parseInt(document.getElementById('failedFiles').textContent) || 0
            };
            
            // 只更新增加的值，不允許減少
            data.stats = {
                total: Math.max(data.stats.total || 0, currentStats.total),
                downloaded: Math.max(data.stats.downloaded || 0, currentStats.downloaded),
                skipped: Math.max(data.stats.skipped || 0, currentStats.skipped),
                failed: Math.max(data.stats.failed || 0, currentStats.failed)
            };
        }
        
        updateDownloadProgress(data);
    }
}

// 監聽下載進度更新
function updateDownloadProgress(data) {
    const { progress, status, message, stats, files, results } = data;
    
    // 確保進度不超過 100%
    const safeProgress = Math.min(Math.max(0, progress || 0), 100);
    
    // 更新進度條
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');

    // 驗證並修正統計
    if (stats) {
        validateStats(stats);
    }

    if (progressFill && progressText) {
        progressFill.style.width = `${safeProgress}%`;
        progressText.textContent = `${Math.round(safeProgress)}%`;
    }
    
    // 更新統計
    if (stats && typeof stats === 'object') {
        updateStats(stats);
    }
    
    // 儲存檔案列表
    if (files) {
        downloadedFilesList = files.downloaded || [];
        skippedFilesList = files.skipped || [];
        failedFilesList = files.failed || [];
    }
    
    // 添加日誌
    addLog(message, status);
    
    // 檢查是否有 Excel 改名訊息
    if (message && message.includes('Excel 檔案已另存為')) {
        // 高亮顯示 Excel 改名訊息
        const logEntry = document.querySelector('.log-entry:last-child');
        if (logEntry) {
            logEntry.style.background = '#E8F5E9';
            logEntry.style.fontWeight = 'bold';
        }
    }
    
    // 處理完成或錯誤
    if (status === 'completed') {
        const finalResults = results || {};
        if (!finalResults.files && files) {
            finalResults.files = files;
        }
        if (!finalResults.stats && stats) {
            finalResults.stats = stats;
        }
        showDownloadResults(finalResults);
    } else if (status === 'error') {
        utils.showNotification(`下載失敗：${message}`, 'error');
        resetDownloadForm();
    }
}

// 更新統計數據
function updateStats(stats) {
    if (!stats) {
        console.error('No stats data provided');
        return;
    }
    
    const elements = {
        totalFiles: stats.total || 0,
        downloadedFiles: stats.downloaded || 0,
        skippedFiles: stats.skipped || 0,
        failedFiles: stats.failed || 0
    };
    
    for (const [id, value] of Object.entries(elements)) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
            
            // 讓統計卡片可點擊
            const card = element.closest('.stat-card');
            if (card && value > 0) {
                card.style.cursor = 'pointer';
                const type = id.replace('Files', '');
                card.onclick = () => showFilesList(type);
                card.title = '點擊查看檔案列表';
            }
        }
    }
}

// 改善日誌顯示
function addLog(message, type = 'info') {
    const log = document.getElementById('downloadLog');
    if (!log) return;
    
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    
    const timestamp = new Date().toLocaleTimeString('zh-TW', { 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });
    
    const iconMap = {
        'info': 'fa-info-circle',
        'success': 'fa-check-circle',
        'warning': 'fa-exclamation-triangle',
        'error': 'fa-times-circle',
        'downloading': 'fa-download',
        'completed': 'fa-flag-checkered'
    };
    
    entry.innerHTML = `
        <span class="log-time">${timestamp}</span>
        <span class="log-icon">
            <i class="fas ${iconMap[type] || iconMap.info}"></i>
        </span>
        <span class="log-message">${message}</span>
    `;
    
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

// 清除日誌
function clearLog() {
    const log = document.getElementById('downloadLog');
    if (log) {
        log.innerHTML = '';
    }
}

// 顯示下載結果時包含 Excel 改名資訊
function showDownloadResults(results) {
    const downloadProgress = document.getElementById('downloadProgress');
    const downloadResults = document.getElementById('downloadResults');
    
    if (downloadProgress) {
        downloadProgress.classList.add('hidden');
    }
    
    if (downloadResults) {
        downloadResults.classList.remove('hidden');
    }
    
    // 處理 Excel 檔案（如果需要）
    if (downloadTaskId) {
        handleDownloadComplete(downloadTaskId, results);
    }
    
    // 確保檔案列表資料被保存
    if (results.files) {
        downloadedFilesList = results.files.downloaded || [];
        skippedFilesList = results.files.skipped || [];
        failedFilesList = results.files.failed || [];
    }
    
    // 生成摘要
    const stats = results.stats || {};
    const summary = generateResultSummary(stats);
    document.getElementById('resultSummary').innerHTML = summary;
    
    // 如果有 Excel 改名資訊，顯示在摘要中
    if (results.excel_renamed) {
        const excelInfo = document.createElement('div');
        excelInfo.className = 'excel-rename-info';
        excelInfo.innerHTML = `
            <div class="alert alert-success" style="margin-top: 20px;">
                <i class="fas fa-check-circle"></i>
                <strong>Excel 檔案已處理：</strong> 
                已將上傳的 Excel 檔案改名為 <code>${results.excel_new_name}</code> 
                並儲存到下載資料夾中
            </div>
        `;
        document.getElementById('resultSummary').appendChild(excelInfo);
    }
    
    // 生成資料夾樹
    if (results.folder_structure) {
        generateFolderTree(results.folder_structure);
    }
}

// 新增處理 Excel 檔案的複製和改名函數
async function handleExcelCopyAndRename(results) {
    // 檢查是否有需要複製的 Excel 檔案資訊
    if (!uploadedExcelInfo || !uploadedExcelInfo.hasDualColumns) {
        return;
    }
    
    try {
        // 決定新檔名
        let newFileName = '';
        const rootFolder = uploadedExcelInfo.rootFolder || results.root_folder;
        
        if (rootFolder === 'DailyBuild') {
            newFileName = 'DailyBuild_mapping.xlsx';
        } else if (rootFolder === '/DailyBuild/PrebuildFW' || rootFolder === 'PrebuildFW') {
            newFileName = 'PrebuildFW_mapping.xlsx';
        } else {
            // 預設使用原檔名
            newFileName = uploadedExcelInfo.originalName;
        }
        
        // 呼叫後端 API 複製和改名 Excel 檔案
        const copyResponse = await utils.apiRequest('/api/copy-excel-to-results', {
            method: 'POST',
            body: JSON.stringify({
                task_id: downloadTaskId,
                original_filepath: uploadedExcelInfo.filepath,
                new_filename: newFileName
            })
        });
        
        if (copyResponse.success) {
            addLog(`Excel 檔案已複製並改名為: ${newFileName}`, 'success');
            utils.showNotification(`Excel 檔案已另存為: ${newFileName}`, 'success');
        }
        
    } catch (error) {
        console.error('複製 Excel 檔案失敗:', error);
        addLog(`複製 Excel 檔案失敗: ${error.message}`, 'warning');
    }
}

// 生成結果摘要
function generateResultSummary(stats) {
    return `
        <div class="progress-stats">
            <div class="stat-card blue" onclick="showFilesList('total')" title="點擊查看所有檔案">
                <div class="stat-icon">
                    <i class="fas fa-file"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stats.total || 0}</div>
                    <div class="stat-label">總檔案數</div>
                </div>
            </div>
            
            <div class="stat-card success" onclick="showFilesList('downloaded')" title="點擊查看已下載檔案">
                <div class="stat-icon">
                    <i class="fas fa-check-circle"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stats.downloaded || 0}</div>
                    <div class="stat-label">已下載</div>
                </div>
            </div>
            
            <div class="stat-card warning" onclick="showFilesList('skipped')" title="點擊查看跳過的檔案">
                <div class="stat-icon">
                    <i class="fas fa-forward"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stats.skipped || 0}</div>
                    <div class="stat-label">已跳過</div>
                </div>
            </div>
            
            <div class="stat-card danger" onclick="showFilesList('failed')" title="點擊查看失敗的檔案">
                <div class="stat-icon">
                    <i class="fas fa-times-circle"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">${stats.failed || 0}</div>
                    <div class="stat-label">失敗</div>
                </div>
            </div>
        </div>
        
        <div class="stats-hint">
            <i class="fas fa-info-circle"></i>
            <span>提示：點擊上方統計卡片可查看詳細的檔案列表（支援搜尋和排序）</span>
        </div>
    `;
}

// 生成資料夾樹
function generateFolderTree(structure) {
    const treeContainer = document.getElementById('folderTree');
    
    if (!structure || Object.keys(structure).length === 0) {
        treeContainer.innerHTML = '<div class="empty-message">沒有檔案</div>';
        return;
    }
    
    const tree = buildTreeHTML(structure, '', '');
    treeContainer.innerHTML = tree;
}

// 建立樹狀結構 HTML
function buildTreeHTML(node, name, parentPath) {
    let html = '';
    
    if (typeof node === 'string') {
        const fileName = name;
        const filePath = node;
        
        // 根據檔案名稱決定圖標
        let fileIcon = 'fa-file';
        const lowerFileName = fileName.toLowerCase();
        
        if (lowerFileName === 'manifest.xml') {
            fileIcon = 'fa-file-code';
        } else if (lowerFileName === 'version.txt') {
            fileIcon = 'fa-file-lines';
        } else if (lowerFileName === 'f_version.txt') {
            fileIcon = 'fa-file-signature';
        } else if (lowerFileName.endsWith('.xml')) {
            fileIcon = 'fa-file-code';
        } else if (lowerFileName.endsWith('.txt')) {
            fileIcon = 'fa-file-alt';
        }
        
        html = `
            <div class="tree-node">
                <div class="tree-node-content file" data-path="${filePath}" ondblclick="previewFile('${filePath}')">
                    <i class="tree-icon tree-file fas ${fileIcon}"></i>
                    <span class="tree-name">${fileName}</span>
                    <div class="tree-actions">
                        <button class="tree-action preview" onclick="event.stopPropagation(); previewFile('${filePath}')" title="預覽">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="tree-action download" onclick="event.stopPropagation(); downloadFile('${filePath}')" title="下載">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    } else if (typeof node === 'object') {
        if (name) {
            html = `
                <div class="tree-node">
                    <div class="tree-node-content folder" onclick="toggleFolder(this)">
                        <i class="tree-icon tree-folder fas fa-folder"></i>
                        <span class="tree-name">${name}/</span>
                    </div>
                    <div class="tree-children">
            `;
        }
        
        for (const [key, value] of Object.entries(node)) {
            const currentPath = parentPath ? `${parentPath}/${name}` : name;
            html += buildTreeHTML(value, key, currentPath);
        }
        
        if (name) {
            html += '</div></div>';
        }
    }
    
    return html;
}

// 切換資料夾展開/摺疊
function toggleFolder(element) {
    const node = element.parentElement;
    const children = node.querySelector('.tree-children');
    const icon = element.querySelector('.tree-folder');
    
    if (children) {
        if (children.style.display === 'none') {
            children.style.display = 'block';
            icon.classList.remove('fa-folder');
            icon.classList.add('fa-folder-open');
        } else {
            children.style.display = 'none';
            icon.classList.remove('fa-folder-open');
            icon.classList.add('fa-folder');
        }
    }
}

// 預覽檔案
async function previewFile(path) {
    if (!previewSource) {
        previewSource = null;
    }
    
    const modal = document.getElementById('filePreviewModal');
    const content = document.getElementById('previewContent');
    const filenameText = document.getElementById('previewFilenameText');
    const filenameElement = document.getElementById('previewFilename');
    
    // 顯示檔名和設定檔案類型
    const fileName = path.split('/').pop();
    const fileExt = fileName.split('.').pop().toLowerCase();
    
    if (filenameText) {
        filenameText.textContent = fileName;
    }
    
    // 設定預覽視窗的檔案圖標
    if (filenameElement) {
        filenameElement.className = `preview-filename ${fileExt}`;
        const icon = filenameElement.querySelector('i');
        if (icon) {
            const lowerFileName = fileName.toLowerCase();
            
            if (lowerFileName === 'manifest.xml') {
                icon.className = 'fas fa-code';
            } else if (lowerFileName === 'version.txt') {
                icon.className = 'fas fa-file-alt';
            } else if (lowerFileName === 'f_version.txt') {
                icon.className = 'fas fa-file-medical';
            } else if (fileExt === 'xml') {
                icon.className = 'fas fa-code';
            } else if (fileExt === 'txt') {
                icon.className = 'fas fa-file-alt';
            } else if (fileExt === 'log') {
                icon.className = 'fas fa-file-alt';
            } else {
                icon.className = 'fas fa-file';
            }
        }
    }
    
    content.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i><span>載入中...</span></div>';
    modal.classList.remove('hidden');
    
    try {
        const response = await utils.apiRequest(`/api/preview-file?path=${encodeURIComponent(path)}`);
        
        if (response.type === 'xml' || fileExt === 'xml') {
            // XML 語法高亮 - 先 escape HTML
            let formattedContent = response.content
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/(&lt;)(\/?)([^&\s]+?)(&gt;)/g, 
                    '<span class="xml-bracket">$1</span>$2<span class="xml-tag">$3</span><span class="xml-bracket">$4</span>')
                .replace(/(\s)([a-zA-Z\-:]+)(=)("[^"]*")/g, 
                    '$1<span class="xml-attr">$2</span>$3<span class="xml-value">$4</span>');
            
            content.innerHTML = formattedContent;
            content.className = 'preview-content xml';
            
        } else if (fileName.toLowerCase().includes('version') || fileExt === 'txt') {
            // 所有文字檔案都使用淺色主題
            content.textContent = response.content;
            
            // 根據檔名設定不同的 class
            if (fileName.toLowerCase() === 'version.txt' || fileName.toLowerCase() === 'f_version.txt') {
                content.className = 'preview-content version-txt';
            } else {
                content.className = 'preview-content plain-text';
            }
        } else {
            // 純文字顯示
            content.textContent = response.content;
            content.className = 'preview-content';
        }
        
        // 重置捲軸位置
        content.scrollTop = 0;
        content.scrollLeft = 0;
        
    } catch (error) {
        content.innerHTML = `<div class="error"><i class="fas fa-exclamation-circle"></i><br>無法預覽檔案：${error.message}</div>`;
        content.className = 'preview-content';
    }
}

// 複製預覽內容
function copyPreviewContent() {
    const content = document.getElementById('previewContent');
    const copyBtn = document.querySelector('.btn-copy');
    
    if (!content) {
        console.error('找不到預覽內容元素');
        return;
    }
    
    // 獲取純文字內容
    const text = content.textContent || content.innerText || '';
    
    if (!text) {
        console.error('預覽內容為空');
        return;
    }
    
    // 創建臨時 textarea
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.cssText = 'position: fixed; left: -9999px; top: -9999px;';
    document.body.appendChild(textarea);
    
    try {
        // 選取文字
        textarea.select();
        textarea.setSelectionRange(0, textarea.value.length);
        
        // 執行複製
        const successful = document.execCommand('copy');
        
        if (successful) {
            // 成功提示
            if (copyBtn) {
                const originalHTML = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="fas fa-check"></i> 已複製';
                copyBtn.style.cssText = 'background: rgba(76, 175, 80, 0.2); border-color: #4CAF50;';
                
                setTimeout(() => {
                    copyBtn.innerHTML = originalHTML;
                    copyBtn.style.cssText = '';
                }, 2000);
            }
            
            // 顯示通知
            if (typeof window.utils !== 'undefined' && window.utils.showNotification) {
                window.utils.showNotification('內容已複製到剪貼簿', 'success');
            } else {
                console.log('內容已複製到剪貼簿');
            }
        } else {
            throw new Error('複製命令執行失敗');
        }
        
    } catch (err) {
        console.error('複製失敗:', err);
        
        // 嘗試使用 Clipboard API
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
                .then(() => {
                    if (typeof window.utils !== 'undefined' && window.utils.showNotification) {
                        window.utils.showNotification('內容已複製到剪貼簿', 'success');
                    }
                })
                .catch(err => {
                    console.error('Clipboard API 複製失敗:', err);
                    alert('複製失敗，請手動選取文字後按 Ctrl+C 複製');
                });
        } else {
            alert('複製失敗，請手動選取文字後按 Ctrl+C 複製');
        }
    } finally {
        document.body.removeChild(textarea);
    }
}

// 切換所有資料夾展開/摺疊
function toggleAllFolders() {
    const btn = document.getElementById('toggleFoldersBtn');
    const btnText = document.getElementById('toggleFoldersText');
    const btnIcon = btn.querySelector('i');
    
    // 檢查當前狀態
    const isExpanded = btnText.textContent === '摺疊全部';
    
    if (isExpanded) {
        // 摺疊全部
        collapseAllFolders();
        btnText.textContent = '展開全部';
        btnIcon.className = 'fas fa-expand-alt';
    } else {
        // 展開全部
        expandAllFolders();
        btnText.textContent = '摺疊全部';
        btnIcon.className = 'fas fa-compress-alt';
    }
}

// 展開所有資料夾
function expandAllFolders() {
    document.querySelectorAll('.tree-children').forEach(el => {
        el.style.display = 'block';
    });
    document.querySelectorAll('.tree-folder').forEach(el => {
        el.classList.remove('fa-folder');
        el.classList.add('fa-folder-open');
    });
}

// 摺疊所有資料夾
function collapseAllFolders() {
    document.querySelectorAll('.tree-children').forEach(el => {
        el.style.display = 'none';
    });
    document.querySelectorAll('.tree-folder').forEach(el => {
        el.classList.remove('fa-folder-open');
        el.classList.add('fa-folder');
    });
}

// 下載檔案
function downloadFile(path) {
    window.open(`/api/download-file?path=${encodeURIComponent(path)}`, '_blank');
}

// 關閉預覽
function closePreview() {
    const previewModal = document.getElementById('filePreviewModal');
    previewModal.classList.add('hidden');
    
    // 如果是從檔案列表開啟的，重新顯示檔案列表
    if (previewSource === 'filesList') {
        const filesModal = document.getElementById('filesListModal');
        if (filesModal) {
            filesModal.style.display = ''; // 恢復顯示
            filesModal.classList.remove('hidden');
        }
        previewSource = null; // 重置來源
    }
}

// 輪詢下載狀態
async function pollDownloadStatus() {
    if (!downloadTaskId) return;
    
    try {
        const status = await utils.apiRequest(`/api/status/${downloadTaskId}`);
        
        if (status.status !== 'not_found') {
            // 確保包含檔案列表資訊
            updateDownloadProgress(status);
            
            // 如果有檔案列表，更新全域變數
            if (status.files) {
                downloadedFilesList = status.files.downloaded || [];
                skippedFilesList = status.files.skipped || [];
                failedFilesList = status.files.failed || [];
            }
        }
        
        // 如果任務未完成，繼續輪詢
        if (status.status !== 'completed' && status.status !== 'error') {
            setTimeout(pollDownloadStatus, 1000);
        } else {
            // 移除事件監聽
            document.removeEventListener('task-progress', handleDownloadProgress);
            
            // 如果是完成狀態，確保顯示結果
            if (status.status === 'completed' && status.results) {
                showDownloadResults(status.results);
            }
        }
    } catch (error) {
        console.error('Poll status error:', error);
        addLog('無法獲取任務狀態', 'error');
    }
}

// 重置下載表單
function resetDownloadForm() {
    const downloadForm = document.querySelector('.download-form');
    const downloadProgress = document.getElementById('downloadProgress');
    const downloadResults = document.getElementById('downloadResults');
    
    if (downloadForm) {
        downloadForm.classList.remove('hidden');
    }
    
    if (downloadProgress) {
        downloadProgress.classList.add('hidden');
    }
    
    if (downloadResults) {
        downloadResults.classList.add('hidden');
    }
    
    clearLog();
    
    // 重置進度
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    if (progressFill) {
        progressFill.style.width = '0%';
    }
    
    if (progressText) {
        progressText.textContent = '0%';
    }
}

// 查看報表
function viewReport() {
    if (downloadTaskId) {
        window.location.href = `/api/download-report/${downloadTaskId}`;
    }
}

// 繼續比對
function proceedToCompare() {
    window.location.href = '/compare';
}

// 新的下載
function newDownload() {
    location.reload();
}

// 選擇檔案來源
function selectSource(source) {
    const clickedCard = event ? event.currentTarget : null;
    
    selectedSource = source;
    
    // 更新選項卡片狀態
    document.querySelectorAll('.source-card').forEach(card => {
        card.classList.remove('active');
    });
    
    if (clickedCard) {
        clickedCard.classList.add('active');
    } else {
        document.querySelectorAll('.source-card').forEach((card, index) => {
            if ((source === 'local' && index === 0) || (source === 'server' && index === 1)) {
                card.classList.add('active');
            }
        });
    }
    
    // 更新內容面板
    document.querySelectorAll('.content-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    const targetPanel = document.getElementById(`${source}-panel`);
    if (targetPanel) {
        targetPanel.classList.add('active');
        
        // 如果選擇伺服器且尚未載入內容，動態生成
        if (source === 'server' && !serverFilesLoaded) {
            targetPanel.innerHTML = `
                <div class="browser-container">
                    <div class="browser-header">
                        <div class="breadcrumb" id="pathBreadcrumb">
                            <span class="breadcrumb-item" onclick="navigateTo('/')">
                                <i class="fas fa-home"></i>
                            </span>
                        </div>
                        <button class="btn-refresh" onclick="refreshServerFiles()">
                            <i class="fas fa-sync"></i>
                        </button>
                    </div>
                    <div class="browser-content" id="serverBrowser">
                        <div class="loading">
                            <i class="fas fa-spinner fa-spin"></i>
                            <span>載入中...</span>
                        </div>
                    </div>
                </div>
                
                <div class="selected-files" id="serverSelectedFiles">
                    <!-- 顯示已選擇的伺服器檔案 -->
                </div>
            `;
            
            // 載入檔案列表
            loadServerFiles(currentServerPath);
            serverFilesLoaded = true;
        }
    }
    
    // 重置選擇
    if (source === 'local') {
        selectedFiles = [];
        displayLocalFiles();
    } else {
        selectedFiles = serverSelectedFiles;
        displaySelectedServerFiles();
    }
    
    updateSelectedHint();
    updateDownloadButton();
}

function validateStats(stats) {
    if (!stats) return;
    
    // 確保總數等於各項總和
    const calculatedTotal = (stats.downloaded || 0) + 
                          (stats.skipped || 0) + 
                          (stats.failed || 0);
    
    if (stats.total !== calculatedTotal) {
        console.warn(`統計不一致: total=${stats.total}, 計算值=${calculatedTotal}`);
        stats.total = calculatedTotal;
    }
    
    return stats;
}
