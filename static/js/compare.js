// 比較頁面 JavaScript - 更新以配合新的 UI

let currentTaskId = null;
let sourceDirectory = null;
let asyncDownloadUrl = null;
let currentServerPath = '/home/vince_lin/ai/preMP/downloads';
let selectedServerDirectory = null;
let currentFoldersList = [];
let serverFilesLoaded = false; // 新增變數追蹤伺服器檔案是否已載入
let pathInputTimer = null;

// 新增：儲存圖表實例
let chartInstances = {
    success: null,
    diff: null
};

// 更新 DOMContentLoaded 事件
document.addEventListener('DOMContentLoaded', () => {
    loadDownloadedDirectories();
    loadRecentComparisons();
    initializeEventListeners();
    initializeFolderDrop();
    initializePathInput()
    
    // 監聽標籤切換事件
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tabName = e.currentTarget.textContent.includes('伺服器') ? 'server' : 'local';
            if (tabName === 'server') {
                // 切換到伺服器標籤時載入資料夾
                setTimeout(() => {
                    if (!serverFilesLoaded) {
                        loadServerFolders(currentServerPath);
                        serverFilesLoaded = true;
                    }
                }, 100);
            }
        });
    });
    
    // 初始載入伺服器資料夾（如果預設是伺服器標籤）
    const activeTab = document.querySelector('.tab-btn.active');
    if (activeTab && activeTab.textContent.includes('伺服器')) {
        loadServerFolders(currentServerPath);
        serverFilesLoaded = true;
    }
});

// 載入伺服器資料夾
async function loadServerFolders(path) {
    const browserContent = document.getElementById('serverBrowser');
    const pathDisplay = document.getElementById('currentPathDisplay');
    
    // 更新路徑輸入框
    const pathInput = document.getElementById('serverPathInput');
    if (pathInput) {
        pathInput.value = path;
    }
    
    // 更新路徑顯示
    if (pathDisplay) {
        pathDisplay.textContent = path;
    }
    
    currentServerPath = path;
    
    // 顯示載入中
    browserContent.innerHTML = `
        <div class="loading">
            <i class="fas fa-spinner fa-spin fa-3x"></i>
            <p>載入中...</p>
        </div>
    `;
    
    try {
        // 呼叫 API 獲取資料夾列表
        const response = await utils.apiRequest(`/api/list-folders?path=${encodeURIComponent(path)}`);
        
        if (response.folders && response.folders.length > 0) {
            currentFoldersList = response.folders; // 儲存資料夾列表
            displayFolders(response.folders);
        } else {
            currentFoldersList = [];
            browserContent.innerHTML = `
                <div class="empty-message">
                    <i class="fas fa-folder-open fa-3x"></i>
                    <p>此目錄下沒有子資料夾</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Load folders error:', error);
        browserContent.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle fa-3x"></i>
                <p>無法載入資料夾列表</p>
                <p class="text-muted">${error.message}</p>
            </div>
        `;
    }
}

// 顯示資料夾列表
function displayFolders(folders) {
    const browserContent = document.getElementById('serverBrowser');
    const pathDisplay = document.getElementById('currentPathDisplay');
    
    // 更新路徑顯示
    if (pathDisplay) {
        pathDisplay.textContent = currentServerPath;
    }
    
    // 只顯示資料夾網格，不重複路徑顯示
    let html = '<div class="folder-grid">';
    
    // 添加返回上層按鈕（如果不是根目錄）
    if (currentServerPath !== '/' && currentServerPath !== '') {
        const parentPath = currentServerPath.substring(0, currentServerPath.lastIndexOf('/')) || '/';
        html += `
            <div class="folder-item parent-folder" onclick="navigateToParent()">
                <i class="fas fa-level-up-alt"></i>
                <div class="folder-name">..</div>
            </div>
        `;
    }
    
    // 顯示資料夾
    folders.forEach(folder => {
        const isSelected = selectedServerDirectory === folder.path;
        html += `
            <div class="folder-item ${isSelected ? 'selected' : ''}" 
                 onclick="selectFolder('${folder.path}')"
                 ondblclick="navigateToFolder('${folder.path}')">
                <i class="fas fa-folder"></i>
                <div class="folder-name">${folder.name}</div>
            </div>
        `;
    });
    
    html += '</div>';
    browserContent.innerHTML = html;
}

// 導航到上層目錄
function navigateToParent() {
    const parentPath = currentServerPath.substring(0, currentServerPath.lastIndexOf('/')) || '/';
    serverFilesLoaded = false;  // 重置載入狀態
    loadServerFolders(parentPath);
}

// 新增導航到子資料夾函數
function navigateToFolder(folderPath) {
    serverFilesLoaded = false;  // 重置載入狀態
    loadServerFolders(folderPath);
}

// 選擇資料夾
function selectFolder(folderPath) {
    // 設定選中的資料夾
    selectedServerDirectory = folderPath;
    
    // 更新輸入框
    document.getElementById('serverPathInput').value = folderPath;
    
    // 設定為來源目錄
    setSourceDirectory(folderPath, 'server');
    
    // 重新顯示當前資料夾列表以更新選中狀態
    displayFoldersFromCache();
}

// 新增從快取重新顯示資料夾的函數
function displayFoldersFromCache() {
    if (currentFoldersList.length > 0) {
        displayFolders(currentFoldersList);
    }
}

// 切換標籤時載入伺服器內容
function switchSourceTab(tab) {
    // 更新標籤按鈕狀態
    document.querySelectorAll('.source-tabs .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // 切換內容
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tab}-tab`).classList.add('active');
    
    // 如果切換到伺服器標籤，載入當前路徑內容
    if (tab === 'server' && !serverFilesLoaded) {
        loadServerFolders(currentServerPath);
        serverFilesLoaded = true;
    }
}

// 防抖動函數
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

// 選擇本地目錄
function selectLocalDirectory() {
    // 因為瀏覽器限制，無法直接選擇資料夾
    // 這裡模擬選擇資料夾的行為
    utils.showNotification('請使用拖放功能或選擇已下載的目錄', 'info');
}

// 載入已下載的目錄
async function loadDownloadedDirectories() {
    try {
        const directories = await utils.apiRequest('/api/list-directories');
        const select = document.getElementById('downloadedDirectories');
        
        // 清空選項
        select.innerHTML = '<option value="">請選擇目錄...</option>';
        
        // 添加目錄選項
        directories.forEach(dir => {
            const option = document.createElement('option');
            option.value = dir.path;
            option.textContent = dir.name;
            option.dataset.type = dir.type;
            select.appendChild(option);
        });
        
        // 監聽選擇變化
        select.addEventListener('change', (e) => {
            if (e.target.value) {
                setSourceDirectory(e.target.value, 'local');
            }
        });
        
    } catch (error) {
        console.error('Load directories error:', error);
    }
}

// 初始化資料夾拖曳
function initializeFolderDrop() {
    const dropArea = document.getElementById('localDirectoryArea');
    
    // 阻止瀏覽器預設行為
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    // 高亮拖曳區域
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    // 處理拖放
    dropArea.addEventListener('drop', handleFolderDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function highlight(e) {
    document.getElementById('localDirectoryArea').classList.add('dragging');
}

function unhighlight(e) {
    document.getElementById('localDirectoryArea').classList.remove('dragging');
}

// 處理資料夾拖放
function handleFolderDrop(e) {
    const dt = e.dataTransfer;
    const items = dt.items;
    
    if (items && items.length > 0) {
        const item = items[0];
        if (item.kind === 'file') {
            const entry = item.webkitGetAsEntry();
            if (entry && entry.isDirectory) {
                // 設定資料夾路徑
                setSourceDirectory(entry.fullPath || entry.name, 'dropped');
            } else {
                utils.showNotification('請拖曳資料夾，而不是檔案', 'warning');
            }
        }
    }
}

// 重新整理伺服器路徑
function refreshServerPath() {
    serverFilesLoaded = false;
    loadServerFolders(currentServerPath);
}

// 前往指定路徑
function goToPath() {
    const path = document.getElementById('serverPathInput').value.trim();
    if (!path) {
        utils.showNotification('請輸入路徑', 'error');
        return;
    }
    
    if (!path.startsWith('/')) {
        utils.showNotification('路徑必須以 / 開頭', 'error');
        return;
    }
    
    serverFilesLoaded = false;  // 重置載入狀態
    loadServerFolders(path);
}

// 設定來源目錄
function setSourceDirectory(path, type = 'local') {
    sourceDirectory = path;
    
    // 更新 UI
    const infoContainer = type === 'server' ? 
        document.getElementById('serverSelectedDirectory') : 
        document.getElementById('selectedDirectoryInfo');
        
    infoContainer.classList.remove('hidden');
    
    // 生成目錄資訊卡片
    infoContainer.innerHTML = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h3 class="file-list-title">
                    <i class="fas fa-folder"></i> 已選擇的目錄
                </h3>
                <span class="file-count-badge">${type === 'server' ? '伺服器' : '本地'}</span>
            </div>
            <div class="file-items">
                <div class="file-item-card">
                    <div class="file-icon-wrapper">
                        <i class="fas fa-folder"></i>
                    </div>
                    <div class="file-details">
                        <div class="file-name">${path.split('/').pop() || path}</div>
                        <div class="file-meta">
                            <span>目錄路徑</span>
                            <span class="file-path">
                                <i class="fas fa-folder-tree"></i> ${path}
                            </span>
                        </div>
                    </div>
                    <button class="btn-remove-file" onclick="removeDirectory('${type}')">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // 啟用比對按鈕
    document.getElementById('compareBtn').disabled = false;
    
    utils.showNotification(`已選擇${type === 'server' ? '伺服器' : ''}目錄: ${path}`, 'success');
}

// 移除目錄
function removeDirectory(type) {
    sourceDirectory = null;
    
    const infoContainer = type === 'server' ? 
        document.getElementById('serverSelectedDirectory') : 
        document.getElementById('selectedDirectoryInfo');
        
    infoContainer.classList.add('hidden');
    document.getElementById('compareBtn').disabled = true;
    
    // 重置選擇器
    if (type === 'local') {
        document.getElementById('downloadedDirectories').value = '';
    }
}

// 初始化事件監聽器
function initializeEventListeners() {

    // 監聽路徑輸入的 Enter 鍵
    document.getElementById('serverPathInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            goToPath();
        }
    });
    
    // 監聽路徑輸入變化
    document.getElementById('serverPathInput').addEventListener('input', debounce((e) => {
        const path = e.target.value.trim();
        if (path && path.startsWith('/')) {
            currentServerPath = path;
        }
    }, 300));
    
    // 監聽任務進度
    document.addEventListener('task-progress', (e) => {
        const data = e.detail;
        if (data.task_id === currentTaskId) {
            updateCompareProgress(data);
        }
    });
}

// 執行比對
async function executeCompare() {
    if (!sourceDirectory) {
        utils.showNotification('請選擇來源目錄', 'error');
        return;
    }
    
    const scenario = document.querySelector('input[name="scenario"]:checked').value;
    
    // 顯示進度
    document.getElementById('compareForm').classList.add('hidden');
    document.getElementById('compareProgress').classList.remove('hidden');
    document.getElementById('compareResults').classList.add('hidden');
    
    try {
        const response = await utils.apiRequest('/api/compare', {
            method: 'POST',
            body: JSON.stringify({
                source_dir: sourceDirectory,
                scenarios: scenario
            })
        });
        
        currentTaskId = response.task_id;
        
        // 加入任務房間
        if (socket) {
            socket.emit('join_task', { task_id: currentTaskId });
        }
        
        // 開始輪詢狀態
        pollCompareStatus();
        
    } catch (error) {
        console.error('Execute compare error:', error);
        utils.showNotification('執行比對失敗', 'error');
        resetCompareUI();
    }
}

// 更新比對進度
function updateCompareProgress(data) {
    const { progress, status, message } = data;
    
    document.getElementById('compareProgressFill').style.width = `${progress}%`;
    document.getElementById('compareProgressText').textContent = `${progress}%`;
    document.getElementById('compareMessage').textContent = message;
    
    if (status === 'completed') {
        showCompareResults(data.results);
    } else if (status === 'error') {
        utils.showNotification(`比對失敗：${message}`, 'error');
        resetCompareUI();
    }
}

// 獲取當前選擇的情境
function getSelectedScenario() {
    const selectedInput = document.querySelector('input[name="scenario"]:checked');
    return selectedInput ? selectedInput.value : 'all';
}

// 獲取情境資訊
function getScenarioInfo(scenario) {
    const scenarioMap = {
        'master_vs_premp': {
            name: 'Master vs PreMP',
            icon: 'fa-code-branch'
        },
        'premp_vs_wave': {
            name: 'PreMP vs Wave',
            icon: 'fa-water'
        },
        'wave_vs_backup': {
            name: 'Wave vs Backup',
            icon: 'fa-database'
        },
        'all': {
            name: '所有比對',
            icon: 'fa-globe'
        }
    };
    
    return scenarioMap[scenario] || scenarioMap['all'];
}

// 顯示比對結果
function showCompareResults(results) {
    document.getElementById('compareProgress').classList.add('hidden');
    document.getElementById('compareResults').classList.remove('hidden');
    
    // 生成結果摘要
    const summaryHtml = generateCompareResultsSummary(results);
    document.getElementById('resultsSummary').innerHTML = summaryHtml;
    
    // 繪製圖表
    drawCharts(results);
    
    // 重新載入最近記錄
    loadRecentComparisons();
    
    utils.showNotification('比對完成！', 'success');
}

// 生成比對結果摘要 - 使用與下載頁面相同的樣式
function generateCompareResultsSummary(results) {
    const compareResults = results.compare_results || {};
    
    // 使用與下載頁面相同的 progress-stats 結構
    let html = '<div class="progress-stats">';
    
    // Master vs PreMP
    if (compareResults.master_vs_premp) {
        const data = compareResults.master_vs_premp;
        html += createStatCard('master_vs_premp', 'Master vs PreMP', data.success || 0, 'blue', 'fa-code-branch');
    }
    
    // PreMP vs Wave  
    if (compareResults.premp_vs_wave) {
        const data = compareResults.premp_vs_wave;
        html += createStatCard('premp_vs_wave', 'PreMP vs Wave', data.success || 0, 'success', 'fa-water');
    }
    
    // Wave vs Backup
    if (compareResults.wave_vs_backup) {
        const data = compareResults.wave_vs_backup;
        html += createStatCard('wave_vs_backup', 'Wave vs Backup', data.success || 0, 'warning', 'fa-database');
    }
    
    // 計算總失敗數
    const totalFailed = Object.values(compareResults).reduce((sum, data) => {
        if (typeof data === 'object' && data.failed) {
            return sum + data.failed;
        }
        return sum;
    }, 0);
    
    // 失敗的模組
    if (totalFailed > 0) {
        html += createStatCard('failed', '無法比對', totalFailed, 'danger', 'fa-exclamation-triangle');
    }
    
    html += '</div>';
    
    // 移除提示文字部分
    
    return html;
}

// 創建統計卡片 - 新函數
function createStatCard(type, title, value, colorClass, icon) {
    return `
        <div class="stat-card ${colorClass}" onclick="showCompareDetails('${type}')" title="點擊查看詳細資料">
            <div class="stat-icon">
                <i class="fas ${icon}"></i>
            </div>
            <div class="stat-content">
                <div class="stat-value">${value}</div>
                <div class="stat-label">${title}</div>
            </div>
        </div>
    `;
}

// 創建摘要卡片
function createSummaryCard(title, data, icon) {
    return `
        <div class="summary-card">
            <div class="card-icon">
                <i class="fas ${icon}"></i>
            </div>
            <div class="card-content">
                <div class="card-title">${title}</div>
                <div class="card-value">${data.success}</div>
                <div class="card-label">個模組成功</div>
                ${data.failed > 0 ? `<div class="card-footer text-warning">${data.failed} 個失敗</div>` : ''}
            </div>
        </div>
    `;
}

// 顯示比對詳細資料
async function showCompareDetails(type) {
    if (!currentTaskId) {
        utils.showNotification('無法取得任務資訊', 'error');
        return;
    }
    
    try {
        // 取得比對資料
        const pivotData = await utils.apiRequest(`/api/pivot-data/${currentTaskId}`);
        
        // 決定要顯示的資料和標題
        let modalTitle = '';
        let modalClass = '';
        let relevantSheets = [];
        
        switch(type) {
            case 'master_vs_premp':
                modalTitle = 'Master vs PreMP';
                modalClass = 'info';
                // 可能的相關資料表
                relevantSheets = [
                    { name: 'revision_diff', title: 'Revision 差異' },
                    { name: 'branch_error', title: '分支錯誤' },
                    { name: 'lost_project', title: '新增/刪除專案' },
                    { name: 'version_diff', title: '版本檔案差異' }
                ];
                break;
            case 'premp_vs_wave':
                modalTitle = 'PreMP vs Wave';
                modalClass = 'success';
                relevantSheets = [
                    { name: 'premp_wave_diff', title: '差異比對' }
                ];
                break;
            case 'wave_vs_backup':
                modalTitle = 'Wave vs Backup';
                modalClass = 'warning';
                relevantSheets = [
                    { name: 'wave_backup_diff', title: '差異比對' }
                ];
                break;
            case 'failed':
                modalTitle = '無法比對的模組';
                modalClass = 'danger';
                relevantSheets = [
                    { name: '無法比對', title: '無法比對的模組' }
                ];
                break;
        }
        
        // 過濾出實際存在的資料表
        const availableSheets = relevantSheets.filter(sheet => pivotData[sheet.name]);
        
        // 顯示資料
        showCompareModal(pivotData, availableSheets, modalTitle, modalClass);
        
    } catch (error) {
        console.error('Show compare details error:', error);
        utils.showNotification('無法載入詳細資料', 'error');
    }
}

// 顯示比對模態框 - 修正版本
function showCompareModal(pivotData, sheets, title, modalClass) {
    // 創建或取得模態框
    let modal = document.getElementById('compareDetailsModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'compareDetailsModal';
        modal.className = 'modal hidden';
        document.body.appendChild(modal);
    }
    
    // 根據 modalClass 決定標題背景色
    let headerColor = '';
    switch(modalClass) {
        case 'info':
            headerColor = '#2196F3';
            break;
        case 'success':
            headerColor = '#4CAF50';
            break;
        case 'warning':
            headerColor = '#FF9800';
            break;
        case 'danger':
            headerColor = '#F44336';
            break;
        default:
            headerColor = '#2196F3';
    }
    
    modal.className = `modal ${modalClass}`;
    
    // 如果沒有資料
    if (!sheets || sheets.length === 0) {
        modal.innerHTML = `
            <div class="modal-content modal-large" style="display: flex; flex-direction: column; max-height: 90vh;">
                <div class="modal-header compare-modal-header" style="background: ${headerColor};">
                    <h3 class="modal-title">
                        <i class="fas fa-table"></i> ${title}
                    </h3>
                    <button class="modal-close" onclick="closeCompareModal()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="empty-message">
                        <i class="fas fa-inbox fa-3x"></i>
                        <p>沒有資料</p>
                    </div>
                </div>
            </div>
        `;
    } else if (sheets.length === 1) {
        // 只有一個資料表，不需要頁籤
        const sheetData = pivotData[sheets[0].name];
        const tableHtml = sheetData ? generateCompareTable(sheetData, sheets[0].title, headerColor) : '<div class="empty-message"><i class="fas fa-inbox fa-3x"></i><p>沒有資料</p></div>';
        
        modal.innerHTML = `
            <div class="modal-content modal-large" style="display: flex; flex-direction: column; max-height: 90vh;">
                <div class="modal-header compare-modal-header" style="background: ${headerColor};">
                    <h3 class="modal-title">
                        <i class="fas fa-table"></i> ${title}
                    </h3>
                    <button class="modal-close" onclick="closeCompareModal()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body" style="padding: 0; flex: 1; overflow: hidden;">
                    ${tableHtml}
                </div>
            </div>
        `;
    } else {
        // 多個資料表，顯示頁籤
        let tabsHtml = '<div class="source-tabs" style="margin: 20px 20px 0 20px;">';
        let contentHtml = '<div class="tab-container" style="flex: 1; overflow: hidden;">';
        
        sheets.forEach((sheet, index) => {
            const isActive = index === 0;
            const sheetData = pivotData[sheet.name];
            
            // 頁籤按鈕
            tabsHtml += `
                <button class="tab-btn ${isActive ? 'active' : ''}" 
                        onclick="switchModalTab('${sheet.name}', this)">
                    <i class="fas fa-file-alt"></i> ${sheet.title}
                </button>
            `;
            
            // 頁籤內容
            const tableHtml = sheetData ? generateCompareTable(sheetData, sheet.title, headerColor) : '<div class="empty-message"><i class="fas fa-inbox fa-3x"></i><p>沒有資料</p></div>';
            contentHtml += `
                <div class="tab-content ${isActive ? 'active' : ''}" id="tab-${sheet.name}" style="height: 100%; display: ${isActive ? 'flex' : 'none'}; flex-direction: column;">
                    ${tableHtml}
                </div>
            `;
        });
        
        tabsHtml += '</div>';
        contentHtml += '</div>';
        
        modal.innerHTML = `
            <div class="modal-content modal-large" style="display: flex; flex-direction: column; max-height: 90vh;">
                <div class="modal-header compare-modal-header" style="background: ${headerColor};">
                    <h3 class="modal-title">
                        <i class="fas fa-table"></i> ${title}
                    </h3>
                    <button class="modal-close" onclick="closeCompareModal()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body" style="padding: 0; flex: 1; overflow: hidden; display: flex; flex-direction: column;">
                    ${tabsHtml}
                    ${contentHtml}
                </div>
            </div>
        `;
    }
    
    modal.classList.remove('hidden');
}

// 切換模態框內的頁籤 - 更新版本
function switchModalTab(sheetName, clickedBtn) {
    // 更新頁籤按鈕狀態
    const modal = document.getElementById('compareDetailsModal');
    modal.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    clickedBtn.classList.add('active');
    
    // 切換內容
    modal.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    const targetContent = modal.querySelector(`#tab-${sheetName}`);
    if (targetContent) {
        targetContent.classList.add('active');
    }
}

// 生成比對表格 - 修正版本
function generateCompareTable(sheetData, sheetTitle, headerColor) {
    if (!sheetData || !sheetData.columns || !sheetData.data || sheetData.data.length === 0) {
        return '<div class="empty-message"><i class="fas fa-inbox fa-3x"></i><p>沒有資料</p></div>';
    }
    
    // 使用統一的表格結構
    let html = `
        <div class="file-list-container">
            <div class="file-list-header modal-table-header">
                <h4 class="file-list-title">
                    <i class="fas fa-list"></i> ${sheetTitle}
                </h4>
                <span class="file-count-badge">
                    共 ${sheetData.data.length} 個檔案
                </span>
            </div>
            <div class="table-scroll-wrapper">
                <div class="files-table-container">
                    <table class="files-table">
    `;
    
    // 表頭
    html += '<thead><tr>';
    
    // 動態生成欄位
    sheetData.columns.forEach(col => {
        let thText = col;
        let minWidth = '150px';
        
        // 欄位名稱對應
        const columnMap = {
            'module': { text: '模組名稱', width: '200px' },
            'location_path': { text: 'FTP 路徑', width: '400px' },
            'path': { text: 'FTP 路徑', width: '400px' },
            'base_folder': { text: '本地路徑', width: '300px' },
            'compare_folder': { text: 'compare_folder', width: '200px' },
            'file_type': { text: 'file_type', width: '150px' },
            'base_content': { text: 'base_content', width: '300px' }
        };
        
        if (columnMap[col]) {
            thText = columnMap[col].text;
            minWidth = columnMap[col].width;
        } else if (col.length > 20) {
            minWidth = '250px';
        }
        
        html += `<th style="min-width: ${minWidth};">${thText}</th>`;
    });
    
    html += '</tr></thead>';
    
    // 表身
    html += '<tbody>';
    
    sheetData.data.forEach((row) => {
        html += '<tr>';
        
        sheetData.columns.forEach(col => {
            let value = row[col] || '';
            let cellContent = value;
            
            // 處理不同類型的欄位
            if (col === 'module' || col === '模組名稱') {
                let icon = 'fa-file';
                const fileName = value.toLowerCase();
                
                if (fileName.includes('manifest.xml')) {
                    icon = 'fa-file-code';
                } else if (fileName.includes('version.txt') || fileName.includes('f_version.txt')) {
                    icon = 'fa-file-alt';
                } else if (fileName.includes('.txt')) {
                    icon = 'fa-file-alt';
                } else if (fileName.includes('dprx_quickshow')) {
                    icon = 'fa-cube';
                } else if (fileName.includes('bootcode')) {
                    icon = 'fa-microchip';
                }
                
                cellContent = `
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <i class="fas ${icon}" style="color: #2196F3;"></i>
                        <span>${value}</span>
                    </div>
                `;
            } else if (col.includes('link') || col.includes('_link')) {
                if (value && value.startsWith('http')) {
                    cellContent = `<a href="${value}" target="_blank" class="table-link">
                        <i class="fas fa-external-link-alt"></i> 查看
                    </a>`;
                }
            } else if (col.includes('path') || col.includes('folder')) {
                cellContent = `<span style="font-family: monospace; font-size: 0.875rem;">${value}</span>`;
            }
            
            html += `<td>${cellContent}</td>`;
        });
        
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    html += '</div></div>'; // 關閉 files-table-container 和 table-scroll-wrapper
    
    // 底部統計
    html += `
        <div class="table-footer">
            <i class="fas fa-chart-bar"></i>
            共 ${sheetData.data.length} 個檔案
        </div>
    `;
    
    html += '</div>';
    
    return html;
}

// 預覽失敗模組
function previewFailedModule(moduleName) {
    utils.showNotification(`無法預覽失敗的模組: ${moduleName}`, 'info');
}

// 預覽比對檔案
function previewCompareFile(fileName, filePath) {
    // 可以實作預覽功能
    console.log('Preview file:', fileName, filePath);
    utils.showNotification('預覽功能開發中', 'info');
}

// 關閉比對模態框
function closeCompareModal() {
    const modal = document.getElementById('compareDetailsModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// 繪製圖表
function drawCharts(results) {
    const compareResults = results.compare_results || {};
    
    // 獲取所有情境的數據
    let scenarios = [];
    let successData = [];
    let failedData = [];
    
    // 遍歷所有比對結果
    for (const [scenario, data] of Object.entries(compareResults)) {
        const scenarioInfo = getScenarioInfo(scenario);
        scenarios.push(scenarioInfo.name);
        successData.push(data.success || 0);
        failedData.push(data.failed || 0);
    }
    
    // 計算總數
    const totalSuccess = successData.reduce((a, b) => a + b, 0);
    const totalFailed = failedData.reduce((a, b) => a + b, 0);
    
    // 銷毀舊的圖表實例
    if (chartInstances.success) {
        chartInstances.success.destroy();
        chartInstances.success = null;
    }
    
    if (chartInstances.diff) {
        chartInstances.diff.destroy();
        chartInstances.diff = null;
    }
    
    // 成功率圖表
    const successCtx = document.getElementById('successChart').getContext('2d');
    chartInstances.success = new Chart(successCtx, {
        type: 'doughnut',
        data: {
            labels: ['成功', '失敗'],
            datasets: [{
                data: [totalSuccess, totalFailed],
                backgroundColor: ['#48BB78', '#F56565']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
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
    
    // 差異分布圖表
    const diffCtx = document.getElementById('diffChart').getContext('2d');
    chartInstances.diff = new Chart(diffCtx, {
        type: 'bar',
        data: {
            labels: ['Master vs PreMP', 'PreMP vs Wave', 'Wave vs Backup'],
            datasets: [{
                label: '成功',
                data: [
                    compareResults.master_vs_premp?.success || 0,
                    compareResults.premp_vs_wave?.success || 0,
                    compareResults.wave_vs_backup?.success || 0
                ],
                backgroundColor: '#2196F3'
            }, {
                label: '失敗',
                data: [
                    compareResults.master_vs_premp?.failed || 0,
                    compareResults.premp_vs_wave?.failed || 0,
                    compareResults.wave_vs_backup?.failed || 0
                ],
                backgroundColor: '#F56565'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    stacked: true,
                },
                y: {
                    stacked: true,
                    beginAtZero: true
                }
            }
        }
    });
}

// 計算總成功數
function getTotalSuccess(compareResults) {
    let total = 0;
    if (compareResults.master_vs_premp) total += compareResults.master_vs_premp.success || 0;
    if (compareResults.premp_vs_wave) total += compareResults.premp_vs_wave.success || 0;
    if (compareResults.wave_vs_backup) total += compareResults.wave_vs_backup.success || 0;
    return total;
}

// 查看詳細結果
function viewDetailedResults() {
    if (currentTaskId) {
        window.location.href = `/results/${currentTaskId}`;
    }
}

// 匯出結果
async function exportResults(format) {
    if (!currentTaskId) return;
    
    const endpoints = {
        excel: `/api/export-excel/${currentTaskId}`,
        html: `/api/export-html/${currentTaskId}`,
        zip: `/api/export-zip/${currentTaskId}`
    };
    
    if (format === 'zip') {
        // ZIP 檔案可能較大，使用非同步下載
        utils.showNotification('正在準備 ZIP 檔案，請稍候...', 'info');
        
        try {
            const response = await utils.apiRequest(`/api/prepare-download/${currentTaskId}`, {
                method: 'POST',
                body: JSON.stringify({ format: 'zip' })
            });
            
            if (response.ready) {
                downloadAsyncFile(response.download_url);
            } else {
                // 輪詢下載狀態
                pollDownloadStatus(response.task_id);
            }
        } catch (error) {
            utils.showNotification('準備下載失敗', 'error');
        }
    } else {
        // 其他格式直接下載
        window.location.href = endpoints[format];
    }
}

// 輪詢下載狀態
async function pollDownloadStatus(taskId) {
    const checkStatus = async () => {
        try {
            const status = await utils.apiRequest(`/api/download-status/${taskId}`);
            
            if (status.ready) {
                showAsyncDownloadToast(status.download_url);
            } else if (status.error) {
                utils.showNotification('檔案準備失敗', 'error');
            } else {
                // 繼續輪詢
                setTimeout(checkStatus, 2000);
            }
        } catch (error) {
            utils.showNotification('檢查下載狀態失敗', 'error');
        }
    };
    
    checkStatus();
}

// 顯示非同步下載提示
function showAsyncDownloadToast(downloadUrl) {
    asyncDownloadUrl = downloadUrl;
    const toast = document.getElementById('asyncDownloadToast');
    toast.classList.remove('hidden');
    
    // 5秒後自動隱藏
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 5000);
}

// 下載非同步檔案
function downloadAsyncFile() {
    if (asyncDownloadUrl) {
        window.location.href = asyncDownloadUrl;
    }
}

// 重置比對 UI
function resetCompareUI() {
    document.getElementById('compareForm').classList.remove('hidden');
    document.getElementById('compareProgress').classList.add('hidden');
    document.getElementById('compareProgressFill').style.width = '0%';
    document.getElementById('compareProgressText').textContent = '0%';
}

// 輪詢比對狀態
async function pollCompareStatus() {
    if (!currentTaskId) return;
    
    try {
        const status = await utils.apiRequest(`/api/status/${currentTaskId}`);
        
        if (status.status !== 'not_found') {
            updateCompareProgress(status);
        }
        
        if (status.status !== 'completed' && status.status !== 'error') {
            setTimeout(pollCompareStatus, 1000);
        }
    } catch (error) {
        console.error('Poll status error:', error);
    }
}

// 載入最近比對記錄
async function loadRecentComparisons() {
    try {
        const comparisons = await utils.apiRequest('/api/recent-comparisons');
        const container = document.getElementById('comparisonTimeline');
        
        if (!comparisons || comparisons.length === 0) {
            container.innerHTML = `
                <div class="timeline-empty">
                    <i class="fas fa-inbox fa-3x"></i>
                    <p>暫無比對記錄</p>
                </div>
            `;
            return;
        }
        
        // 生成時間軸
        let html = '';
        comparisons.forEach((comp, index) => {
            const statusIcon = comp.status === 'completed' ? 'fa-check-circle' : 'fa-exclamation-circle';
            const statusColor = comp.status === 'completed' ? 'text-success' : 'text-danger';
            
            html += `
                <div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <div class="timeline-content">
                        <div class="timeline-time">${formatTimeAgo(comp.timestamp)}</div>
                        <div class="timeline-title">
                            ${comp.scenario}
                            <span class="${statusColor} ml-2">
                                <i class="fas ${statusIcon}"></i>
                            </span>
                        </div>
                        <div class="timeline-desc">
                            ${comp.modules} 個模組 · ${comp.duration || '< 1 分鐘'}
                        </div>
                        <button class="btn btn-small btn-primary mt-2" 
                                onclick="window.location.href='/results/${comp.id}'">
                            查看結果
                        </button>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Load recent comparisons error:', error);
    }
}

// 格式化時間
function formatTimeAgo(date) {
    const now = new Date();
    const diff = now - new Date(date);
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return '剛剛';
    if (minutes < 60) return `${minutes} 分鐘前`;
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} 小時前`;
    
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days} 天前`;
    
    return new Date(date).toLocaleDateString('zh-TW');
}

// 初始化路徑輸入自動補全
function initializePathAutocomplete() {
    const pathInput = document.getElementById('serverPathInput');
    const suggestions = document.getElementById('pathSuggestions');
    let currentSuggestions = [];
    let selectedIndex = -1;
    
    // 監聽輸入事件
    pathInput.addEventListener('input', async (e) => {
        const value = e.target.value;
        if (value.length < 2) {
            hideSuggestions();
            return;
        }
        
        try {
            // 獲取路徑建議
            const response = await utils.apiRequest(`/api/path-suggestions?path=${encodeURIComponent(value)}`);
            if (response.suggestions && response.suggestions.length > 0) {
                showSuggestions(response.suggestions);
            } else {
                hideSuggestions();
            }
        } catch (error) {
            console.error('Get path suggestions error:', error);
            hideSuggestions();
        }
    });
    
    // 顯示建議
    function showSuggestions(items) {
        currentSuggestions = items;
        selectedIndex = -1;
        
        let html = '';
        items.forEach((item, index) => {
            html += `
                <div class="suggestion-item" data-index="${index}" data-path="${item.path}">
                    <i class="fas ${item.type === 'directory' ? 'fa-folder' : 'fa-file'}"></i>
                    <span class="path-text">${item.path}</span>
                    <span class="suggestion-type">${item.type === 'directory' ? '目錄' : '檔案'}</span>
                </div>
            `;
        });
        
        suggestions.innerHTML = html;
        suggestions.classList.add('show');
        
        // 綁定點擊事件
        suggestions.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                selectSuggestion(item.dataset.path);
            });
        });
    }
    
    // 選擇建議
    function selectSuggestion(path) {
        pathInput.value = path;
        hideSuggestions();
        // 如果是目錄，可以觸發刷新
        refreshServerPath();
    }
    
    // 隱藏建議
    function hideSuggestions() {
        suggestions.classList.remove('show');
        currentSuggestions = [];
        selectedIndex = -1;
    }
    
    // 鍵盤導航
    pathInput.addEventListener('keydown', (e) => {
        if (!suggestions.classList.contains('show')) return;
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                selectedIndex = Math.min(selectedIndex + 1, currentSuggestions.length - 1);
                updateSelection();
                break;
            case 'ArrowUp':
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, 0);
                updateSelection();
                break;
            case 'Enter':
                e.preventDefault();
                if (selectedIndex >= 0) {
                    selectSuggestion(currentSuggestions[selectedIndex].path);
                }
                break;
            case 'Escape':
                hideSuggestions();
                break;
        }
    });
    
    // 更新選中狀態
    function updateSelection() {
        const items = suggestions.querySelectorAll('.suggestion-item');
        items.forEach((item, index) => {
            if (index === selectedIndex) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
    }
    
    // 點擊外部關閉建議
    document.addEventListener('click', (e) => {
        if (!pathInput.contains(e.target) && !suggestions.contains(e.target)) {
            hideSuggestions();
        }
    });
}

// 再比一次（使用相同的設定）
function compareAgain() {
    // 銷毀現有的圖表實例
    if (chartInstances.success) {
        chartInstances.success.destroy();
        chartInstances.success = null;
    }
    
    if (chartInstances.diff) {
        chartInstances.diff.destroy();
        chartInstances.diff = null;
    }
    
    // 隱藏結果，顯示進度
    document.getElementById('compareResults').classList.add('hidden');
    document.getElementById('compareProgress').classList.remove('hidden');
    
    // 重新執行比對
    executeCompare();
}

// 比對新資料（重置表單）
function compareNewData() {
    // 銷毀現有的圖表實例
    if (chartInstances.success) {
        chartInstances.success.destroy();
        chartInstances.success = null;
    }
    
    if (chartInstances.diff) {
        chartInstances.diff.destroy();
        chartInstances.diff = null;
    }
    
    // 重置所有狀態
    sourceDirectory = null;
    selectedServerDirectory = null;
    currentTaskId = null;
    
    // 隱藏結果和進度，顯示表單
    document.getElementById('compareResults').classList.add('hidden');
    document.getElementById('compareProgress').classList.add('hidden');
    document.getElementById('compareForm').classList.remove('hidden');
    
    // 重置表單
    document.getElementById('downloadedDirectories').value = '';
    document.getElementById('selectedDirectoryInfo').classList.add('hidden');
    document.getElementById('serverSelectedDirectory').classList.add('hidden');
    document.getElementById('compareBtn').disabled = true;
    
    // 重置比對選項到預設值
    document.getElementById('scenario-all').checked = true;
    
    // 清除路徑輸入
    document.getElementById('serverPathInput').value = currentServerPath;
    
    // 通知用戶
    utils.showNotification('已重置，請選擇新的資料進行比對', 'info');
}

// 顯示路徑建議
async function showPathSuggestions(inputValue) {
    const suggestions = document.getElementById('pathSuggestions');
    if (!suggestions) {
        console.error('pathSuggestions element not found!');  // 除錯用
        return;
    }
    
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
        
        if (directories.length === 0) {
            suggestions.innerHTML = '<div class="suggestion-item disabled">沒有找到匹配的路徑</div>';
        } else {
            // 只顯示目錄（比對頁面只需要選擇目錄）
            directories.forEach(dir => {
                const item = createSuggestionItem(dir.path, dir.name, 'folder');
                suggestions.appendChild(item);
            });
        }
        
        suggestions.classList.add('show');
        
    } catch (error) {
        console.error('Path suggestions error:', error);  // 除錯用
        // 如果後端沒有實現，使用靜態建議
        showStaticSuggestions(inputValue);
    }
}

// 建立建議項目 - 新增
function createSuggestionItem(path, name, type) {
    const div = document.createElement('div');
    div.className = 'suggestion-item';
    div.dataset.path = path;
    div.onclick = () => selectSuggestion(path);
    
    // 比對頁面主要關注資料夾，但也要正確顯示檔案類型
    let icon = 'fa-folder';
    let typeText = '資料夾';
    
    if (type === 'file') {
        if (name.endsWith('.csv')) {
            icon = 'fa-file-csv';
            typeText = 'CSV 檔案';
        } else if (name.endsWith('.xls')) {
            icon = 'fa-file-excel';
            typeText = 'Excel 97-2003';
        } else if (name.endsWith('.xlsx')) {
            icon = 'fa-file-excel';
            typeText = 'Excel 檔案';
        } else {
            icon = 'fa-file';
            typeText = '檔案';
        }
    }
    
    div.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${path}</span>
        <span class="suggestion-type">${typeText}</span>
    `;
    
    return div;
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

// 隱藏建議 - 新增
function hideSuggestions() {
    const suggestions = document.getElementById('pathSuggestions');
    if (suggestions) {
        suggestions.classList.remove('show');
    }
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


// 匯出函數
window.switchSourceTab = switchSourceTab;
window.selectLocalDirectory = selectLocalDirectory;
window.refreshServerPath = refreshServerPath;
window.removeDirectory = removeDirectory;
window.executeCompare = executeCompare;
window.viewDetailedResults = viewDetailedResults;
window.exportResults = exportResults;
window.downloadAsyncFile = downloadAsyncFile;
window.navigateToParent = navigateToParent;
window.navigateToFolder = navigateToFolder;
window.selectFolder = selectFolder;
window.goToPath = goToPath;
window.compareAgain = compareAgain;
window.compareNewData = compareNewData;
window.showCompareDetails = showCompareDetails;
window.closeCompareModal = closeCompareModal;
window.switchModalTab = switchModalTab;
window.previewCompareFile = previewCompareFile;
window.previewFailedModule = previewFailedModule;