// 後台管理 JavaScript
let currentFunction = 'chip-mapping';
let selectedMappingFile = null;
let selectedPrebuildFiles = {
    master: null,
    premp: null,
    mp: null,
    mpbackup: null
};

// 改為分開儲存兩個功能的結果
let chipMappingResult = {
    data: [],
    columns: [],
    totalRows: 0
};

let prebuildMappingResult = {
    data: [],
    columns: [],
    totalRows: 0
};

// 指向當前顯示的結果
let currentResult = null;

let currentPage = 1;
let pageSize = 50;
let sortColumn = null;
let sortDirection = 'asc';
let filterText = '';
let dbVersionsCache = {}; // 快取 DB 版本資訊
let currentResultSource = null

// 在檔案開頭加入
let resultCache = {
    'chip-mapping': null,
    'prebuild-mapping': null
};

// 定義標準欄位順序
const STANDARD_COLUMNS = [
    'SN',
    'RootFolder',
    'Module',
    'DB_Type',
    'DB_Info',
    'DB_Folder',
    'DB_Version',
    'SftpPath',
    'compare_DB_Type',
    'compare_DB_Info',
    'compare_DB_Folder',
    'compare_DB_Version',
    'compare_SftpPath'
];

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initializeFileUploads();
    loadQuickPaths();
    initializeSearch();
    setupDBSelectors();
    setupQuickPathListeners();
});

// 設定 DB 選擇器
function setupDBSelectors() {
    const dbSelect = document.getElementById('dbFilter');
    const versionSelect = document.getElementById('dbVersion');
    const versionGroup = document.getElementById('dbVersionGroup');
    
    // 監聽 DB 選擇變化
    dbSelect.addEventListener('change', async (e) => {
        const selectedDB = e.target.value;
        
        if (selectedDB && selectedDB !== 'all') {
            // 顯示版本選擇器
            versionGroup.style.display = 'block';
            
            // 載入版本
            await loadDBVersions(selectedDB);
        } else {
            // 隱藏版本選擇器
            versionGroup.style.display = 'none';
            versionSelect.innerHTML = '<option value="">選擇版本...</option>';
        }
    });
}

// 切換功能
function switchFunction(func) {
    currentFunction = func;
    
    // 更新標籤狀態
    document.querySelectorAll('.function-tabs .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.currentTarget.classList.add('active');
    
    // 切換內容
    document.querySelectorAll('.function-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${func}-content`).classList.add('active');
    
    // 顯示對應功能的結果
    const resultSection = document.getElementById('resultSection');
    
    if (func === 'chip-mapping' && chipMappingResult.data.length > 0) {
        currentResult = chipMappingResult;
        resultSection.classList.remove('hidden');
        document.getElementById('totalRows').textContent = chipMappingResult.totalRows;
        document.getElementById('filteredRows').textContent = chipMappingResult.totalRows;
        buildResultTable(chipMappingResult.columns);
    } else if (func === 'prebuild-mapping' && prebuildMappingResult.data.length > 0) {
        currentResult = prebuildMappingResult;
        resultSection.classList.remove('hidden');
        document.getElementById('totalRows').textContent = prebuildMappingResult.totalRows;
        document.getElementById('filteredRows').textContent = prebuildMappingResult.totalRows;
        buildResultTable(prebuildMappingResult.columns);
    } else {
        // 如果該功能沒有結果，隱藏結果區域
        resultSection.classList.add('hidden');
        currentResult = null;
    }
}

// 顯示結果來源提示
function showResultSourceHint() {
    const resultHeader = document.querySelector('#resultSection .step-header');
    if (!resultHeader) return;
    
    // 移除舊的提示
    const oldHint = resultHeader.querySelector('.result-source-hint');
    if (oldHint) {
        oldHint.remove();
    }
    
    // 新增提示
    const hint = document.createElement('div');
    hint.className = 'result-source-hint';
    
    const sourceName = currentResultSource === 'chip-mapping' ? 'Chip Mapping' : 'Prebuild Mapping';
    hint.innerHTML = `
        <i class="fas fa-info-circle"></i>
        <span>此結果來自 ${sourceName}</span>
    `;
    
    resultHeader.appendChild(hint);
}

// 初始化檔案上傳
function initializeFileUploads() {
    // Chip Mapping 檔案上傳
    setupFileUpload('mappingUploadArea', 'mappingFileInput', handleMappingFile);
    
    // Prebuild Mapping 檔案上傳
    ['master', 'premp', 'mp', 'mpbackup'].forEach(type => {
        setupFileUpload(`${type}UploadArea`, `${type}FileInput`, (file) => handlePrebuildFile(type, file));
    });
}

// 設定檔案上傳
function setupFileUpload(areaId, inputId, handler) {
    const area = document.getElementById(areaId);
    const input = document.getElementById(inputId);
    
    if (!area || !input) return;
    
    // 點擊上傳
    area.addEventListener('click', (e) => {
        if (e.target.tagName !== 'BUTTON') {
            input.click();
        }
    });
    
    // 檔案選擇
    input.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handler(file);
    });
    
    // 拖放功能
    area.addEventListener('dragover', (e) => {
        e.preventDefault();
        area.classList.add('dragging');
    });
    
    area.addEventListener('dragleave', () => {
        area.classList.remove('dragging');
    });
    
    area.addEventListener('drop', (e) => {
        e.preventDefault();
        area.classList.remove('dragging');
        
        const file = e.dataTransfer.files[0];
        if (file) handler(file);
    });
}

// 處理 Mapping Table 檔案
async function handleMappingFile(file) {
    if (!validateFile(file)) return;
    
    try {
        showLoading('上傳檔案中...');
        
        // 使用 utils.uploadFile 上傳檔案
        const uploadResult = await utils.uploadFile(file);
        selectedMappingFile = uploadResult.filepath;
        
        // 顯示已選擇的檔案
        displaySelectedFile('mappingFileList', file.name);
        
        // 分析檔案內容
        showLoading('分析檔案內容...');
        const analysis = await analyzeMapping(uploadResult.filepath);
        
        // 更新 DB 選項
        updateDBOptions(analysis);
        
        hideLoading();
        utils.showNotification('檔案上傳成功', 'success');
        
    } catch (error) {
        hideLoading();
        console.error('檔案上傳錯誤:', error);
        utils.showNotification('檔案上傳失敗: ' + error.message, 'error');
    }
}

// 分析 Mapping Table
async function analyzeMapping(filepath) {
    console.log('分析檔案路徑:', filepath);
    
    const requestBody = JSON.stringify({ file_path: filepath });
    console.log('請求內容:', requestBody);
    
    const response = await utils.apiRequest('/api/admin/analyze-mapping-table', {
        method: 'POST',
        body: requestBody
    });
    
    return response;
}

// 更新 DB 選項
function updateDBOptions(analysis) {
    const dbSelect = document.getElementById('dbFilter');
    const versionGroup = document.getElementById('dbVersionGroup');
    const chipFilter = document.getElementById('chipFilter');
    
    // 清空現有選項
    dbSelect.innerHTML = '<option value="all">All</option>';
    
    // 更新 Chip Filter
    if (chipFilter && analysis.modules) {
        chipFilter.innerHTML = '<option value="all">All Chips</option>';
        analysis.modules.forEach(module => {
            const option = document.createElement('option');
            option.value = module.toLowerCase();
            option.textContent = module;
            chipFilter.appendChild(option);
        });
    }
    
    // 清空版本快取
    dbVersionsCache = {};
    
    // 添加 DB 選項
    if (analysis.db_list && analysis.db_list.length > 0) {
        analysis.db_list.forEach(db => {
            const option = document.createElement('option');
            option.value = db;
            
            // 建立顯示文字
            let displayText = db;
            if (analysis.db_info && analysis.db_info[db]) {
                const info = analysis.db_info[db];
                
                // 顯示 DB 類型
                if (info.types && info.types.length > 0) {
                    displayText = `${db} (${info.types.join('/')})`;
                }
            }
            
            option.textContent = displayText;
            dbSelect.appendChild(option);
        });
        
        // 顯示 DB 選擇提示
        const dbGroup = document.querySelector('.param-group:has(#dbFilter)');
        if (dbGroup) {
            let hint = dbGroup.querySelector('.form-hint');
            if (!hint) {
                hint = document.createElement('div');
                hint.className = 'form-hint';
                dbGroup.appendChild(hint);
            }
            hint.innerHTML = `<i class="fas fa-info-circle"></i> 找到 ${analysis.db_list.length} 個 DB`;
        }
    } else {
        // 沒有找到 DB
        const option = document.createElement('option');
        option.value = '';
        option.textContent = '(未找到 DB 資訊)';
        option.disabled = true;
        dbSelect.appendChild(option);
    }
    
    // 確保版本選擇器隱藏
    if (versionGroup) {
        versionGroup.style.display = 'none';
    }
}

// 載入 DB 版本
async function loadDBVersions(dbName) {
    try {
        const versionSelect = document.getElementById('dbVersion');
        
        // 顯示載入中
        versionSelect.innerHTML = '<option value="">載入版本中...</option>';
        versionSelect.disabled = true;
        
        // 檢查快取
        if (dbVersionsCache[dbName]) {
            displayVersionOptions(dbVersionsCache[dbName]);
            return;
        }
        
        // 從伺服器獲取版本
        const response = await utils.apiRequest('/api/admin/get-db-versions', {
            method: 'POST',
            body: JSON.stringify({
                db_name: dbName,
                mapping_file: selectedMappingFile
            })
        });
        
        if (response.success && response.versions) {
            // 快取結果
            dbVersionsCache[dbName] = response.versions;
            displayVersionOptions(response.versions);
        } else {
            versionSelect.innerHTML = '<option value="">無可用版本</option>';
        }
        
    } catch (error) {
        console.error('載入版本失敗:', error);
        const versionSelect = document.getElementById('dbVersion');
        versionSelect.innerHTML = '<option value="">載入失敗</option>';
        utils.showNotification('載入版本失敗: ' + error.message, 'error');
    } finally {
        const versionSelect = document.getElementById('dbVersion');
        versionSelect.disabled = false;
    }
}

// 顯示版本選項
function displayVersionOptions(versions) {
    const versionSelect = document.getElementById('dbVersion');
    
    // 清空並添加預設選項
    versionSelect.innerHTML = '<option value="">選擇版本 (可選)</option>';
    versionSelect.innerHTML += '<option value="latest">最新版本</option>';
    
    if (versions && versions.length > 0) {
        // 添加分隔線
        const separator = document.createElement('option');
        separator.disabled = true;
        separator.textContent = '─────────────';
        versionSelect.appendChild(separator);
        
        // 添加版本選項
        versions.forEach((version, index) => {
            const option = document.createElement('option');
            option.value = version;
            option.textContent = version;
            
            // 標記第一個（最新）版本
            if (index === 0) {
                option.textContent += ' (最新)';
            }
            
            versionSelect.appendChild(option);
        });
        
        // 顯示版本數量提示
        const versionGroup = document.getElementById('dbVersionGroup');
        const hint = versionGroup.querySelector('.form-hint');
        if (!hint) {
            const hintDiv = document.createElement('div');
            hintDiv.className = 'form-hint';
            hintDiv.innerHTML = `<i class="fas fa-info-circle"></i> 找到 ${versions.length} 個版本`;
            versionGroup.appendChild(hintDiv);
        }
    }
}

// 處理 Prebuild 檔案 - 修正版本，使用 utils.uploadFile
async function handlePrebuildFile(type, file) {
    if (!validateFile(file)) return;
    
    try {
        showLoading('上傳檔案中...');
        
        // 使用 utils.uploadFile 上傳檔案
        const uploadResult = await utils.uploadFile(file);
        selectedPrebuildFiles[type] = uploadResult.filepath;
        
        // 更新狀態
        document.getElementById(`${type}Status`).innerHTML = '<i class="fas fa-check-circle"></i>';
        document.getElementById(`${type}Status`).classList.add('success');
        
        // 顯示已選擇的檔案（修正這裡）
        const selectedDiv = document.getElementById(`${type}Selected`);
        selectedDiv.innerHTML = `
            <div class="file-name">${file.name}</div>
            <button class="btn-remove" onclick="removePrebuildFile('${type}')">
                <i class="fas fa-times"></i> 移除
            </button>
        `;
        selectedDiv.style.display = 'flex';
        selectedDiv.style.justifyContent = 'space-between';
        selectedDiv.style.alignItems = 'center';
        selectedDiv.style.padding = '10px 15px';
        selectedDiv.style.background = 'var(--success-light)';
        selectedDiv.style.borderTop = '1px solid var(--border-light)';
        
        // 更新篩選預覽
        updateFilterPreview();
        
        hideLoading();
        utils.showNotification('檔案上傳成功', 'success');
        
    } catch (error) {
        hideLoading();
        utils.showNotification('檔案上傳失敗: ' + error.message, 'error');
    }
}

function removePrebuildFile(type) {
    // 清除檔案
    selectedPrebuildFiles[type] = null;
    
    // 更新 UI
    document.getElementById(`${type}Status`).innerHTML = '<i class="fas fa-cloud-upload-alt"></i>';
    document.getElementById(`${type}Status`).classList.remove('success');
    document.getElementById(`${type}Selected`).style.display = 'none';
    document.getElementById(`${type}Selected`).innerHTML = '';
    
    // 更新篩選預覽
    updateFilterPreview();
    
    utils.showNotification(`已移除 ${type.toUpperCase()} 檔案`, 'info');
}

// 驗證檔案
function validateFile(file) {
    const allowedExtensions = ['xlsx', 'xls', 'csv'];
    const extension = file.name.split('.').pop().toLowerCase();
    
    if (!allowedExtensions.includes(extension)) {
        utils.showNotification('不支援的檔案格式，請選擇 Excel 或 CSV 檔案', 'error');
        return false;
    }
    
    // 檢查檔案大小（最大 50MB）
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
        utils.showNotification('檔案太大，請選擇小於 50MB 的檔案', 'error');
        return false;
    }
    
    return true;
}

// 顯示已選擇的檔案
function displaySelectedFile(containerId, filename) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h4 class="file-list-title">
                    <i class="fas fa-check-circle" style="color:white"></i>
                    已選擇的檔案
                </h4>
            </div>
            <div class="file-items">
                <div class="file-item-card">
                    <div class="file-icon-wrapper">
                        <i class="fas fa-file-excel"></i>
                    </div>
                    <div class="file-details">
                        <div class="file-name">${filename}</div>
                        <div class="file-meta">準備就緒</div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// 更新篩選預覽
function updateFilterPreview() {
    const filters = [];
    
    if (selectedPrebuildFiles.master && selectedPrebuildFiles.premp) {
        filters.push('master_vs_premp');
    }
    if (selectedPrebuildFiles.premp && selectedPrebuildFiles.mp) {
        filters.push('premp_vs_mp');
    }
    if (selectedPrebuildFiles.mp && selectedPrebuildFiles.mpbackup) {
        filters.push('mp_vs_mpbackup');
    }
    
    const preview = document.getElementById('filterPreview');
    if (filters.length > 0) {
        preview.textContent = `-filter ${filters.join(',')}`;
        preview.style.display = 'block';
    } else {
        preview.style.display = 'none';
    }
}

// 執行 Chip Mapping 時組合 filter 參數
async function runChipMapping() {
    if (!selectedMappingFile) {
        utils.showNotification('請先選擇 Mapping Table 檔案', 'error');
        return;
    }
    
    try {
        showLoading('執行 Chip Mapping 中...');
        
        // 組合 filter 參數
        const filterType = document.getElementById('filterType').value;
        const chipFilter = document.getElementById('chipFilter').value;
        
        let filterParam = filterType;
        if (chipFilter !== 'all') {
            if (filterType !== 'all') {
                filterParam = `${chipFilter},${filterType}`;
            } else {
                filterParam = chipFilter;
            }
        }
        
        // 收集參數
        const params = {
            mapping_file: selectedMappingFile,
            filter_type: filterParam,
            db_filter: document.getElementById('dbFilter').value,
            output_path: document.getElementById('chipOutputPath').value
        };
        
        // 處理 DB 版本參數
        if (params.db_filter !== 'all') {
            const dbVersion = document.getElementById('dbVersion').value;
            
            if (dbVersion && dbVersion !== 'latest') {
                // 如果選擇了特定版本，使用 DB#版本 格式
                params.db_filter = `${params.db_filter}#${dbVersion}`;
            }
        }
        
        console.log('執行參數:', params);
        
        const response = await utils.apiRequest('/api/admin/run-chip-mapping', {
            method: 'POST',
            body: JSON.stringify(params)
        });
        
        hideLoading();
        
        if (response.success) {
            currentResultSource = 'chip-mapping';  // 記錄結果來源
            displayResults(response);
            utils.showNotification('執行成功', 'success');
        } else {
            utils.showNotification('執行失敗: ' + (response.error || '未知錯誤'), 'error');
        }
        
    } catch (error) {
        hideLoading();
        utils.showNotification('執行失敗: ' + error.message, 'error');
    }
}

// 修改 displayResults 函數
function displayResults(response) {

    console.log('收到的回應:', response);
    console.log('欄位:', response.columns);
    console.log('資料範例:', response.data ? response.data[0] : '無資料');
        
    const resultData = response.data || [];
    const columns = response.columns || [];
    const totalRows = response.total_rows || resultData.length;
    
    // 根據來源儲存結果
    if (currentFunction === 'chip-mapping') {
        chipMappingResult = {
            data: resultData,
            columns: columns,
            totalRows: totalRows
        };
        currentResult = chipMappingResult;
    } else if (currentFunction === 'prebuild-mapping') {
        prebuildMappingResult = {
            data: resultData,
            columns: columns,
            totalRows: totalRows
        };
        currentResult = prebuildMappingResult;
    }
    
    // 顯示結果區域
    document.getElementById('resultSection').classList.remove('hidden');
    
    // 更新統計
    document.getElementById('totalRows').textContent = totalRows;
    document.getElementById('filteredRows').textContent = totalRows;
    
    // 建立表格
    buildResultTable(columns);
    
    // 滾動到結果區域
    document.getElementById('resultSection').scrollIntoView({ behavior: 'smooth' });
}

// 建立結果表格
function buildResultTable(columns) {
    // 確保欄位順序正確
    const expectedOrder = [
        'SN', 'RootFolder', 'Module', 'DB_Type', 'DB_Info', 
        'DB_Folder', 'DB_Version', 'SftpPath',
        'compare_DB_Type', 'compare_DB_Info', 
        'compare_DB_Folder', 'compare_DB_Version', 'compare_SftpPath'
    ];
    
    // 重新排序欄位
    const orderedColumns = [];
    expectedOrder.forEach(col => {
        if (columns.includes(col)) {
            orderedColumns.push(col);
        }
    });
    
    // 加入任何未預期的欄位
    columns.forEach(col => {
        if (!orderedColumns.includes(col)) {
            orderedColumns.push(col);
        }
    });
    
    // 使用排序後的欄位
    const finalColumns = orderedColumns.length > 0 ? orderedColumns : columns;
    
    // 建立表頭
    const thead = document.getElementById('resultTableHead');
    thead.innerHTML = '';
    
    const headerRow = document.createElement('tr');
    finalColumns.forEach(column => {
        const th = document.createElement('th');
        th.textContent = column;
        th.onclick = () => sortTable(column);
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    
    // 更新表格資料
    updateTableData();
}

// 更新表格資料（確保資料正確對應）
function updateTableData() {
    const tbody = document.getElementById('resultTableBody');
    tbody.innerHTML = '';
    
    if (!currentResult) return;
    
    // 取得欄位順序
    const headers = Array.from(document.querySelectorAll('#resultTableHead th')).map(th => th.textContent);
    
    let filteredData = currentResult.data;
    
    // 篩選資料
    if (filterText) {
        filteredData = currentResult.data.filter(row => {
            return Object.values(row).some(value => 
                String(value).toLowerCase().includes(filterText.toLowerCase())
            );
        });
    }
    
    // 更新篩選統計
    document.getElementById('filteredRows').textContent = filteredData.length;
    
    // 排序
    if (sortColumn) {
        filteredData.sort((a, b) => {
            const aVal = a[sortColumn] || '';
            const bVal = b[sortColumn] || '';
            
            if (sortDirection === 'asc') {
                return aVal > bVal ? 1 : -1;
            } else {
                return aVal < bVal ? 1 : -1;
            }
        });
    }
    
    // 分頁
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const pageData = filteredData.slice(startIndex, endIndex);
    
    // 顯示資料（按照表頭順序）
    pageData.forEach((row, rowIndex) => {
        const tr = document.createElement('tr');
        
        // 按照表頭順序取值
        headers.forEach(header => {
            const td = document.createElement('td');
            const value = row[header] || '';
            
            // 如果有搜尋文字，進行高亮
            if (filterText && value) {
                td.innerHTML = highlightText(value, filterText);
            } else {
                td.textContent = value;
            }
            
            tr.appendChild(td);
        });
        
        tbody.appendChild(tr);
    });
    
    // 更新分頁
    updatePagination(filteredData.length);
}

function highlightText(text, searchTerm) {
    if (!searchTerm || !text) return text;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    return text.toString().replace(regex, '<mark class="search-highlight">$1</mark>');
}

// 排序表格
function sortTable(column) {
    if (sortColumn === column) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = column;
        sortDirection = 'asc';
    }
    
    // 更新表頭樣式
    document.querySelectorAll('#resultTableHead th').forEach((th, index) => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        if (th.textContent === column) {
            th.classList.add(`sorted-${sortDirection}`);
        }
    });
    
    updateTableData();
}

// 更新分頁
function updatePagination(totalRows) {
    const totalPages = Math.ceil(totalRows / pageSize);
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';
    
    // 上一頁
    const prevBtn = document.createElement('button');
    prevBtn.innerHTML = '<i class="fas fa-chevron-left"></i>';
    prevBtn.disabled = currentPage === 1;
    prevBtn.onclick = () => {
        if (currentPage > 1) {
            currentPage--;
            updateTableData();
        }
    };
    pagination.appendChild(prevBtn);
    
    // 頁碼
    for (let i = 1; i <= Math.min(totalPages, 10); i++) {
        const pageBtn = document.createElement('button');
        pageBtn.textContent = i;
        pageBtn.classList.toggle('active', i === currentPage);
        pageBtn.onclick = () => {
            currentPage = i;
            updateTableData();
        };
        pagination.appendChild(pageBtn);
    }
    
    // 下一頁
    const nextBtn = document.createElement('button');
    nextBtn.innerHTML = '<i class="fas fa-chevron-right"></i>';
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.onclick = () => {
        if (currentPage < totalPages) {
            currentPage++;
            updateTableData();
        }
    };
    pagination.appendChild(nextBtn);
}

// 初始化搜尋
function initializeSearch() {
    const searchInput = document.getElementById('searchInput');
    let searchTimer;
    
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            filterText = e.target.value;
            currentPage = 1;
            updateTableData();
        }, 300);
    });
}

// 匯出結果
async function exportResult() {
    if (!currentResult || currentResult.data.length === 0) {
        utils.showNotification('沒有資料可匯出', 'warning');
        return;
    }
    
    try {
        showLoading('準備匯出...');
        
        const columns = currentResult.columns;
        
        // 直接使用 fetch 而不是 apiRequest
        const response = await fetch('/api/admin/export-result', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                data: currentResult.data,
                columns: columns,
                filename: `${currentFunction}_${new Date().getTime()}.xlsx`
            })
        });
        
        hideLoading();
        
        if (!response.ok) {
            throw new Error('匯出失敗');
        }
        
        // 下載檔案
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentFunction}_result.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        utils.showNotification('匯出成功', 'success');
        
    } catch (error) {
        hideLoading();
        utils.showNotification('匯出失敗: ' + error.message, 'error');
    }
}

// 清除結果
function clearResult() {
    document.getElementById('resultSection').classList.add('hidden');
    
    // 清除當前功能的結果
    if (currentFunction === 'chip-mapping') {
        chipMappingResult = { data: [], columns: [], totalRows: 0 };
    } else if (currentFunction === 'prebuild-mapping') {
        prebuildMappingResult = { data: [], columns: [], totalRows: 0 };
    }
    
    currentResult = null;
    currentPage = 1;
    sortColumn = null;
    sortDirection = 'asc';
    filterText = '';
    document.getElementById('searchInput').value = '';
}

// 載入快速路徑 - 修正版本，包含 DEFAULT_OUTPUT_DIR
async function loadQuickPaths() {
    try {
        const response = await utils.apiRequest('/api/admin/get-download-dirs');
        
        if (response.success) {
            const directories = response.directories || [];
            const downloadPath = response.download_path;
            
            // 添加 DEFAULT_OUTPUT_DIR 本身到目錄列表
            if (downloadPath) {
                // 檢查是否已經存在
                const exists = directories.some(dir => dir.path === downloadPath);
                
                if (!exists) {
                    // 計算 downloads 目錄的資訊
                    let fileCount = 0;
                    let totalSize = 0;
                    
                    // 統計所有子目錄的檔案數和大小
                    directories.filter(d => d.type === 'download').forEach(dir => {
                        fileCount += dir.file_count || 0;
                        totalSize += dir.size || 0;
                    });
                    
                    // 將 DEFAULT_OUTPUT_DIR 加入到目錄列表的開頭
                    directories.unshift({
                        name: 'downloads (根目錄)',
                        path: downloadPath,
                        file_count: fileCount,
                        size: totalSize,
                        size_formatted: formatFileSize(totalSize),
                        type: 'download-root'
                    });
                }
            }
            
            // 更新 Chip Mapping 的快速路徑
            updateQuickPathSelect('chipQuickPath', directories);
            
            // 更新 Prebuild Mapping 的快速路徑
            updateQuickPathSelect('prebuildQuickPath', directories);
            
            // 顯示路徑資訊
            console.log('基礎路徑:', response.base_path);
            console.log('下載路徑:', downloadPath);
            console.log('找到的目錄:', directories.length);
        }
        
    } catch (error) {
        console.error('載入快速路徑失敗:', error);
    }
}

// 格式化檔案大小 - 本地函數
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 更新快速路徑下拉選單 - 修正版本
function updateQuickPathSelect(selectId, directories) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // 清空現有選項
    select.innerHTML = '<option value="">-- 選擇目錄 --</option>';
    
    if (directories && directories.length > 0) {
        // 分組顯示目錄
        const rootDir = directories.filter(d => d.type === 'download-root');
        const taskDirs = directories.filter(d => d.type === 'task');
        const downloadDirs = directories.filter(d => d.type === 'download');
        
        // 添加 downloads 根目錄
        if (rootDir.length > 0) {
            const rootGroup = document.createElement('optgroup');
            rootGroup.label = 'Downloads 根目錄';
            
            rootDir.forEach(dir => {
                const option = document.createElement('option');
                option.value = dir.path;
                option.textContent = `${dir.name} (${dir.file_count} 檔案, ${dir.size_formatted})`;
                option.style.fontWeight = '600';
                rootGroup.appendChild(option);
            });
            
            select.appendChild(rootGroup);
        }
        
        // 添加 task 目錄
        if (taskDirs.length > 0) {
            const taskGroup = document.createElement('optgroup');
            taskGroup.label = 'Task 目錄';
            
            taskDirs.forEach(dir => {
                const option = document.createElement('option');
                option.value = dir.path;
                option.textContent = `${dir.name} (${dir.file_count} 檔案, ${dir.size_formatted})`;
                taskGroup.appendChild(option);
            });
            
            select.appendChild(taskGroup);
        }
        
        // 添加 download 子目錄
        if (downloadDirs.length > 0) {
            const downloadGroup = document.createElement('optgroup');
            downloadGroup.label = 'Downloads 子目錄';
            
            downloadDirs.forEach(dir => {
                const option = document.createElement('option');
                option.value = dir.path;
                option.textContent = `${dir.name} (${dir.file_count} 檔案, ${dir.size_formatted})`;
                downloadGroup.appendChild(option);
            });
            
            select.appendChild(downloadGroup);
        }
    } else {
        // 沒有找到目錄
        const option = document.createElement('option');
        option.value = '';
        option.textContent = '(尚無下載目錄)';
        option.disabled = true;
        select.appendChild(option);
    }
}

// 選擇快速路徑
function selectQuickPath(type) {
    const select = document.getElementById(`${type}QuickPath`);
    const input = document.getElementById(`${type}OutputPath`);
    const browseBtn = input.nextElementSibling; // 取得旁邊的瀏覽按鈕
    
    if (select.value) {
        input.value = select.value;
        // 停用手動輸入和瀏覽按鈕
        input.disabled = true;
        input.style.backgroundColor = '#f5f5f5';
        input.style.cursor = 'not-allowed';
        if (browseBtn) {
            browseBtn.disabled = true;
            browseBtn.style.opacity = '0.6';
            browseBtn.style.cursor = 'not-allowed';
        }
        utils.showNotification('已選擇路徑: ' + select.value, 'success');
    } else {
        // 恢復輸入和瀏覽按鈕
        input.disabled = false;
        input.style.backgroundColor = '';
        input.style.cursor = '';
        if (browseBtn) {
            browseBtn.disabled = false;
            browseBtn.style.opacity = '';
            browseBtn.style.cursor = '';
        }
        utils.showNotification('請選擇一個目錄', 'warning');
    }
}

// 監聽快速路徑選擇的變化
function setupQuickPathListeners() {
    ['chip', 'prebuild'].forEach(type => {
        const select = document.getElementById(`${type}QuickPath`);
        if (select) {
            select.addEventListener('change', () => {
                const input = document.getElementById(`${type}OutputPath`);
                const browseBtn = input.nextElementSibling;
                
                if (select.value === '') {
                    // 清空選擇時，恢復輸入框
                    input.disabled = false;
                    input.style.backgroundColor = '';
                    input.style.cursor = '';
                    if (browseBtn) {
                        browseBtn.disabled = false;
                        browseBtn.style.opacity = '';
                        browseBtn.style.cursor = '';
                    }
                }
            });
        }
    });
}

// 瀏覽輸出路徑（暫時實作）
function browseOutputPath(type) {
    // 顯示提示訊息
    const currentPath = document.getElementById(`${type}OutputPath`).value;
    const newPath = prompt('請輸入輸出路徑:', currentPath);
    
    if (newPath && newPath !== currentPath) {
        document.getElementById(`${type}OutputPath`).value = newPath;
        utils.showNotification('已更新輸出路徑', 'success');
    }
}

// 切換 Mapping 來源
let mappingSource = 'local';
let mappingServerPath = '/home/vince_lin/ai/preMP';
let mappingServerFiles = [];

function switchMappingSource(source) {
    mappingSource = source;
    
    // 更新標籤狀態
    document.querySelectorAll('.source-tabs .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.currentTarget.classList.add('active');
    
    // 切換內容
    document.getElementById('mapping-local-tab').classList.toggle('active', source === 'local');
    document.getElementById('mapping-server-tab').classList.toggle('active', source === 'server');
    
    // 如果切換到伺服器，載入檔案
    if (source === 'server' && !mappingServerFiles.length) {
        loadMappingServerFiles();
    }
}

// 載入伺服器檔案
async function loadMappingServerFiles() {
    const browser = document.getElementById('mappingServerBrowser');
    browser.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> 載入中...</div>';
    
    try {
        const response = await utils.apiRequest(`/api/browse-server?path=${encodeURIComponent(mappingServerPath)}`);
        displayMappingServerFiles(response);
    } catch (error) {
        browser.innerHTML = `<div class="error-message">載入失敗: ${error.message}</div>`;
    }
}

// 顯示伺服器檔案
function displayMappingServerFiles(data) {
    const browser = document.getElementById('mappingServerBrowser');
    const { files = [], folders = [] } = data;
    
    let html = '<div class="file-grid">';
    
    // 返回上層
    if (mappingServerPath !== '/') {
        html += `
            <div class="file-item folder" onclick="navigateMappingParent()">
                <i class="fas fa-level-up-alt"></i>
                <span class="file-name">..</span>
            </div>
        `;
    }
    
    // 資料夾
    folders.forEach(folder => {
        html += `
            <div class="file-item folder" onclick="navigateMappingTo('${folder.path}')">
                <i class="fas fa-folder"></i>
                <span class="file-name">${folder.name}</span>
            </div>
        `;
    });
    
    // Excel/CSV 檔案
    files.filter(f => f.name.endsWith('.xlsx') || f.name.endsWith('.xls') || f.name.endsWith('.csv'))
        .forEach(file => {
            html += `
                <div class="file-item file" onclick="selectMappingServerFile('${file.path}', '${file.name}')">
                    <i class="fas fa-file-excel"></i>
                    <span class="file-name">${file.name}</span>
                    <span class="file-size">${utils.formatFileSize(file.size)}</span>
                </div>
            `;
        });
    
    html += '</div>';
    browser.innerHTML = html;
}

// 導航到資料夾
function navigateMappingTo(path) {
    mappingServerPath = path;
    document.getElementById('mappingServerPath').value = path;
    loadMappingServerFiles();
}

// 返回上層
function navigateMappingParent() {
    const parentPath = mappingServerPath.substring(0, mappingServerPath.lastIndexOf('/')) || '/';
    navigateMappingTo(parentPath);
}

// 前往路徑
function goToMappingPath() {
    const path = document.getElementById('mappingServerPath').value;
    if (path) {
        mappingServerPath = path;
        loadMappingServerFiles();
    }
}

// 重新整理
function refreshMappingFiles() {
    loadMappingServerFiles();
}

// 選擇伺服器檔案
async function selectMappingServerFile(path, name) {
    selectedMappingFile = path;
    
    // 顯示已選擇
    document.getElementById('mappingServerSelected').innerHTML = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h4 class="file-list-title">
                    <i class="fas fa-check-circle" style="color:white"></i>
                    已選擇的檔案
                </h4>
            </div>
            <div class="file-items">
                <div class="file-item-card">
                    <div class="file-icon-wrapper">
                        <i class="fas fa-file-excel"></i>
                    </div>
                    <div class="file-details">
                        <div class="file-name">${name}</div>
                        <div class="file-meta">
                            <span class="file-path">${path}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 分析檔案
    try {
        showLoading('分析檔案中...');
        const analysis = await analyzeMapping(path);
        updateDBOptions(analysis);
        hideLoading();
        utils.showNotification('檔案選擇成功', 'success');
    } catch (error) {
        hideLoading();
        utils.showNotification('檔案分析失敗: ' + error.message, 'error');
    }
}

// 顯示載入中
function showLoading(text = '處理中...') {
    const overlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    
    if (overlay && loadingText) {
        loadingText.textContent = text;
        overlay.classList.remove('hidden');
    }
}

// 隱藏載入中
function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.add('hidden');
    }
}

// 關閉資料夾瀏覽器
function closeFolderBrowser() {
    document.getElementById('folderBrowserModal').classList.add('hidden');
}

// 選擇資料夾
function selectFolder() {
    // 實作資料夾選擇邏輯
    closeFolderBrowser();
}

// 切換快速路徑開關
function toggleQuickPath(type) {
    const toggle = document.getElementById(`${type}UseQuickPath`);
    const quickPathGroup = document.getElementById(`${type}QuickPathGroup`);
    const quickSelect = quickPathGroup.parentElement;
    const outputPath = document.getElementById(`${type}OutputPath`);
    const browseBtn = outputPath.nextElementSibling;
    const quickPathSelect = document.getElementById(`${type}QuickPath`);
    
    if (toggle.checked) {
        // 開啟快速路徑
        quickPathGroup.style.display = 'block';
        quickSelect.classList.add('active');
        
        // 如果已選擇路徑，套用到輸入框
        if (quickPathSelect.value) {
            outputPath.value = quickPathSelect.value;
        }
        
        // 停用手動輸入
        outputPath.disabled = true;
        browseBtn.disabled = true;
    } else {
        // 關閉快速路徑
        quickPathGroup.style.display = 'none';
        quickSelect.classList.remove('active');
        
        // 恢復手動輸入
        outputPath.disabled = false;
        browseBtn.disabled = false;
    }
}

// 更新快速路徑選擇
function updateQuickPath(type) {
    const toggle = document.getElementById(`${type}UseQuickPath`);
    const quickPathSelect = document.getElementById(`${type}QuickPath`);
    const outputPath = document.getElementById(`${type}OutputPath`);
    
    // 只有在開關開啟時才更新
    if (toggle.checked && quickPathSelect.value) {
        outputPath.value = quickPathSelect.value;
        utils.showNotification('已選擇路徑: ' + quickPathSelect.value, 'success');
    }
}

// 執行 Prebuild Mapping
async function runPrebuildMapping() {
    // 檢查至少有兩個檔案
    const validFiles = {};
    let fileCount = 0;
    
    for (const [type, path] of Object.entries(selectedPrebuildFiles)) {
        if (path && path !== null && path !== 'null') {
            validFiles[type] = path;
            fileCount++;
        }
    }
    
    if (fileCount < 2) {
        utils.showNotification('請至少選擇兩個檔案', 'error');
        return;
    }
    
    try {
        showLoading('執行 Prebuild Mapping 中...');
        
        const params = {
            files: validFiles,  // 只傳遞有效的檔案
            output_path: document.getElementById('prebuildOutputPath').value
        };
        
        console.log('執行參數:', params);
        
        const response = await utils.apiRequest('/api/admin/run-prebuild-mapping', {
            method: 'POST',
            body: JSON.stringify(params)
        });
        
        hideLoading();
        
        if (response.success) {
            currentResultSource = 'prebuild-mapping';  // 記錄結果來源
            displayResults(response);
            utils.showNotification('執行成功', 'success');
        } else {
            console.error('執行失敗:', response);
            utils.showNotification('執行失敗: ' + (response.error || '未知錯誤'), 'error');
        }
        
    } catch (error) {
        hideLoading();
        console.error('執行錯誤:', error);
        utils.showNotification('執行失敗: ' + error.message, 'error');
    }
}

// 顯示已選擇的檔案（加入刪除功能）
function displaySelectedFile(containerId, filename) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h4 class="file-list-title">
                    <i class="fas fa-check-circle"></i>
                    已選擇的檔案
                </h4>
                <button class="btn btn-small btn-danger" onclick="removeFile('${containerId}')">
                    <i class="fas fa-trash"></i> 刪除
                </button>
            </div>
            <div class="file-items">
                <div class="file-item-card">
                    <div class="file-icon-wrapper">
                        <i class="fas fa-file-excel"></i>
                    </div>
                    <div class="file-details">
                        <div class="file-name">${filename}</div>
                        <div class="file-meta">準備就緒</div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// 新增刪除檔案函數
function removeFile(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = '';
    }
    
    // 清除相關的檔案變數
    if (containerId === 'mappingFileList') {
        selectedMappingFile = null;
        // 清空 DB 選項
        const dbSelect = document.getElementById('dbFilter');
        dbSelect.innerHTML = '<option value="all">All</option>';
        const chipFilter = document.getElementById('chipFilter');
        chipFilter.innerHTML = '<option value="all">All Chips</option>';
        utils.showNotification('已移除 Mapping Table 檔案', 'info');
    }
}