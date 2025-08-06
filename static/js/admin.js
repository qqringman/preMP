// 後台管理 JavaScript
let currentFunction = 'chip-mapping';
let selectedMappingFile = null;
let selectedPrebuildFiles = {
    master: null,
    premp: null,
    mp: null,
    mpbackup: null
};
let resultData = [];
let currentPage = 1;
let pageSize = 50;
let sortColumn = null;
let sortDirection = 'asc';
let filterText = '';

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initializeFileUploads();
    loadQuickPaths();
    initializeSearch();
});

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
    
    // 隱藏結果區域
    document.getElementById('resultSection').classList.add('hidden');
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
        
        // 上傳檔案
        const uploadResult = await utils.uploadFile(file);
        selectedMappingFile = uploadResult.filepath;
        
        // 顯示已選擇的檔案
        displaySelectedFile('mappingFileList', file.name);
        
        // 分析檔案內容
        const analysis = await analyzeMapping(uploadResult.filepath);
        
        // 更新 DB 選項
        updateDBOptions(analysis);
        
        hideLoading();
        utils.showNotification('檔案上傳成功', 'success');
        
    } catch (error) {
        hideLoading();
        utils.showNotification('檔案上傳失敗: ' + error.message, 'error');
    }
}

// 分析 Mapping Table
async function analyzeMapping(filepath) {
    const response = await utils.apiRequest('/api/admin/analyze-mapping-table', {
        method: 'POST',
        body: JSON.stringify({ file_path: filepath })
    });
    
    return response;
}

// 更新 DB 選項
function updateDBOptions(analysis) {
    const dbSelect = document.getElementById('dbFilter');
    
    // 清空現有選項
    dbSelect.innerHTML = '<option value="all">All</option>';
    
    // 添加 DB 選項
    if (analysis.db_list) {
        analysis.db_list.forEach(db => {
            const option = document.createElement('option');
            option.value = db;
            option.textContent = db;
            dbSelect.appendChild(option);
        });
    }
    
    // 監聽 DB 選擇變化
    dbSelect.addEventListener('change', async (e) => {
        if (e.target.value !== 'all') {
            document.getElementById('dbVersionGroup').style.display = 'block';
            await loadDBVersions(e.target.value);
        } else {
            document.getElementById('dbVersionGroup').style.display = 'none';
        }
    });
}

// 載入 DB 版本
async function loadDBVersions(dbName) {
    try {
        const response = await utils.apiRequest('/api/admin/get-db-versions', {
            method: 'POST',
            body: JSON.stringify({
                db_name: dbName,
                mapping_file: selectedMappingFile
            })
        });
        
        const versionSelect = document.getElementById('dbVersion');
        versionSelect.innerHTML = '<option value="">選擇版本...</option>';
        
        if (response.versions) {
            response.versions.forEach(version => {
                const option = document.createElement('option');
                option.value = version;
                option.textContent = version;
                versionSelect.appendChild(option);
            });
        }
        
    } catch (error) {
        utils.showNotification('載入版本失敗: ' + error.message, 'error');
    }
}

// 處理 Prebuild 檔案
async function handlePrebuildFile(type, file) {
    if (!validateFile(file)) return;
    
    try {
        showLoading('上傳檔案中...');
        
        // 上傳檔案
        const uploadResult = await utils.uploadFile(file);
        selectedPrebuildFiles[type] = uploadResult.filepath;
        
        // 更新狀態
        document.getElementById(`${type}Status`).innerHTML = '<i class="fas fa-check-circle"></i>';
        document.getElementById(`${type}Status`).classList.add('success');
        document.getElementById(`${type}Selected`).textContent = file.name;
        
        // 更新篩選預覽
        updateFilterPreview();
        
        hideLoading();
        utils.showNotification('檔案上傳成功', 'success');
        
    } catch (error) {
        hideLoading();
        utils.showNotification('檔案上傳失敗: ' + error.message, 'error');
    }
}

// 驗證檔案
function validateFile(file) {
    const allowedExtensions = ['xlsx', 'xls', 'csv'];
    const extension = file.name.split('.').pop().toLowerCase();
    
    if (!allowedExtensions.includes(extension)) {
        utils.showNotification('不支援的檔案格式，請選擇 Excel 或 CSV 檔案', 'error');
        return false;
    }
    
    return true;
}

// 顯示已選擇的檔案
function displaySelectedFile(containerId, filename) {
    const container = document.getElementById(containerId);
    container.innerHTML = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h4 class="file-list-title">
                    <i class="fas fa-check-circle"></i>
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

// 執行 Chip Mapping
async function runChipMapping() {
    if (!selectedMappingFile) {
        utils.showNotification('請先選擇 Mapping Table 檔案', 'error');
        return;
    }
    
    try {
        showLoading('執行 Chip Mapping 中...');
        
        const params = {
            mapping_file: selectedMappingFile,
            filter_type: document.getElementById('filterType').value,
            db_filter: document.getElementById('dbFilter').value,
            output_path: document.getElementById('chipOutputPath').value
        };
        
        // 如果選擇了特定 DB，加入版本資訊
        if (params.db_filter !== 'all') {
            const version = document.getElementById('dbVersion').value;
            if (version) {
                params.db_version = version;
            }
        }
        
        const response = await utils.apiRequest('/api/admin/run-chip-mapping', {
            method: 'POST',
            body: JSON.stringify(params)
        });
        
        hideLoading();
        
        if (response.success) {
            displayResults(response);
            utils.showNotification('執行成功', 'success');
        }
        
    } catch (error) {
        hideLoading();
        utils.showNotification('執行失敗: ' + error.message, 'error');
    }
}

// 執行 Prebuild Mapping
async function runPrebuildMapping() {
    // 檢查至少有兩個檔案
    const fileCount = Object.values(selectedPrebuildFiles).filter(f => f !== null).length;
    if (fileCount < 2) {
        utils.showNotification('請至少選擇兩個檔案', 'error');
        return;
    }
    
    try {
        showLoading('執行 Prebuild Mapping 中...');
        
        const params = {
            files: selectedPrebuildFiles,
            output_path: document.getElementById('prebuildOutputPath').value
        };
        
        const response = await utils.apiRequest('/api/admin/run-prebuild-mapping', {
            method: 'POST',
            body: JSON.stringify(params)
        });
        
        hideLoading();
        
        if (response.success) {
            displayResults(response);
            utils.showNotification('執行成功', 'success');
        }
        
    } catch (error) {
        hideLoading();
        utils.showNotification('執行失敗: ' + error.message, 'error');
    }
}

// 顯示結果
function displayResults(response) {
    resultData = response.data || [];
    const columns = response.columns || [];
    
    // 顯示結果區域
    document.getElementById('resultSection').classList.remove('hidden');
    
    // 更新統計
    document.getElementById('totalRows').textContent = response.total_rows || resultData.length;
    
    // 建立表格
    buildResultTable(columns);
    
    // 滾動到結果區域
    document.getElementById('resultSection').scrollIntoView({ behavior: 'smooth' });
}

// 建立結果表格
function buildResultTable(columns) {
    // 建立表頭
    const thead = document.getElementById('resultTableHead');
    thead.innerHTML = '';
    
    const headerRow = document.createElement('tr');
    columns.forEach(column => {
        const th = document.createElement('th');
        th.textContent = column;
        th.onclick = () => sortTable(column);
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    
    // 更新表格資料
    updateTableData();
}

// 更新表格資料
function updateTableData() {
    const tbody = document.getElementById('resultTableBody');
    tbody.innerHTML = '';
    
    // 篩選資料
    let filteredData = resultData;
    if (filterText) {
        filteredData = resultData.filter(row => {
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
            const aVal = a[sortColumn];
            const bVal = b[sortColumn];
            
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
    
    // 顯示資料
    pageData.forEach(row => {
        const tr = document.createElement('tr');
        Object.values(row).forEach(value => {
            const td = document.createElement('td');
            td.textContent = value || '';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    
    // 更新分頁
    updatePagination(filteredData.length);
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
    if (resultData.length === 0) {
        utils.showNotification('沒有資料可匯出', 'warning');
        return;
    }
    
    try {
        showLoading('準備匯出...');
        
        const columns = Array.from(document.querySelectorAll('#resultTableHead th')).map(th => th.textContent);
        
        const response = await utils.apiRequest('/api/admin/export-result', {
            method: 'POST',
            body: JSON.stringify({
                data: resultData,
                columns: columns,
                filename: `${currentFunction}_${new Date().getTime()}.xlsx`
            })
        });
        
        hideLoading();
        
        // 下載檔案
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentFunction}_result.xlsx`;
        a.click();
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
    resultData = [];
    currentPage = 1;
    sortColumn = null;
    sortDirection = 'asc';
    filterText = '';
    document.getElementById('searchInput').value = '';
}

// 載入快速路徑
async function loadQuickPaths() {
    try {
        const response = await utils.apiRequest('/api/admin/get-download-dirs');
        
        if (response.directories) {
            ['chip', 'prebuild'].forEach(type => {
                const select = document.getElementById(`${type}QuickPath`);
                select.innerHTML = '<option value="">-- 選擇目錄 --</option>';
                
                response.directories.forEach(dir => {
                    const option = document.createElement('option');
                    option.value = dir.path;
                    option.textContent = dir.name;
                    select.appendChild(option);
                });
            });
        }
        
    } catch (error) {
        console.error('載入快速路徑失敗:', error);
    }
}

// 選擇快速路徑
function selectQuickPath(type) {
    const select = document.getElementById(`${type}QuickPath`);
    const input = document.getElementById(`${type}OutputPath`);
    
    if (select.value) {
        input.value = select.value;
    }
}

// 瀏覽輸出路徑
function browseOutputPath(type) {
    // 這裡可以實作資料夾瀏覽功能
    // 暫時使用簡單的提示
    utils.showNotification('資料夾瀏覽功能開發中', 'info');
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
                    <i class="fas fa-check-circle"></i>
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
    
    loadingText.textContent = text;
    overlay.classList.remove('hidden');
}

// 隱藏載入中
function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
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