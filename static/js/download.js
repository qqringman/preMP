// 下載頁面 JavaScript - 北歐藍版本

// 頁面變數
let selectedSource = 'local';
let selectedFiles = [];
let downloadTaskId = null;
let currentServerPath = '/';
let serverSelectedFiles = [];
let serverFilesLoaded = false;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 立即將需要的函數綁定到 window
    window.selectSource = selectSource;
    window.switchTab = switchTab;
    window.toggleDepthControl = toggleDepthControl;
    window.removeFile = removeFile;
    window.navigateTo = navigateTo;
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
    
    // 初始化功能
    initializeTabs();
    initializeUploadAreas();
    initializeConfigToggles();
    updateDownloadButton();
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

// 切換標籤
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
    
    // 重置選擇
    if (tab === 'local') {
        selectedFiles = [];
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
    
    selectedFiles = excelFiles;
    displayLocalFiles();
    updateSelectedHint();
    updateDownloadButton();
}

// 顯示本地檔案列表
function displayLocalFiles() {
    const listEl = document.getElementById('localFileList');
    
    if (!listEl) return;
    
    if (selectedFiles.length === 0) {
        listEl.innerHTML = '';
        return;
    }
    
    let html = `
        <div class="selected-files-container">
            <div class="selected-files-header">
                <div class="selected-files-title">
                    <i class="fas fa-check-circle"></i>
                    已選擇 ${selectedFiles.length} 個檔案
                </div>
            </div>
            <div class="file-items">
    `;
    
    selectedFiles.forEach((file, index) => {
        html += `
            <div class="file-item">
                <div class="file-icon">
                    <i class="fas fa-file-excel"></i>
                </div>
                <div class="file-info">
                    <div class="file-name">${file.name}</div>
                    <div class="file-size">${utils.formatFileSize(file.size)}</div>
                </div>
                <button class="file-remove" onclick="removeFile(${index})" title="移除檔案">
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
    selectedFiles.splice(index, 1);
    displayLocalFiles();
    updateSelectedHint();
    updateDownloadButton();
}

// 載入伺服器檔案列表
async function loadServerFiles(path) {
    const browser = document.getElementById('serverBrowser');
    if (!browser) return;
    
    browser.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><span> 載入中...</span></div>';
    
    try {
        const response = await utils.apiRequest(`/api/browse-server?path=${encodeURIComponent(path)}`);
        currentServerPath = path;
        displayServerFiles(response);
        updateBreadcrumb(path);
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
    
    if (files.length === 0 && folders.length === 0) {
        browser.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-folder-open"></i>
                <p>此資料夾是空的</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="file-grid">';
    
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

// 切換伺服器檔案選擇
function toggleServerFile(path, name, size) {
    const index = serverSelectedFiles.findIndex(f => f.path === path);
    
    if (index === -1) {
        serverSelectedFiles.push({ path, name, size, type: 'server' });
    } else {
        serverSelectedFiles.splice(index, 1);
    }
    
    selectedFiles = serverSelectedFiles;
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
    
    let html = '<div class="selected-info"><h4>已選擇的檔案：</h4><div class="selected-chips">';
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
    selectedFiles = serverSelectedFiles;
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
    const hint = document.getElementById('selectedHint');
    const count = document.getElementById('selectedCount');
    
    if (selectedFiles.length > 0) {
        count.textContent = selectedFiles.length;
        hint.classList.remove('hidden');
    } else {
        hint.classList.add('hidden');
    }
}

// 更新下載按鈕狀態
function updateDownloadButton() {
    const btn = document.getElementById('downloadBtn');
    btn.disabled = selectedFiles.length === 0;
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

// 取得 SFTP 設定
function getSftpConfig() {
    const config = {};
    
    if (!document.getElementById('useDefaultConfig').checked) {
        config.host = document.getElementById('sftpHost').value;
        config.port = parseInt(document.getElementById('sftpPort').value) || 22;
        config.username = document.getElementById('sftpUsername').value;
        config.password = document.getElementById('sftpPassword').value;
        
        // 驗證必要欄位
        if (!config.host || !config.username || !config.password) {
            throw new Error('請填寫完整的 SFTP 設定');
        }
    }
    
    return config;
}

// 修改開始下載函數
async function startDownload() {
    if (selectedFiles.length === 0) {
        utils.showNotification('請先選擇檔案', 'error');
        return;
    }
    
    try {
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
        
        if (selectedSource === 'local') {
            // 本地檔案模式
            const uploadedFiles = [];
            
            addLog('開始上傳 Excel 檔案...', 'info');
            
            for (const file of selectedFiles) {
                try {
                    addLog(`上傳檔案: ${file.name}`, 'info');
                    const result = await utils.uploadFile(file);
                    uploadedFiles.push(result.filepath);
                    addLog(`檔案 ${file.name} 上傳成功`, 'success');
                } catch (error) {
                    addLog(`上傳檔案 ${file.name} 失敗: ${error.message}`, 'error');
                    utils.showNotification(`上傳檔案 ${file.name} 失敗`, 'error');
                    resetDownloadForm();
                    return;
                }
            }
            
            requestData.excel_file = uploadedFiles[0];
        } else {
            // 伺服器檔案模式
            const excelFile = selectedFiles.find(f => f.name.endsWith('.xlsx'));
            if (excelFile) {
                requestData.excel_file = excelFile.path;
                addLog(`使用伺服器檔案: ${excelFile.name}`, 'info');
            }
        }
        
        if (!requestData.excel_file) {
            utils.showNotification('請至少選擇一個 Excel 檔案', 'error');
            resetDownloadForm();
            return;
        }
        
        addLog('正在初始化下載任務...', 'info');
        
        // 發送下載請求
        const response = await utils.apiRequest('/api/download', {
            method: 'POST',
            body: JSON.stringify(requestData)
        });
        
        downloadTaskId = response.task_id;
        
        addLog(`任務 ID: ${downloadTaskId}`, 'info');
        addLog('開始下載檔案...', 'downloading');
        
        // 如果有 socket 連接，加入任務房間
        if (window.socket) {
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

// 添加日誌
function addLog(message, type = 'info') {
    const log = document.getElementById('downloadLog');
    if (!log) return;
    
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `
        <span class="log-time">${new Date().toLocaleTimeString('zh-TW')}</span>
        <span class="log-icon">
            <i class="fas ${getLogIcon(type)}"></i>
        </span>
        <span class="log-message">${message}</span>
    `;
    
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

// 取得日誌圖示
function getLogIcon(type) {
    const icons = {
        'info': 'fa-info-circle',
        'success': 'fa-check-circle',
        'warning': 'fa-exclamation-triangle',
        'error': 'fa-times-circle',
        'downloading': 'fa-download',
        'completed': 'fa-check'
    };
    return icons[type] || icons.info;
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
    
    // 生成摘要
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
    const tree = buildTreeHTML(structure, 'downloads', '');
    document.getElementById('folderTree').innerHTML = tree;
}

// 建立樹狀結構 HTML
function buildTreeHTML(node, name, path) {
    const fullPath = path ? `${path}/${name}` : name;
    
    if (typeof node === 'string') {
        // 檔案節點
        return `
            <div class="tree-node">
                <div class="tree-node-content" data-path="${fullPath}">
                    <i class="tree-icon tree-file fas fa-file"></i>
                    <span class="tree-name">${name}</span>
                    <div class="tree-actions">
                        <button class="tree-action" onclick="previewFile('${fullPath}')" title="預覽">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="tree-action" onclick="downloadFile('${fullPath}')" title="下載">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    
    // 資料夾節點
    let html = `
        <div class="tree-node">
            <div class="tree-node-content folder" onclick="toggleFolder(this)">
                <i class="tree-icon tree-folder fas fa-folder"></i>
                <span class="tree-name">${name}/</span>
            </div>
            <div class="tree-children">
    `;
    
    for (const [key, value] of Object.entries(node)) {
        html += buildTreeHTML(value, key, fullPath);
    }
    
    html += '</div></div>';
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
    
    content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> 載入中...</div>';
    modal.classList.remove('hidden');
    
    try {
        const response = await utils.apiRequest(`/api/preview-file?path=${encodeURIComponent(path)}`);
        content.innerHTML = `<pre>${response.content}</pre>`;
    } catch (error) {
        content.innerHTML = `<div class="error">無法預覽檔案</div>`;
    }
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