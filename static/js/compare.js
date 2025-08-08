// 比較頁面 JavaScript - 更新以配合新的 UI

// 頁面變數
let currentTaskId = null;
let sourceDirectory = null;
let asyncDownloadUrl = null;
let currentServerPath = '/home/vince_lin/ai/preMP/downloads';
let selectedServerDirectory = null;
let currentFoldersList = [];
let serverFilesLoaded = false;
let pathInputTimer = null;
let chartInstances = {
    success: null,
    diff: null
};
let currentModalData = null; // 當前模態框資料

// DOMContentLoaded 事件
document.addEventListener('DOMContentLoaded', () => {
    loadDownloadedDirectories();
    loadRecentComparisons();
    initializeEventListeners();
    initializeFolderDrop();
    initializePathInput();
    
    // 監聽標籤切換事件
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tabName = e.currentTarget.textContent.includes('伺服器') ? 'server' : 'local';
            if (tabName === 'server') {
                setTimeout(() => {
                    if (!serverFilesLoaded) {
                        loadServerFolders(currentServerPath);
                        serverFilesLoaded = true;
                    }
                }, 100);
            }
        });
    });
    
    // 初始載入伺服器資料夾
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
            currentFoldersList = response.folders;
            displayFolders(response.folders);
        } else {
            currentFoldersList = [];
            browserContent.innerHTML = generateEmptyState('此目錄下沒有子資料夾', false);
        }
    } catch (error) {
        console.error('Load folders error:', error);
        browserContent.innerHTML = generateEmptyState(
            `無法載入資料夾列表：${error.message}`,
            true
        );
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
                scenarios: scenario,
                // 添加多維度支援標誌
                multi_dimension: scenario === 'all',
                separate_results: true  // 要求分開儲存各維度結果
            })
        });
        
        currentTaskId = response.task_id;
        console.log('Current task_id:', currentTaskId);
        
        // 記錄當前比對情境
        window.currentCompareScenario = scenario;
        
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
    const { progress, status, message, task_id } = data;
    
    // 如果資料中有 task_id，更新當前 task_id
    if (task_id) {
        currentTaskId = task_id;
    }
    
    document.getElementById('compareProgressFill').style.width = `${progress}%`;
    document.getElementById('compareProgressText').textContent = `${progress}%`;
    document.getElementById('compareMessage').textContent = message;
    
    if (status === 'completed') {
        // 確保 results 中包含 task_id
        if (!data.results) {
            data.results = {};
        }
        data.results.task_id = currentTaskId;
        
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

// 如果後端沒有儲存歷史記錄的 API，可以在前端暫存
let completedTasks = [];

// 修改 showCompareResults 函數，儲存失敗模組資訊
function showCompareResults(results) {
    document.getElementById('compareProgress').classList.add('hidden');
    document.getElementById('compareResults').classList.remove('hidden');
    
    // 確保 results 中有 task_id
    if (results.task_id) {
        currentTaskId = results.task_id;
    }
    
    // 儲存失敗模組資訊到全域變數
    if (results.compare_results) {
        let failedModulesList = [];
        
        Object.entries(results.compare_results).forEach(([scenario, data]) => {
            if (data && data.failed_modules && Array.isArray(data.failed_modules)) {
                data.failed_modules.forEach(module => {
                    failedModulesList.push({
                        module: module,
                        scenario: getScenarioDisplayName(scenario)
                    });
                });
            }
        });
        
        // 儲存到全域變數
        if (!window.taskFailedModules) {
            window.taskFailedModules = {};
        }
        window.taskFailedModules[currentTaskId] = failedModulesList;
    }
    
    // 生成結果摘要
    const summaryHtml = generateCompareResultsSummary(results);
    document.getElementById('resultsSummary').innerHTML = summaryHtml;
    
    // 繪製圖表
    drawCharts(results);
    
    // 重新載入最近記錄
    loadRecentComparisons();
    
    utils.showNotification('比對完成！', 'success');
}

// 新增函數：將任務儲存到歷史記錄
async function saveTaskToHistory(results) {
    try {
        // 獲取當前選擇的情境
        const scenarioInput = document.querySelector('input[name="scenario"]:checked');
        const scenarioValue = scenarioInput ? scenarioInput.value : 'all';
        const scenarioInfo = getScenarioInfo(scenarioValue);
        
        // 計算總模組數
        const compareResults = results.compare_results || {};
        let totalModules = 0;
        Object.values(compareResults).forEach(data => {
            if (typeof data === 'object' && data.success) {
                totalModules += data.success;
            }
        });
        
        // 呼叫後端 API 儲存任務記錄
        await utils.apiRequest('/api/save-comparison-history', {
            method: 'POST',
            body: JSON.stringify({
                task_id: currentTaskId,
                scenario: scenarioInfo.name,
                modules: totalModules,
                status: 'completed',
                timestamp: new Date().toISOString()
            })
        });
    } catch (error) {
        console.error('Save task to history error:', error);
        // 不顯示錯誤訊息給使用者，因為這是背景操作
    }
}

function insertCurrentTaskToTimeline(results) {
    const container = document.getElementById('comparisonTimeline');
    if (!container) return;
    
    // 獲取當前選擇的情境
    const scenarioInput = document.querySelector('input[name="scenario"]:checked');
    const scenarioValue = scenarioInput ? scenarioInput.value : 'all';
    const scenarioInfo = getScenarioInfo(scenarioValue);
    
    // 計算總模組數
    const compareResults = results.compare_results || {};
    let totalModules = 0;
    Object.values(compareResults).forEach(data => {
        if (typeof data === 'object' && data.success) {
            totalModules += data.success;
        }
    });
    
    // 建立當前任務的 HTML
    const currentTaskHtml = `
        <div class="timeline-item current-task-highlight" data-task-id="${currentTaskId}">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
                <div class="timeline-time">剛剛完成</div>
                <div class="timeline-title">
                    ${scenarioInfo.name}
                    <span class="text-success ml-2">
                        <i class="fas fa-check-circle"></i>
                    </span>
                    <span class="badge badge-current ml-2">當前任務</span>
                </div>
                <div class="timeline-desc">
                    ${totalModules} 個模組 · 剛完成
                </div>
                <button class="btn btn-small btn-primary mt-2" 
                        onclick="window.location.href='/results/${currentTaskId}'">
                    查看結果
                </button>
            </div>
        </div>
    `;
    
    // 先設定當前任務
    container.innerHTML = currentTaskHtml;
    
    // 然後載入歷史記錄（會附加在當前任務後面）
    loadHistoricalComparisons();
}

// 載入歷史比對記錄（不包含當前任務）
async function loadHistoricalComparisons() {
    try {
        const comparisons = await utils.apiRequest('/api/recent-comparisons');
        const container = document.getElementById('comparisonTimeline');
        
        if (!comparisons || comparisons.length === 0) {
            // 如果沒有歷史記錄，只保留當前任務
            return;
        }
        
        // 保存當前任務的 HTML（如果存在）
        const currentTaskElement = container.querySelector('.current-task-highlight');
        let html = currentTaskElement ? currentTaskElement.outerHTML : '';
        
        // 生成歷史記錄
        comparisons.forEach((comp) => {
            const taskId = comp.task_id || comp.id || '';
            
            // 跳過當前任務
            if (currentTaskId && taskId === currentTaskId) {
                return;
            }
            
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
                                onclick="window.location.href='/results/${taskId}'">
                            查看結果
                        </button>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Load historical comparisons error:', error);
    }
}

// 修改 loadRecentComparisons 函數，排除當前任務
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
            const taskId = comp.task_id || comp.id || '';
            
            // 檢查是否為當前任務
            const isCurrentTask = currentTaskId && taskId === currentTaskId;
            
            html += `
                <div class="timeline-item ${isCurrentTask ? 'current-task' : ''}">
                    <div class="timeline-dot"></div>
                    <div class="timeline-content">
                        <div class="timeline-time">${formatTimeAgo(comp.timestamp)}</div>
                        <div class="timeline-title">
                            ${comp.scenario}
                            <span class="${statusColor} ml-2">
                                <i class="fas ${statusIcon}"></i>
                            </span>
                            ${isCurrentTask ? '<span class="badge badge-primary ml-2">當前</span>' : ''}
                        </div>
                        <div class="timeline-desc">
                            ${comp.modules} 個模組 · ${comp.duration || '< 1 分鐘'}
                        </div>
                        <button class="btn btn-small btn-primary mt-2" 
                                onclick="window.location.href='/results/${taskId}'">
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

// 修改生成結果摘要，確保失敗統計正確
function generateCompareResultsSummary(results) {
    const compareResults = results.compare_results || {};
    
    // 計算總失敗數
    let totalFailed = 0;
    let failedModulesList = [];
    
    Object.values(compareResults).forEach(data => {
        if (typeof data === 'object') {
            totalFailed += data.failed || 0;
            if (data.failed_modules && Array.isArray(data.failed_modules)) {
                failedModulesList = failedModulesList.concat(data.failed_modules);
            }
        }
    });
    
    // 儲存失敗的模組列表供後續使用
    if (currentTaskId) {
        if (!window.taskFailedModules) {
            window.taskFailedModules = {};
        }
        window.taskFailedModules[currentTaskId] = failedModulesList;
    }
    
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
    
    // 失敗的模組 - 只有當確實有失敗時才顯示
    if (totalFailed > 0) {
        html += createStatCard('failed', '無法比對', totalFailed, 'danger', 'fa-exclamation-triangle');
    }
    
    html += '</div>';
    
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

// 顯示比對詳細資料 - 修正版
async function showCompareDetails(type) {
    if (!currentTaskId) {
        utils.showNotification('無法取得任務資訊', 'error');
        return;
    }
    
    try {
        // 如果是 'failed' 類型，需要特別處理
        if (type === 'failed') {
            // 從 API 獲取失敗的模組資料
            await showFailedModulesModal();
            return;
        }
        
        // 其他類型的正常處理
        const pivotData = await utils.apiRequest(`/api/pivot-data/${currentTaskId}`);
        
        let modalTitle = '';
        let modalClass = '';
        let relevantSheets = [];
        
        switch(type) {
            case 'master_vs_premp':
                modalTitle = 'Master vs PreMP';
                modalClass = 'info';
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
                    { name: 'revision_diff', title: 'Revision 差異' },
                    { name: 'branch_error', title: '分支錯誤' },
                    { name: 'lost_project', title: '新增/刪除專案' },
                    { name: 'version_diff', title: '版本檔案差異' }
                ];
                break;
            case 'wave_vs_backup':
                modalTitle = 'Wave vs Backup';
                modalClass = 'warning';
                relevantSheets = [
                    { name: 'revision_diff', title: 'Revision 差異' },
                    { name: 'branch_error', title: '分支錯誤' },
                    { name: 'lost_project', title: '新增/刪除專案' },
                    { name: 'version_diff', title: '版本檔案差異' }
                ];
                break;
        }
        
        const availableSheets = relevantSheets.filter(sheet => pivotData[sheet.name]);
        
        if (availableSheets.length === 0) {
            // 如果沒有資料，顯示空資料提示
            showEmptyModal(modalTitle, modalClass);
            return;
        }
        
        currentModalData = { pivotData, sheets: availableSheets, title: modalTitle, modalClass };
        showCompareModal(pivotData, availableSheets, modalTitle, modalClass);
        
    } catch (error) {
        console.error('Show compare details error:', error);
        utils.showNotification('無法載入詳細資料', 'error');
    }
}

// 修正：顯示失敗模組的模態框
async function showFailedModulesModal() {
    try {
        // 方法1: 先嘗試從 pivot data API 獲取「無法比對」資料表
        const pivotData = await utils.apiRequest(`/api/pivot-data/${currentTaskId}`);
        
        if (pivotData && pivotData['無法比對']) {
            const failedData = pivotData['無法比對'];
            displayFailedModulesModal(failedData.data || []);
            return;
        }
        
        // 方法2: 從任務狀態 API 獲取失敗模組資訊
        const statusData = await utils.apiRequest(`/api/status/${currentTaskId}`);
        
        if (statusData && statusData.results && statusData.results.compare_results) {
            const compareResults = statusData.results.compare_results;
            
            // 收集所有失敗的模組
            let failedModules = [];
            let sn = 1;
            
            for (const [scenario, data] of Object.entries(compareResults)) {
                if (data && data.failed_modules && Array.isArray(data.failed_modules)) {
                    data.failed_modules.forEach(module => {
                        failedModules.push({
                            SN: sn++,
                            module: typeof module === 'string' ? module : (module.name || module.module || '未知'),
                            scenario: getScenarioDisplayName(scenario),
                            reason: typeof module === 'object' ? (module.reason || '無法比對') : '無法比對'
                        });
                    });
                }
            }
            
            if (failedModules.length > 0) {
                displayFailedModulesModal(failedModules);
                return;
            }
        }
        
        // 方法3: 檢查本地儲存的失敗模組資料
        if (window.taskFailedModules && window.taskFailedModules[currentTaskId]) {
            const failedModules = window.taskFailedModules[currentTaskId];
            if (failedModules.length > 0) {
                const formattedModules = failedModules.map((module, index) => ({
                    SN: index + 1,
                    module: typeof module === 'string' ? module : (module.name || module.module || '未知'),
                    scenario: '未知',
                    reason: typeof module === 'object' ? (module.reason || '無法比對') : '無法比對'
                }));
                displayFailedModulesModal(formattedModules);
                return;
            }
        }
        
        // 如果都沒有資料，顯示空模態框
        showEmptyModal('無法比對的模組', 'danger');
        
    } catch (error) {
        console.error('Show failed modules error:', error);
        showEmptyModal('無法比對的模組', 'danger');
    }
}

// 從 pivot data 獲取失敗的模組
async function fetchFailedModulesFromPivot() {
    try {
        const pivotData = await utils.apiRequest(`/api/pivot-data/${currentTaskId}`);
        
        // 檢查是否有「無法比對」資料表
        if (pivotData && pivotData['無法比對']) {
            const failedData = pivotData['無法比對'];
            displayFailedModulesModal(failedData.data || []);
        } else {
            // 沒有失敗的模組
            showEmptyModal('無法比對的模組', 'danger');
        }
    } catch (error) {
        console.error('Fetch failed modules error:', error);
        showEmptyModal('無法比對的模組', 'danger');
    }
}

// 顯示失敗模組的模態框
function displayFailedModulesModal(failedModules) {
    let modal = document.getElementById('compareDetailsModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'compareDetailsModal';
        modal.className = 'modal hidden';
        document.body.appendChild(modal);
    }
    
    modal.className = 'modal danger';
    
    const recordCount = failedModules.length;
    
    let html = `
        <div class="modal-content modal-large">
            <div class="modal-header">
                <h3 class="modal-title">
                    <i class="fas fa-exclamation-triangle"></i> 無法比對的模組
                </h3>
                <span class="modal-count">共 ${recordCount} 筆資料</span>
                <button class="modal-close" onclick="closeCompareModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
    `;
    
    if (recordCount > 0) {
        // 加入搜尋列
        html += `
            <div class="modal-search-bar">
                <div class="search-input-wrapper">
                    <i class="fas fa-search search-icon"></i>
                    <input type="text" 
                           class="search-input" 
                           id="failedSearchInput" 
                           placeholder="搜尋模組名稱、情境..."
                           onkeyup="searchFailedModules()">
                </div>
                <div class="search-stats">
                    <i class="fas fa-filter"></i>
                    <span>找到 <span class="highlight-count" id="failedSearchCount">${recordCount}</span> 筆</span>
                </div>
                <button class="btn-clear-search" onclick="clearFailedSearch()">
                    <i class="fas fa-times"></i> 清除
                </button>
            </div>
        `;
        
        // 表格
        html += `
            <div class="table-wrapper">
                <div class="table-container">
                    <table class="modal-table" id="failedModulesTable">
                        <thead>
                            <tr>
                                <th class="sortable" onclick="sortFailedTable(0)" style="width: 60px; text-align: center;">SN</th>
                                <th class="sortable" onclick="sortFailedTable(1)" style="min-width: 200px;">模組名稱</th>
                                <th class="sortable" onclick="sortFailedTable(2)" style="min-width: 150px;">比對情境</th>
                                <th style="min-width: 200px;">失敗原因</th>
                            </tr>
                        </thead>
                        <tbody id="failedModulesBody">
        `;
        
        // 表格內容
        failedModules.forEach((module, index) => {
            // 檢查不同可能的欄位名稱
            const moduleId = module.SN || module['SN'] || (index + 1);
            const moduleName = module.module || module['模組名稱'] || module['module'] || '-';
            const scenario = module.scenario || module['比對情境'] || module['scenario'] || '-';
            const reason = module.reason || module['失敗原因'] || module['原因'] || module['reason'] || '無法比對';
            
            html += `
                <tr>
                    <td class="index-cell">${moduleId}</td>
                    <td class="file-name-cell">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i class="fas fa-exclamation-circle" style="color: #F44336;"></i>
                            <span class="searchable">${moduleName}</span>
                        </div>
                    </td>
                    <td class="searchable">${scenario}</td>
                    <td class="text-red searchable">${reason}</td>
                </tr>
            `;
        });
        
        html += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        
        // 底部統計
        html += `
            <div class="table-footer">
                <div class="table-footer-stats">
                    <div class="footer-stat">
                        <i class="fas fa-chart-bar"></i>
                        <span>共 <span class="footer-stat-value">${recordCount}</span> 個無法比對的模組</span>
                    </div>
                </div>
            </div>
        `;
    } else {
        html += '<div class="empty-message"><i class="fas fa-check-circle"></i><p>沒有無法比對的模組</p></div>';
    }
    
    html += '</div></div>';
    
    modal.innerHTML = html;
    modal.classList.remove('hidden');
}

// 新增：排序失敗模組表格
function sortFailedTable(columnIndex) {
    const table = document.getElementById('failedModulesTable');
    if (!table) return;
    
    const tbody = table.querySelector('tbody');
    const headers = table.querySelectorAll('th');
    const currentHeader = headers[columnIndex];
    
    // 獲取當前排序狀態
    let sortOrder = currentHeader.classList.contains('sort-asc') ? 'desc' : 'asc';
    
    // 清除所有排序狀態
    headers.forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
    });
    
    // 設置新的排序狀態
    currentHeader.classList.add(`sort-${sortOrder}`);
    
    // 獲取所有行
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // 排序
    rows.sort((a, b) => {
        const aValue = a.cells[columnIndex].textContent.trim();
        const bValue = b.cells[columnIndex].textContent.trim();
        
        // 數字排序
        if (columnIndex === 0) { // SN 欄位
            return sortOrder === 'asc' ? 
                parseInt(aValue) - parseInt(bValue) : 
                parseInt(bValue) - parseInt(aValue);
        }
        
        // 文字排序
        if (sortOrder === 'asc') {
            return aValue.localeCompare(bValue);
        } else {
            return bValue.localeCompare(aValue);
        }
    });
    
    // 重新排列行
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

// 顯示空模態框
function showEmptyModal(title, modalClass) {
    let modal = document.getElementById('compareDetailsModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'compareDetailsModal';
        modal.className = 'modal hidden';
        document.body.appendChild(modal);
    }
    
    modal.className = `modal ${modalClass}`;
    
    modal.innerHTML = `
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
    
    modal.classList.remove('hidden');
}

// 獲取情境顯示名稱
function getScenarioDisplayName(scenario) {
    const nameMap = {
        'master_vs_premp': 'Master vs PreMP',
        'premp_vs_wave': 'PreMP vs Wave',
        'wave_vs_backup': 'Wave vs Backup'
    };
    return nameMap[scenario] || scenario;
}

// 搜尋失敗的模組
function searchFailedModules() {
    const searchInput = document.getElementById('failedSearchInput');
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const tbody = document.querySelector('#failedModulesBody');
    const resultCount = document.getElementById('failedSearchCount');
    
    if (tbody) {
        searchTableContent(tbody, searchTerm, resultCount);
    }
}

// 清除失敗模組搜尋
function clearFailedSearch() {
    const searchInput = document.getElementById('failedSearchInput');
    if (searchInput) {
        searchInput.value = '';
        searchFailedModules();
    }
}

// 顯示比對模態框 - 統一樣式版本
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
        modal.innerHTML = generateEmptyModal(title);
    } else if (sheets.length === 1) {
        // 單頁籤 - 使用統一的樣式
        modal.innerHTML = generateSingleSheetModal(pivotData[sheets[0].name], sheets[0], title, modalClass);
    } else {
        // 多頁籤 - 保持原設計但加入搜尋功能
        modal.innerHTML = generateMultiSheetModal(pivotData, sheets, title, modalClass);
    }
    
    modal.classList.remove('hidden');
}

// 修改多頁籤模態框生成 - 加入底部統計
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
        const recordCount = sheetData && sheetData.data ? sheetData.data.length : 0;
        
        html += `
            <div class="tab-content ${isActive ? 'active' : ''}" 
                 id="tab-${sheet.name}" 
                 style="display: ${isActive ? 'block' : 'none'};">
        `;
        
        if (sheetData && sheetData.data && sheetData.data.length > 0) {
            // 搜尋列
            html += `
                <div class="modal-search-bar">
                    <div class="search-input-wrapper">
                        <i class="fas fa-search search-icon"></i>
                        <input type="text" 
                               class="search-input" 
                               id="search-${sheet.name}" 
                               placeholder="搜尋${sheet.title}..."
                               onkeyup="searchTabContent('${sheet.name}')">
                    </div>
                    <div class="search-stats">
                        <i class="fas fa-filter"></i>
                        <span>找到 <span class="highlight-count" id="count-${sheet.name}">${recordCount}</span> 筆</span>
                    </div>
                    <button class="btn-clear-search" onclick="clearTabSearch('${sheet.name}')">
                        <i class="fas fa-times"></i> 清除
                    </button>
                </div>
            `;
            
            html += generateCompareTable(sheetData, sheet.name);
            
            // 加入底部統計
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
        
        html += '</div>';
    });
    
    html += '</div></div>';
    
    return html;
}

// 生成空模態框
function generateEmptyModal(title) {
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

// 生成單頁籤模態框 - 修正搜尋功能綁定
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
        // 加入搜尋列 - 使用通用的搜尋函數
        html += `
            <div class="modal-search-bar">
                <div class="search-input-wrapper">
                    <i class="fas fa-search search-icon"></i>
                    <input type="text" 
                           class="search-input" 
                           id="search-single-sheet" 
                           placeholder="搜尋內容..."
                           onkeyup="searchSingleSheetContent()">
                </div>
                <div class="search-stats">
                    <i class="fas fa-filter"></i>
                    <span>找到 <span class="highlight-count" id="singleSheetSearchCount">${recordCount}</span> 筆</span>
                </div>
                <button class="btn-clear-search" onclick="clearSingleSheetSearch()">
                    <i class="fas fa-times"></i> 清除
                </button>
            </div>
        `;
        
        // 給表格加上特定 ID
        html += '<div class="table-wrapper">';
        html += '<div class="table-container">';
        html += '<table class="modal-table" id="single-sheet-table">';
        
        // 生成表格內容...
        const tableContent = generateCompareTableContent(sheetData, sheet.name);
        html += tableContent.replace('<table class="modal-table"', '').replace('</table>', '');
        
        html += '</table>';
        html += '</div></div>';
        
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

// 搜尋單頁籤內容
function searchSingleSheetContent() {
    const searchInput = document.getElementById('search-single-sheet');
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const tbody = document.querySelector('#single-sheet-table tbody');
    const resultCount = document.getElementById('singleSheetSearchCount');
    
    if (tbody) {
        searchTableContent(tbody, searchTerm, resultCount);
    }
}

// 清除單頁籤搜尋
function clearSingleSheetSearch() {
    const searchInput = document.getElementById('search-single-sheet');
    if (searchInput) {
        searchInput.value = '';
        searchSingleSheetContent();
    }
}

// 生成比對表格內容 - 完整版本，包含版本差異顏色標註
function generateCompareTableContent(sheetData, sheetName) {
    console.log('generateCompareTableContent - sheetName:', sheetName);
    if (!sheetData || !sheetData.columns || !sheetData.data || sheetData.data.length === 0) {
        return generateEmptyState('此資料表沒有內容', false);
    }
    
    // 定義需要特殊處理的欄位
    const redHeaderColumns = {
        'revision_diff': ['base_short', 'base_revision', 'compare_short', 'compare_revision'],
        'branch_error': ['problem'],
        'lost_project': ['Base folder', '狀態'],
        'version_diff': ['base_content', 'compare_content']
    };
    
    // 修改表格容器結構，確保有捲軸
    let html = '<div class="table-wrapper" style="height: 100%; display: flex; flex-direction: column;">';
    html += '<div class="table-container" style="flex: 1; overflow: auto; max-height: 500px;">';
    html += '<table class="modal-table">';
    
    // 表頭
    html += '<thead><tr>';
    
    // 動態生成欄位
    sheetData.columns.forEach(col => {
        let thText = col;
        let minWidth = '150px';
        let headerClass = '';
        
        // 檢查是否需要紅色標題
        if (redHeaderColumns[sheetName] && redHeaderColumns[sheetName].includes(col)) {
            headerClass = 'header-red-bg';
        }
        
        // 欄位名稱對應和寬度設定
        const columnMap = {
            'SN': { text: 'SN', width: '60px' },
            'module': { text: '模組名稱', width: '200px' },
            'location_path': { text: 'FTP 路徑', width: '400px' },
            'path': { text: 'FTP 路徑', width: '400px' },
            'base_folder': { text: '本地路徑', width: '300px' },
            'compare_folder': { text: 'compare_folder', width: '200px' },
            'file_type': { text: 'file_type', width: '150px' },
            'base_content': { text: 'base_content', width: '400px' },
            'compare_content': { text: 'compare_content', width: '400px' },
            'org_content': { text: 'org_content', width: '500px' },
            'problem': { text: '問題', width: '200px' },
            'has_wave': { text: 'has_wave', width: '100px' },
            'Base folder': { text: 'Base folder', width: '150px' },
            '狀態': { text: '狀態', width: '100px' },
            'name': { text: 'name', width: '250px' },
            'revision': { text: 'revision', width: '150px' },
            'revision_short': { text: 'revision_short', width: '100px' },
            'upstream': { text: 'upstream', width: '300px' },
            'dest-branch': { text: 'dest-branch', width: '300px' },
            'base_link': { text: 'base_link', width: '200px' },
            'compare_link': { text: 'compare_link', width: '200px' },
            'base_upstream': { text: 'base_upstream', width: '300px' },
            'compare_upstream': { text: 'compare_upstream', width: '300px' },
            'base_dest-branch': { text: 'base_dest-branch', width: '300px' },
            'compare_dest-branch': { text: 'compare_dest-branch', width: '300px' },
            'folder': { text: 'folder', width: '200px' },
            'link': { text: 'link', width: '200px' },
            'folder_count': { text: 'folder_count', width: '100px' },
            'folders': { text: 'folders', width: '300px' },
            'reason': { text: 'reason', width: '400px' }
        };
        
        if (columnMap[col]) {
            thText = columnMap[col].text;
            minWidth = columnMap[col].width;
        } else if (col.length > 20) {
            minWidth = '250px';
        }
        
        html += `<th class="${headerClass}" style="min-width: ${minWidth};">${thText}</th>`;
    });
    
    html += '</tr></thead>';
    
    // 表身
    html += '<tbody>';
    
    sheetData.data.forEach((row) => {
        html += `<tr>`;

        sheetData.columns.forEach(col => {
            let value = row[col] || '';
            let cellContent = value;
            let cellClass = '';
            let minWidth = '150px';
            
            // 取得與標頭相同的寬度
            const columnMap = {
                'SN': { width: '60px' },
                'module': { width: '200px' },
                'location_path': { width: '400px' },
                'path': { width: '400px' },
                'base_folder': { width: '300px' },
                'compare_folder': { width: '200px' },
                'file_type': { width: '150px' },
                'base_content': { width: '400px' },
                'compare_content': { width: '400px' },
                'org_content': { width: '500px' },
                'problem': { width: '200px' },
                'has_wave': { width: '100px' },
                'Base folder': { width: '150px' },
                '狀態': { width: '100px' },
                'name': { width: '250px' },
                'revision': { width: '150px' },
                'revision_short': { width: '100px' },
                'upstream': { width: '300px' },
                'dest-branch': { width: '300px' },
                'base_link': { width: '200px' },
                'compare_link': { width: '200px' },
                'base_upstream': { width: '300px' },
                'compare_upstream': { width: '300px' },
                'base_dest-branch': { width: '300px' },
                'compare_dest-branch': { width: '300px' },
                'folder': { width: '200px' },
                'link': { width: '200px' },
                'folder_count': { width: '100px' },
                'folders': { width: '300px' },
                'reason': { width: '400px' }
            };
            
            if (columnMap[col]) {
                minWidth = columnMap[col].width;
            } else if (col.length > 20) {
                minWidth = '250px';
            }
            
            // 處理不同類型的欄位
            if (col === 'SN') {
                // SN 欄位居中顯示
                cellContent = `<div style="text-align: center;">${value}</div>`;
            } else if (col === 'module' || col === '模組名稱') {
                // 模組名稱處理
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
                } else if (fileName.includes('emcu')) {
                    icon = 'fa-memory';
                } else if (fileName.includes('audio_fw')) {
                    icon = 'fa-volume-up';
                } else if (fileName.includes('video_fw')) {
                    icon = 'fa-video';
                } else if (fileName.includes('tee')) {
                    icon = 'fa-shield-alt';
                } else if (fileName.includes('bl31')) {
                    icon = 'fa-lock';
                }
                
                cellContent = `
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <i class="fas ${icon}" style="color: #2196F3;"></i>
                        <span>${value}</span>
                    </div>
                `;
            } else if (col === 'problem' && value) {
                // problem 欄位紅字
                cellClass = 'text-red';
                cellContent = value;
            } else if (col === '狀態') {
                // 狀態欄位根據值顯示不同顏色
                if (value === '刪除') {
                    cellClass = 'text-red';
                } else if (value === '新增') {
                    cellClass = 'text-blue';
                }
                cellContent = value;
            } else if (['base_short', 'base_revision', 'compare_short', 'compare_revision'].includes(col)) {
                // revision 相關欄位紅字
                cellClass = 'text-red';
                cellContent = value;
            } else if (col === 'has_wave' || col.toLowerCase().includes('has_wave')) {
                if (value === 'Y' || value === 'y' || value === true || value === 'True') {
                    cellContent = '<span class="badge-yes">Y</span>';
                } else if (value === 'N' || value === 'n' || value === false || value === 'False') {
                    cellContent = '<span class="badge-no">N</span>';
                } else {
                    cellContent = value;
                }
            } else if ((col === 'base_content' || col === 'compare_content') && sheetName === 'version_diff') {
                // 版本差異內容的特殊處理 - 關鍵部分！
                cellContent = formatVersionDiffContentWithColors(row, col);
            } else if (col.includes('link') || col.includes('_link')) {
                // 連結欄位
                if (value && value.startsWith('http')) {
                    cellContent = `<a href="${value}" target="_blank" class="table-link">
                        <i class="fas fa-external-link-alt"></i> 查看
                    </a>`;
                }
            } else if (col.includes('path') || col.includes('folder')) {
                // 路徑欄位使用等寬字型
                cellContent = `<span style="font-family: monospace; font-size: 0.875rem;">${value}</span>`;
            } else if (col === 'org_content') {
                // org_content 欄位可能很長，限制顯示
                if (value && value.length > 100) {
                    const truncated = value.substring(0, 100) + '...';
                    cellContent = `<span title="${value.replace(/"/g, '&quot;')}" style="cursor: help;">${truncated}</span>`;
                } else {
                    cellContent = value;
                }
            }
            
            html += `<td class="${cellClass}" style="min-width: ${minWidth};">${cellContent}</td>`;
        });
        
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    html += '</div></div>';  // 關閉 table-container 和 table-wrapper
    
    return html;
}

// 修改 formatVersionDiffContentWithColors 函數，加入 debug 訊息
function formatVersionDiffContentWithColors(row, column) {
    const fileType = row['file_type'] || '';
    const baseContent = row['base_content'] || '';
    const compareContent = row['compare_content'] || '';
    const currentValue = row[column] || '';
    
    // DEBUG: 輸出原始資料
    console.log('=== formatVersionDiffContentWithColors DEBUG ===');
    console.log('Column:', column);
    console.log('File Type:', fileType);
    console.log('Current Value:', currentValue);
    console.log('Base Content:', baseContent);
    console.log('Compare Content:', compareContent);
    
    // 處理檔案不存在的情況
    if (currentValue === '(檔案不存在)') {
        return `<span class="text-red">${currentValue}</span>`;
    }
    
    if (currentValue === '(檔案存在)') {
        return `<span>${currentValue}</span>`;
    }
    
    // 處理多行差異（用換行符號分隔）
    if (currentValue.includes('\n')) {
        console.log('Multi-line detected, splitting...');
        const currentLines = currentValue.split('\n');
        const otherContent = column === 'base_content' ? compareContent : baseContent;
        const otherLines = otherContent ? otherContent.split('\n') : [];
        
        console.log('Current Lines:', currentLines);
        console.log('Other Lines:', otherLines);
        
        let formattedHtml = '<div class="version-diff-container">';
        
        currentLines.forEach((line, index) => {
            const otherLine = otherLines[index] || '';
            console.log(`Line ${index}: "${line}" vs "${otherLine}"`);
            
            formattedHtml += '<div class="version-diff-line">';
            
            if (line.startsWith('P_GIT_')) {
                console.log('Processing P_GIT line...');
                formattedHtml += formatPGitLine(line, otherLine);
            } else if (line.includes(':')) {
                console.log('Processing key:value line...');
                formattedHtml += formatKeyValueLine(line, otherLine);
            } else {
                formattedHtml += line;
            }
            
            formattedHtml += '</div>';
        });
        
        formattedHtml += '</div>';
        console.log('Final HTML:', formattedHtml);
        return formattedHtml;
    }
    
    // 單行處理
    console.log('Single line processing...');
    if (currentValue.startsWith('P_GIT_')) {
        return formatPGitLine(currentValue, column === 'base_content' ? compareContent : baseContent);
    } else if (currentValue.includes(':')) {
        return formatKeyValueLine(currentValue, column === 'base_content' ? compareContent : baseContent);
    }
    
    return currentValue;
}

// 格式化 P_GIT 行
function formatPGitLine(currentLine, otherLine) {
    if (!currentLine || !currentLine.startsWith('P_GIT_')) return currentLine;
    
    const currentParts = currentLine.split(';');
    const otherParts = otherLine ? otherLine.split(';') : [];
    
    let formatted = '';
    
    currentParts.forEach((part, index) => {
        if (index > 0) formatted += ';';
        
        if (index === 3 || index === 4) {
            const isDifferent = otherParts[index] && part !== otherParts[index];
            
            if (isDifferent) {
                formatted += `<span class="highlight" style="color: red; font-weight: bold;">${part}</span>`;
            } else {
                formatted += part;
            }
        } else {
            formatted += part;
        }
    });
    
    return formatted;
}

// 格式化 key:value 行
function formatKeyValueLine(currentLine, otherLine) {
    if (!currentLine || !currentLine.includes(':')) return currentLine;
    
    const colonIndex = currentLine.indexOf(':');
    const key = currentLine.substring(0, colonIndex);
    const value = currentLine.substring(colonIndex + 1).trim();
    
    let isDifferent = false;
    if (otherLine && otherLine.includes(':')) {
        const otherColonIndex = otherLine.indexOf(':');
        const otherKey = otherLine.substring(0, otherColonIndex);
        const otherValue = otherLine.substring(otherColonIndex + 1).trim();
        
        if (key === otherKey && value !== otherValue) {
            isDifferent = true;
        }
    }
    
    if (isDifferent) {
        return `${key}: <span class="highlight" style="color: red; font-weight: bold;">${value}</span>`;
    }
    
    return currentLine;
}

// 搜尋比對內容
function searchCompareContent() {
    const searchInput = document.getElementById('compareSearchInput');
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const tbody = document.querySelector('.modal-table tbody');
    const resultCount = document.getElementById('compareSearchCount');
    
    if (tbody) {
        searchTableContent(tbody, searchTerm, resultCount);
    }
}

// 搜尋頁籤內容
function searchTabContent(sheetName) {
    const searchInput = document.getElementById(`search-${sheetName}`);
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const tbody = document.querySelector(`#table-${sheetName} tbody`);
    const resultCount = document.getElementById(`count-${sheetName}`);
    
    if (tbody) {
        searchTableContent(tbody, searchTerm, resultCount);
    }
}

// 通用的表格搜尋功能 - 修正版
function searchTableContent(tbody, searchTerm, resultCountElement) {
    if (!tbody) return;
    
    // 清除所有現有的高亮
    tbody.querySelectorAll('.highlight').forEach(el => {
        try {
            const parent = el.parentNode;
            if (parent && parent.textContent) {
                const text = parent.textContent;
                // 保留其他 HTML 結構，只替換高亮部分
                const newHTML = parent.innerHTML.replace(/<span class="highlight">(.*?)<\/span>/gi, '$1');
                parent.innerHTML = newHTML;
            }
        } catch (e) {
            console.warn('清除高亮時出錯:', e);
        }
    });
    
    let visibleCount = 0;
    const rows = tbody.querySelectorAll('tr');
    
    rows.forEach(row => {
        if (!row) return;
        
        let matchFound = false;
        
        if (searchTerm === '') {
            // 沒有搜尋詞時顯示所有行
            row.style.display = '';
            visibleCount++;
        } else {
            // 搜尋所有 td 元素的文字內容
            const cells = row.querySelectorAll('td');
            
            cells.forEach(cell => {
                if (!cell) return;
                
                const text = (cell.textContent || '').toLowerCase();
                if (text.includes(searchTerm)) {
                    matchFound = true;
                    // 高亮匹配的文字
                    highlightSearchTerm(cell, searchTerm);
                }
            });
            
            row.style.display = matchFound ? '' : 'none';
            if (matchFound) visibleCount++;
        }
    });
    
    // 更新結果計數
    if (resultCountElement) {
        resultCountElement.textContent = visibleCount;
    }
}

// 高亮搜尋詞 - 改進版
function highlightSearchTerm(element, searchTerm) {
    if (!element || !searchTerm) return;
    
    // 遞迴處理所有文字節點
    function highlightTextNodes(node) {
        if (node.nodeType === 3) { // 文字節點
            const text = node.textContent;
            const regex = new RegExp(`(${escapeRegExp(searchTerm)})`, 'gi');
            
            if (regex.test(text)) {
                const span = document.createElement('span');
                span.innerHTML = text.replace(regex, '<span class="highlight">$1</span>');
                node.parentNode.replaceChild(span, node);
            }
        } else if (node.nodeType === 1) { // 元素節點
            // 跳過已經是高亮的元素
            if (node.className !== 'highlight') {
                // 不處理 script 和 style 標籤
                if (node.tagName !== 'SCRIPT' && node.tagName !== 'STYLE') {
                    for (let i = 0; i < node.childNodes.length; i++) {
                        highlightTextNodes(node.childNodes[i]);
                    }
                }
            }
        }
    }
    
    // 只處理可見的文字內容
    try {
        highlightTextNodes(element);
    } catch (e) {
        console.warn('高亮文字時出錯:', e);
    }
}

// 輔助函數：轉義正則表達式特殊字符
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// 清除比對搜尋
function clearCompareSearch() {
    const searchInput = document.getElementById('compareSearchInput');
    if (searchInput) {
        searchInput.value = '';
        searchCompareContent();
    }
}

// 清除頁籤搜尋
function clearTabSearch(sheetName) {
    const searchInput = document.getElementById(`search-${sheetName}`);
    if (searchInput) {
        searchInput.value = '';
        searchTabContent(sheetName);
    }
}

// 切換比對頁籤
function switchCompareTab(sheetName, clickedBtn) {
    // 更新頁籤按鈕狀態
    const modal = document.getElementById('compareDetailsModal');
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

// 在顯示空狀態時，使用新的 UI
function showEmptyState(containerId, message) {
    const container = document.getElementById(containerId);
    container.innerHTML = `
        <div class="empty-message">
            <i class="fas fa-inbox fa-3x"></i>
            <p>${message}</p>
        </div>
        <div class="empty-reload-container">
            <button class="btn-reload" onclick="location.reload()">
                <i class="fas fa-sync-alt"></i>
                重新載入
            </button>
        </div>
    `;
}

// 格式化版本差異內容
function formatVersionDiffContent(row, column) {
    const currentValue = row[column] || '';
    const baseContent = row['base_content'] || '';
    const compareContent = row['compare_content'] || '';
    
    if (currentValue === '(檔案不存在)') {
        return `<span class="text-red">${currentValue}</span>`;
    }
    
    if (currentValue === '(檔案存在)') {
        return `<span>${currentValue}</span>`;
    }
    
    // 處理多行差異
    if (currentValue.includes('\n')) {
        const currentLines = currentValue.split('\n');
        const otherContent = column === 'base_content' ? compareContent : baseContent;
        const otherLines = otherContent ? otherContent.split('\n') : [];
        
        let formattedHtml = '<div class="version-diff-container">';
        
        currentLines.forEach((line, index) => {
            const otherLine = otherLines[index] || '';
            formattedHtml += '<div class="version-diff-line">';
            
            if (line.startsWith('P_GIT_')) {
                formattedHtml += formatPGitLine(line, otherLine);
            } else if (line.includes(':')) {
                formattedHtml += formatKeyValueLine(line, otherLine);
            } else {
                formattedHtml += line;
            }
            
            formattedHtml += '</div>';
        });
        
        formattedHtml += '</div>';
        return formattedHtml;
    }
    
    // 單行處理
    if (currentValue.startsWith('P_GIT_')) {
        return formatPGitLine(currentValue, column === 'base_content' ? compareContent : baseContent);
    } else if (currentValue.includes(':')) {
        return formatKeyValueLine(currentValue, column === 'base_content' ? compareContent : baseContent);
    }
    
    return currentValue;
}

// 新增：格式化單行 F_Version 內容
function formatSingleFVersionLine(currentLine, otherLine) {
    if (!currentLine.startsWith('P_GIT_')) return currentLine;
    
    const currentParts = currentLine.split(';');
    const otherParts = otherLine ? otherLine.split(';') : [];
    
    let formattedContent = '<span class="diff-text">';
    
    currentParts.forEach((part, index) => {
        if (index > 0) formattedContent += ';';
        
        // 只有第4和第5部分（索引3和4）需要比較
        if ((index === 3 || index === 4) && 
            index < otherParts.length && 
            part !== otherParts[index]) {
            formattedContent += `<span class="diff-part">${part}</span>`;
        } else {
            formattedContent += `<span class="normal-part">${part}</span>`;
        }
    });
    
    formattedContent += '</span>';
    return formattedContent;
}

// 新增：格式化單行 F_HASH 內容
function formatSingleFHashLine(currentLine, otherLine) {
    if (!currentLine.includes('F_HASH:')) return currentLine;
    
    const parts = currentLine.split('F_HASH:', 2);
    if (parts.length < 2) return currentLine;
    
    const currentHash = parts[1].trim();
    let otherHash = '';
    
    if (otherLine && otherLine.includes('F_HASH:')) {
        const otherParts = otherLine.split('F_HASH:', 2);
        if (otherParts.length >= 2) {
            otherHash = otherParts[1].trim();
        }
    }
    
    let formattedContent = '<span class="diff-text">';
    formattedContent += '<span class="normal-part">F_HASH: </span>';
    
    if (currentHash !== otherHash) {
        formattedContent += `<span class="diff-part">${currentHash}</span>`;
    } else {
        formattedContent += `<span class="normal-part">${currentHash}</span>`;
    }
    
    formattedContent += '</span>';
    return formattedContent;
}

// 新增：格式化單行冒號內容
function formatSingleColonLine(currentLine, otherLine) {
    if (!currentLine.includes(':')) return currentLine;
    
    const parts = currentLine.split(':', 2);
    if (parts.length < 2) return currentLine;
    
    const key = parts[0];
    const currentVal = parts[1].trim();
    let otherVal = '';
    
    if (otherLine && otherLine.includes(':')) {
        const otherParts = otherLine.split(':', 2);
        if (otherParts.length >= 2 && otherParts[0] === key) {
            otherVal = otherParts[1].trim();
        }
    }
    
    let formattedContent = '<span class="diff-text">';
    formattedContent += `<span class="normal-part">${key}: </span>`;
    
    if (currentVal !== otherVal) {
        formattedContent += `<span class="diff-part">${currentVal}</span>`;
    } else {
        formattedContent += `<span class="normal-part">${currentVal}</span>`;
    }
    
    formattedContent += '</span>';
    return formattedContent;
}

// 格式化包含冒號的內容
function formatColonContent(currentValue, otherValue) {
    if (!currentValue.includes(':')) return currentValue;
    
    const parts = currentValue.split(':', 2);
    if (parts.length < 2) return currentValue;
    
    const key = parts[0];
    const currentVal = parts[1].trim();
    let otherVal = '';
    
    if (otherValue && otherValue.includes(':')) {
        const otherParts = otherValue.split(':', 2);
        if (otherParts.length >= 2 && otherParts[0] === key) {
            otherVal = otherParts[1].trim();
        }
    }
    
    let formattedContent = '<span class="diff-text">';
    formattedContent += `<span class="normal-part">${key}: </span>`;
    
    if (currentVal !== otherVal) {
        formattedContent += `<span class="diff-part">${currentVal}</span>`;
    } else {
        formattedContent += `<span class="normal-part">${currentVal}</span>`;
    }
    
    formattedContent += '</span>';
    return formattedContent;
}

// 格式化 F_HASH 內容
function formatFHashContent(currentValue, otherValue) {
    if (!currentValue.includes('F_HASH:')) return currentValue;
    
    const parts = currentValue.split('F_HASH:', 2);
    if (parts.length < 2) return currentValue;
    
    const currentHash = parts[1].trim();
    let otherHash = '';
    
    if (otherValue && otherValue.includes('F_HASH:')) {
        const otherParts = otherValue.split('F_HASH:', 2);
        if (otherParts.length >= 2) {
            otherHash = otherParts[1].trim();
        }
    }
    
    let formattedContent = '<span class="diff-text">';
    formattedContent += '<span class="normal-part">F_HASH: </span>';
    
    if (currentHash !== otherHash) {
        formattedContent += `<span class="diff-part">${currentHash}</span>`;
    } else {
        formattedContent += `<span class="normal-part">${currentHash}</span>`;
    }
    
    formattedContent += '</span>';
    return formattedContent;
}

// 格式化 F_Version.txt 內容
function formatFVersionContent(currentValue, otherValue) {
    if (!currentValue.startsWith('P_GIT_')) return currentValue;
    
    const currentParts = currentValue.split(';');
    const otherParts = otherValue ? otherValue.split(';') : [];
    
    let formattedContent = '<span class="diff-text">';
    
    currentParts.forEach((part, index) => {
        if (index > 0) formattedContent += ';';
        
        // 只有第4和第5部分（索引3和4）需要比較
        if ((index === 3 || index === 4) && 
            index < otherParts.length && 
            part !== otherParts[index]) {
            formattedContent += `<span class="diff-part">${part}</span>`;
        } else {
            formattedContent += `<span class="normal-part">${part}</span>`;
        }
    });
    
    formattedContent += '</span>';
    return formattedContent;
}

// 切換模態框內的頁籤 - 更新版本
function switchModalTab(sheetName, clickedBtn) {
    // 更新頁籤按鈕狀態
    const modal = document.getElementById('compareDetailsModal');
    modal.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    clickedBtn.classList.add('active');
    
    // 更新筆數顯示
    const count = clickedBtn.getAttribute('data-count') || '0';
    const modalCount = modal.querySelector('.modal-count');
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

// 生成比對表格 - 修正版，確保捲軸顯示
function generateCompareTable(sheetData, sheetName) {
    if (!sheetData || !sheetData.columns || !sheetData.data || sheetData.data.length === 0) {
        return '<div class="empty-message"><i class="fas fa-inbox"></i><p>此資料表沒有內容</p></div>';
    }
    
    let html = '<div class="table-wrapper">';
    html += '<div class="table-container">';
    html += `<table class="modal-table" id="table-${sheetName}">`;
    
    // 表頭（加入排序功能）
    html += '<thead><tr>';
    sheetData.columns.forEach((col, index) => {
        const columnInfo = getColumnInfo(col, sheetName);
        const sortable = col !== 'reason' && col !== 'problem'; // 某些欄位不需要排序
        
        html += `<th style="min-width: ${columnInfo.width};" 
                     class="${columnInfo.headerClass} ${sortable ? 'sortable' : ''}"
                     ${sortable ? `onclick="sortSheetTable('${sheetName}', ${index})"` : ''}>
                    ${columnInfo.text}
                 </th>`;
    });
    html += '</tr></thead>';
    
    // 表身
    html += '<tbody>';
    sheetData.data.forEach((row, index) => {
        html += generateCompareTableRow(row, sheetData.columns, sheetName, index);
    });
    html += '</tbody>';
    
    html += '</table>';
    html += '</div></div>';
    
    return html;
}

// 新增：排序資料表
function sortSheetTable(sheetName, columnIndex) {
    const table = document.getElementById(`table-${sheetName}`);
    if (!table) return;
    
    const tbody = table.querySelector('tbody');
    const headers = table.querySelectorAll('th');
    const currentHeader = headers[columnIndex];
    
    // 獲取當前排序狀態
    let sortOrder = currentHeader.classList.contains('sort-asc') ? 'desc' : 'asc';
    
    // 清除所有排序狀態
    headers.forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
    });
    
    // 設置新的排序狀態
    currentHeader.classList.add(`sort-${sortOrder}`);
    
    // 獲取所有行
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // 排序
    rows.sort((a, b) => {
        const aValue = a.cells[columnIndex].textContent.trim();
        const bValue = b.cells[columnIndex].textContent.trim();
        
        // 數字排序
        if (!isNaN(aValue) && !isNaN(bValue)) {
            return sortOrder === 'asc' ? 
                parseFloat(aValue) - parseFloat(bValue) : 
                parseFloat(bValue) - parseFloat(aValue);
        }
        
        // 文字排序
        if (sortOrder === 'asc') {
            return aValue.localeCompare(bValue);
        } else {
            return bValue.localeCompare(aValue);
        }
    });
    
    // 重新排列行
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

// 生成表格行 - 確保所有需要搜尋的內容都可被搜尋
function generateCompareTableRow(row, columns, sheetName, rowIndex) {
    let html = '<tr>';
    
    columns.forEach(col => {
        const value = row[col];
        const cellContent = formatCellContent(value, col, row, sheetName);
        const cellClass = getCellClass(col, value, sheetName);
        const columnInfo = getColumnInfo(col, sheetName);
        
        // 所有單元格都可以被搜尋
        html += `<td class="${cellClass}" style="min-width: ${columnInfo.width};">
                    ${cellContent}
                 </td>`;
    });
    
    html += '</tr>';
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
        // 其他欄位...
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

// 格式化單元格內容 - 保持原有功能
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
    
    // 版本差異處理
    if ((col === 'base_content' || col === 'compare_content') && sheetName === 'version_diff') {
        return formatVersionDiffContentWithColors(row, col);
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
    
    // 長內容處理
    if (col === 'org_content' && value && value.toString().length > 100) {
        const truncated = value.toString().substring(0, 100) + '...';
        return `<span title="${value.toString().replace(/"/g, '&quot;')}" style="cursor: help;">${truncated}</span>`;
    }
    
    return value;
}

// 獲取檔案圖標
function getFileIcon(fileName) {
    const lowerName = fileName.toLowerCase();
    
    if (lowerName.includes('manifest.xml')) return 'fa-file-code';
    if (lowerName.includes('version.txt')) return 'fa-file-lines';
    if (lowerName.includes('f_version.txt')) return 'fa-file-signature';
    if (lowerName.includes('.xml')) return 'fa-file-code';
    if (lowerName.includes('.txt')) return 'fa-file-alt';
    if (lowerName.includes('dprx_quickshow')) return 'fa-cube';
    if (lowerName.includes('bootcode')) return 'fa-microchip';
    if (lowerName.includes('emcu')) return 'fa-memory';
    if (lowerName.includes('audio_fw')) return 'fa-volume-up';
    if (lowerName.includes('video_fw')) return 'fa-video';
    if (lowerName.includes('tee')) return 'fa-shield-alt';
    if (lowerName.includes('bl31')) return 'fa-lock';
    
    return 'fa-file';
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
        console.log('Viewing detailed results for task_id:', currentTaskId); // 除錯用
        window.location.href = `/results/${currentTaskId}`;
    } else {
        utils.showNotification('無法取得任務 ID', 'error');
    }
}

// 匯出結果
async function exportResults(format) {
    if (!currentTaskId) {
        utils.showNotification('無任務 ID', 'error');
        return;
    }
    
    // 獲取當前選擇的情境
    const scenario = document.querySelector('input[name="scenario"]:checked').value;
    
    const endpoints = {
        excel: `/api/export-excel/${currentTaskId}`,
        html: `/api/export-html/${currentTaskId}`,
        zip: `/api/export-zip/${currentTaskId}`
    };
    
    // 如果是特定情境，傳遞情境參數
    if (scenario !== 'all') {
        endpoints.excel += `?scenario=${scenario}`;
        endpoints.html += `?scenario=${scenario}`;
        endpoints.zip += `?scenario=${scenario}`;
    }
    
    if (format === 'excel') {
        // Excel 匯出支援多維度
        try {
            const response = await fetch(endpoints.excel);
            
            if (!response.ok) {
                throw new Error('匯出失敗');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            
            // 檔名包含情境資訊
            let filename = scenario === 'all' ? 
                'all_scenarios_compare.xlsx' : 
                `${scenario}_compare.xlsx`;
            
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            utils.showNotification('Excel 檔案匯出完成', 'success');
            
        } catch (error) {
            console.error('Export error:', error);
            utils.showNotification('匯出失敗', 'error');
        }
    } else if (format === 'zip') {
        utils.showNotification('正在準備 ZIP 檔案，請稍候...', 'info');
        
        try {
            // 先檢查任務是否存在
            const checkResponse = await fetch(`/api/status/${currentTaskId}`);
            if (!checkResponse.ok) {
                utils.showNotification('找不到任務資料', 'error');
                return;
            }
            
            // 下載 ZIP 檔案
            const response = await fetch(endpoints[format]);
            
            if (!response.ok) {
                const error = await response.json();
                utils.showNotification(`下載失敗: ${error.error || '未知錯誤'}`, 'error');
                return;
            }
            
            // 檢查 content-type
            const contentType = response.headers.get('content-type');
            console.log('Content-Type:', contentType);
            
            if (!contentType || !contentType.includes('application/zip')) {
                utils.showNotification('回應格式錯誤，不是有效的 ZIP 檔案', 'error');
                return;
            }
            
            // 下載檔案
            const blob = await response.blob();
            console.log('Blob size:', blob.size);
            
            if (blob.size === 0) {
                utils.showNotification('下載的檔案為空', 'error');
                return;
            }
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `results_${currentTaskId}_${new Date().getTime()}.zip`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            utils.showNotification('ZIP 檔案下載完成', 'success');
            
        } catch (error) {
            console.error('Download error:', error);
            utils.showNotification('下載失敗', 'error');
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

function generateEmptyState(message = '暫無資料可顯示', showReloadBtn = true) {
    return `
        <div class="empty-state-container">
            <div class="empty-state-decoration">
                <div class="decoration-circle small"></div>
                <div class="decoration-circle medium"></div>
                <div class="decoration-circle large"></div>
            </div>
            
            <div class="empty-state-icon">
                <i class="fas fa-inbox"></i>
            </div>
            
            <h3 class="empty-state-title">暫無資料可顯示</h3>
            <p class="empty-state-desc">
                ${message || '此任務可能還在處理中，或尚未產生報表。'}
            </p>
            
            ${showReloadBtn ? `
                <button class="btn-reload-elegant" onclick="location.reload()">
                    <i class="fas fa-sync-alt"></i>
                    重新載入
                </button>
            ` : ''}
        </div>
    `;
}

// 原始的 loadRecentComparisons 函數（頁面初次載入時使用）
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
            const taskId = comp.task_id || comp.id || '';
            
            // 判斷是否為最新任務（第一筆）
            const isLatest = index === 0;
            
            html += `
                <div class="timeline-item ${isLatest ? 'latest-task' : ''}">
                    <div class="timeline-dot"></div>
                    <div class="timeline-content">
                        <div class="timeline-time">${formatTimeAgo(comp.timestamp)}</div>
                        <div class="timeline-title">
                            ${comp.scenario}
                            <span class="${statusColor} ml-2">
                                <i class="fas ${statusIcon}"></i>
                            </span>
                            ${isLatest ? '<span class="badge badge-info ml-2">最新</span>' : ''}
                        </div>
                        <div class="timeline-desc">
                            ${comp.modules} 個模組 · ${comp.duration || '< 1 分鐘'}
                        </div>
                        <button class="btn btn-small btn-primary mt-2" 
                                onclick="window.location.href='/results/${taskId}'">
                            查看結果
                        </button>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Load recent comparisons error:', error);
        const container = document.getElementById('comparisonTimeline');
        container.innerHTML = `
            <div class="timeline-empty">
                <i class="fas fa-exclamation-triangle fa-3x"></i>
                <p>載入歷史記錄時發生錯誤</p>
                <button class="btn btn-small btn-secondary mt-2" onclick="loadRecentComparisons()">
                    <i class="fas fa-sync-alt"></i> 重試
                </button>
            </div>
        `;
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
window.closeCompareModal = closeCompareModal;
window.switchCompareTab = switchCompareTab;
window.searchCompareContent = searchCompareContent;
window.searchTabContent = searchTabContent;
window.clearCompareSearch = clearCompareSearch;
window.clearTabSearch = clearTabSearch;
window.searchSingleSheetContent = searchSingleSheetContent;
window.clearSingleSheetSearch = clearSingleSheetSearch;
window.searchFailedModules = searchFailedModules;
window.clearFailedSearch = clearFailedSearch;
window.showFailedModulesModal = showFailedModulesModal;
window.sortFailedTable = sortFailedTable;