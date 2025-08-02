// 下載頁面 JavaScript - 修正版（含路徑輸入功能）

// 頁面變數
let selectedSource = 'local';
let selectedFiles = [];  // 當前選擇的檔案
let localSelectedFiles = []; // 本地選擇的檔案
let serverSelectedFiles = []; // 伺服器選擇的檔案  
let downloadTaskId = null;
let currentServerPath = '/home/vince_lin/ai/preMP'; // 使用 config.py 的預設路徑
let serverFilesLoaded = false;
let pathInputTimer = null;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 綁定函數到 window
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
    
    // 初始化功能
    initializeTabs();
    initializeUploadAreas();
    initializeConfigToggles();
    initializePathInput(); // 新增
    updateDownloadButton();
    
    // 修正預設設定開關
    const useDefaultConfig = document.getElementById('useDefaultConfig');
    if (useDefaultConfig) {
        useDefaultConfig.addEventListener('change', (e) => {
            toggleSftpConfig(e.target.checked);
        });
        // 初始化狀態
        toggleSftpConfig(useDefaultConfig.checked);
    }
});

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

// 切換標籤 - 修正版
function switchTab(tab) {
    selectedSource = tab;
    
    // 更新標籤按鈕狀態
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.currentTarget.classList.add('active');
    
    // 更新標籤內容
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tab}-tab`).classList.add('active');
    
    // 如果切換到伺服器，載入檔案列表
    if (tab === 'server' && !serverFilesLoaded) {
        loadServerFiles(currentServerPath);
        serverFilesLoaded = true;
    }
    
    // 根據標籤設定當前的檔案選擇
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

// 處理本地檔案
function handleLocalFiles(files) {
    const excelFiles = files.filter(f => f.name.endsWith('.xlsx'));
    
    if (excelFiles.length === 0) {
        utils.showNotification('請選擇 Excel (.xlsx) 檔案', 'error');
        return;
    }
    
    localSelectedFiles = excelFiles;  // 儲存到本地選擇
    selectedFiles = excelFiles;       // 更新當前選擇
    displayLocalFiles();
    updateSelectedHint();
    updateDownloadButton();
}

// 使用真實檔案名稱顯示
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
        html += `
            <div class="file-item-card">
                <div class="file-icon-wrapper">
                    <i class="fas fa-file-excel"></i>
                </div>
                <div class="file-details">
                    <div class="file-name" title="${file.name}">${file.name}</div>
                    <div class="file-meta">
                        <span class="file-size">${fileSize}</span>
                        <span class="file-type">Excel 檔案</span>
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
            
            // 顯示 Excel 檔案
            files.filter(f => f.name.endsWith('.xlsx')).forEach(file => {
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
    
    const icon = type === 'folder' ? 'fa-folder' : 'fa-file-excel';
    const typeText = type === 'folder' ? '資料夾' : 'Excel 檔案';
    
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

// 改進的載入伺服器檔案
async function loadServerFiles(path) {
    const browser = document.getElementById('serverBrowser');
    if (!browser) return;
    
    browser.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><span> 載入中...</span></div>';
    
    try {
        const response = await utils.apiRequest(`/api/browse-server?path=${encodeURIComponent(path)}`);
        currentServerPath = path;
        displayServerFiles(response);
        updateBreadcrumb(path);
        
        // 更新路徑輸入框
        const pathInput = document.getElementById('serverPathInput');
        if (pathInput) {
            pathInput.value = path;
        }
    } catch (error) {
        browser.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                <p>無法載入檔案列表</p>
                <p class="text-muted">${error.message}</p>
                <button class="btn-retry" onclick="loadServerFiles('${path}')">
                    <i class="fas fa-redo"></i> 重試
                </button>
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
    
    // 顯示 Excel 檔案
    files.filter(f => f.name.endsWith('.xlsx')).forEach(file => {
        const isSelected = serverSelectedFiles.some(f => f.path === file.path);
        html += `
            <div class="file-item file ${isSelected ? 'selected' : ''}" 
                 onclick="toggleServerFile('${file.path}', '${file.name}', ${file.size})">
                <i class="fas fa-file-excel"></i>
                <span class="file-name">${file.name}</span>
                <span class="file-size">${utils.formatFileSize(file.size)}</span>
                ${isSelected ? '<i class="fas fa-check-circle check-icon"></i>' : ''}
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

// 顯示已選擇的伺服器檔案
function displaySelectedServerFiles() {
    const container = document.getElementById('serverSelectedFiles');
    if (!container) return;
    
    if (serverSelectedFiles.length === 0) {
        container.innerHTML = '';
        return;
    }
    
    let html = '<div class="selected-info"><h4><i class="fas fa-check-circle"></i> 已選擇的檔案</h4><div class="selected-chips">';
    serverSelectedFiles.forEach((file, index) => {
        html += `
            <div class="file-chip">
                <i class="fas fa-file-excel"></i>
                <span>${file.name}</span>
                <button class="chip-remove" onclick="removeServerFile(${index})">
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

// 修正開始下載函數
async function startDownload() {
    // 根據當前標籤決定使用哪些檔案
    const currentFiles = selectedSource === 'local' ? localSelectedFiles : serverSelectedFiles;
    
    if (currentFiles.length === 0) {
        utils.showNotification('請先選擇檔案', 'error');
        return;
    }
    
    try {
        // 取得 SFTP 設定
        const sftpConfig = getSftpConfig();
        
        // 隱藏表單，顯示進度
        document.getElementById('downloadForm').classList.add('hidden');
        document.getElementById('downloadProgress').classList.remove('hidden');
        
        // 清除之前的日誌
        clearLog();
        
        // 準備請求數據
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
            // 本地檔案模式 - 上傳檔案
            const file = localSelectedFiles[0]; // 只處理第一個檔案
            
            addLog('正在上傳 Excel 檔案...', 'info');
            
            try {
                const uploadResult = await utils.uploadFile(file);
                
                // 檢查返回的數據結構
                if (!uploadResult.filepath) {
                    throw new Error('上傳檔案失敗：返回數據格式錯誤');
                }
                
                requestData.excel_file = uploadResult.filepath;
                addLog(`檔案 ${file.name} 上傳成功`, 'success');
                
            } catch (error) {
                addLog(`上傳檔案失敗: ${error.message}`, 'error');
                utils.showNotification('上傳檔案失敗', 'error');
                resetDownloadForm();
                return;
            }
        } else {
            // 伺服器檔案模式
            const excelFile = serverSelectedFiles.find(f => f.name.endsWith('.xlsx'));
            if (!excelFile) {
                utils.showNotification('請選擇一個 Excel 檔案', 'error');
                resetDownloadForm();
                return;
            }
            requestData.excel_file = excelFile.path;
            addLog(`使用伺服器檔案: ${excelFile.name}`, 'info');
        }
        
        addLog('正在初始化下載任務...', 'info');
        
        // 發送下載請求
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
        
        // 如果有 socket 連接，加入任務房間
        if (window.socket && socket.connected) {
            socket.emit('join_task', { task_id: downloadTaskId });
        }
        
        // 監聽進度更新
        document.addEventListener('task-progress', handleDownloadProgress);
        
        // 開始輪詢狀態
        pollDownloadStatus();
        
    } catch (error) {
        console.error('Download error:', error);
        addLog(`下載失敗: ${error.message}`, 'error');
        utils.showNotification(error.message || '下載失敗', 'error');
        resetDownloadForm();
    }
}

// 處理下載進度
function handleDownloadProgress(event) {
    const data = event.detail;
    if (data.task_id === downloadTaskId) {
        updateDownloadProgress(data);
    }
}

// 更新下載進度
function updateDownloadProgress(data) {
    const { progress, status, message, stats } = data;
    
    // 更新進度條
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    if (progressFill && progressText) {
        progressFill.style.width = `${progress}%`;
        progressText.textContent = `${Math.round(progress)}%`;
    }
    
    // 更新統計
    if (stats) {
        updateStats(stats);
    }
    
    // 添加日誌
    addLog(message, status);
    
    // 處理完成或錯誤
    if (status === 'completed') {
        showDownloadResults(data.results);
    } else if (status === 'error') {
        utils.showNotification(`下載失敗：${message}`, 'error');
        resetDownloadForm();
    }
}

// 更新統計數據
function updateStats(stats) {
    const elements = {
        totalFiles: stats.total || 0,
        downloadedFiles: stats.downloaded || 0,
        skippedFiles: stats.skipped || 0,
        failedFiles: stats.failed || 0
    };
    
    for (const [id, value] of Object.entries(elements)) {
        const element = document.getElementById(id);
        if (element) {
            animateValue(element, parseInt(element.textContent) || 0, value);
        }
    }
}

// 數值動畫
function animateValue(element, start, end) {
    const duration = 500;
    const range = end - start;
    const increment = range / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
            current = end;
            clearInterval(timer);
        }
        element.textContent = Math.round(current);
    }, 16);
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

// 顯示下載結果
function showDownloadResults(results) {
    const downloadProgress = document.getElementById('downloadProgress');
    const downloadResults = document.getElementById('downloadResults');
    
    if (downloadProgress) {
        downloadProgress.classList.add('hidden');
    }
    
    if (downloadResults) {
        downloadResults.classList.remove('hidden');
    } else {
        console.error('downloadResults element not found');
        return;
    }
    
    // 生成摘要 - 使用北歐藍配色
    const stats = results.stats || {};
    const summary = `
        <div class="summary-grid">
            <div class="summary-item">
                <i class="fas fa-check-circle text-success"></i>
                <div class="summary-content">
                    <div class="summary-value">${stats.downloaded || 0}</div>
                    <div class="summary-label">成功下載</div>
                </div>
            </div>
            <div class="summary-item">
                <i class="fas fa-forward text-info"></i>
                <div class="summary-content">
                    <div class="summary-value">${stats.skipped || 0}</div>
                    <div class="summary-label">跳過檔案</div>
                </div>
            </div>
            ${stats.failed > 0 ? `
                <div class="summary-item">
                    <i class="fas fa-times-circle text-danger"></i>
                    <div class="summary-content">
                        <div class="summary-value">${stats.failed}</div>
                        <div class="summary-label">下載失敗</div>
                    </div>
                </div>
            ` : ''}
            <div class="summary-item">
                <i class="fas fa-folder-tree text-info"></i>
                <div class="summary-content">
                    <div class="summary-value">${stats.total || 0}</div>
                    <div class="summary-label">總檔案數</div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('resultSummary').innerHTML = summary;
    
    // 生成資料夾樹
    if (results.folder_structure) {
        generateFolderTree(results.folder_structure);
    }
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
    
    // 如果是字串，表示是檔案（包含完整路徑）
    if (typeof node === 'string') {
        const fileName = name;
        const filePath = node; // node 就是完整路徑
        
        html = `
            <div class="tree-node">
                <div class="tree-node-content file" data-path="${filePath}" ondblclick="previewFile('${filePath}')">
                    <i class="tree-icon tree-file fas fa-file"></i>
                    <span class="tree-name">${fileName}</span>
                    <div class="tree-actions">
                        <button class="tree-action" onclick="event.stopPropagation(); previewFile('${filePath}')" title="預覽">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="tree-action" onclick="event.stopPropagation(); downloadFile('${filePath}')" title="下載">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    } else if (typeof node === 'object') {
        // 資料夾
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
        
        // 遞迴處理子項目
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

// 預覽檔案
async function previewFile(path) {
    const modal = document.getElementById('filePreviewModal');
    const content = document.getElementById('previewContent');
    const filename = document.getElementById('previewFilename');
    
    // 顯示檔名
    const fileName = path.split('/').pop();
    if (filename) {
        filename.textContent = fileName;
    }
    
    content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> 載入中...</div>';
    modal.classList.remove('hidden');
    
    try {
        const response = await utils.apiRequest(`/api/preview-file?path=${encodeURIComponent(path)}`);
        
        // 根據檔案類型處理內容
        if (response.type === 'xml') {
            // XML語法高亮
            let formattedContent = response.content
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/(&lt;\/?)(\w+)(.*?)(&gt;)/g, 
                    '$1<span class="xml-tag">$2</span>$3$4')
                .replace(/(\w+)="([^"]*)"/g, 
                    '<span class="xml-attr">$1</span>="<span class="xml-value">$2</span>"');
            
            content.innerHTML = `<code class="xml">${formattedContent}</code>`;
            content.classList.add('xml');
        } else {
            content.textContent = response.content;
            content.classList.remove('xml');
        }
    } catch (error) {
        content.innerHTML = `<div class="error">無法預覽檔案：${error.message}</div>`;
    }
}

// 複製預覽內容
function copyPreviewContent() {
    const content = document.getElementById('previewContent');
    const text = content.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        utils.showNotification('內容已複製到剪貼簿', 'success');
    }).catch(() => {
        utils.showNotification('複製失敗', 'error');
    });
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
    document.getElementById('filePreviewModal').classList.add('hidden');
}

// 輪詢下載狀態
async function pollDownloadStatus() {
    if (!downloadTaskId) return;
    
    try {
        const status = await utils.apiRequest(`/api/status/${downloadTaskId}`);
        
        if (status.status !== 'not_found') {
            updateDownloadProgress(status);
        }
        
        // 如果任務未完成，繼續輪詢
        if (status.status !== 'completed' && status.status !== 'error') {
            setTimeout(pollDownloadStatus, 1000);
        } else {
            // 移除事件監聽
            document.removeEventListener('task-progress', handleDownloadProgress);
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