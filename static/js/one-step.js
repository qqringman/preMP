// 一步到位頁面 JavaScript - 與下載頁面共用相同的檔案選擇邏輯

let selectedFile = null;
let currentTaskId = null;
let selectedServerFiles = [];

// 初始化頁面
document.addEventListener('DOMContentLoaded', () => {
    initializeUpload();
    initializeSftpConfig();
    initializeEventListeners();
    updateStepIndicator('upload', 'active');    
});

// 切換檔案來源標籤
function switchTab(tab) {
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
    
    // 如果切換到伺服器標籤，載入檔案列表
    if (tab === 'server') {
        loadServerFiles();
    }
}

// 初始化上傳功能
function initializeUpload() {
    const uploadArea = document.getElementById('localUploadArea');
    const fileInput = document.getElementById('localFileInput');
    
    // 拖放事件
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragging');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragging');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragging');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });
    
    // 點擊上傳
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });
    
    // 檔案選擇
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
}

// 處理檔案選擇
async function handleFileSelect(file) {
    // 驗證檔案類型
    if (!file.name.endsWith('.xlsx')) {
        utils.showNotification('請選擇 Excel (.xlsx) 檔案', 'error');
        return;
    }
    
    // 驗證檔案大小
    if (file.size > 16 * 1024 * 1024) {
        utils.showNotification('檔案大小不能超過 16MB', 'error');
        return;
    }
    
    // 顯示檔案列表
    displayLocalFile(file);
    
    // 上傳檔案
    try {
        const result = await utils.uploadFile(file);
        selectedFile = result.filepath;
        checkExecuteButton();
    } catch (error) {
        console.error('Upload error:', error);
        removeLocalFile();
    }
}

// 顯示本地檔案
function displayLocalFile(file) {
    const fileList = document.getElementById('localFileList');
    fileList.classList.remove('hidden');
    
    fileList.innerHTML = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h3 class="file-list-title">
                    <i class="fas fa-file-excel"></i> 已選擇的檔案
                </h3>
                <span class="file-count-badge">1 個檔案</span>
            </div>
            <div class="file-items">
                <div class="file-item-card">
                    <div class="file-icon-wrapper">
                        <i class="fas fa-file-excel"></i>
                    </div>
                    <div class="file-details">
                        <div class="file-name">${file.name}</div>
                        <div class="file-meta">
                            <span>Excel 檔案</span>
                            <span class="file-size">${utils.formatFileSize(file.size)}</span>
                        </div>
                    </div>
                    <button class="btn-remove-file" onclick="removeLocalFile()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
}

// 移除本地檔案
function removeLocalFile() {
    selectedFile = null;
    document.getElementById('localFileList').classList.add('hidden');
    document.getElementById('localFileInput').value = '';
    checkExecuteButton();
}

// 載入伺服器檔案
async function loadServerFiles() {
    const path = document.getElementById('serverPathInput').value || '/home/vince_lin/ai/preMP';
    const browserContent = document.getElementById('serverBrowser');
    
    browserContent.innerHTML = `
        <div class="loading">
            <i class="fas fa-spinner fa-spin fa-3x"></i>
            <p>載入中...</p>
        </div>
    `;
    
    try {
        const result = await utils.apiRequest(`/api/browse-server?path=${encodeURIComponent(path)}`);
        displayServerFiles(result);
    } catch (error) {
        browserContent.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle fa-3x"></i>
                <p>無法載入檔案列表</p>
                <p class="text-muted">${error.message}</p>
                <button class="btn btn-primary" onclick="loadServerFiles()">重試</button>
            </div>
        `;
    }
}

// 顯示伺服器檔案
function displayServerFiles(result) {
    const browserContent = document.getElementById('serverBrowser');
    
    if (!result.folders && !result.files) {
        browserContent.innerHTML = `
            <div class="empty-message">
                <i class="fas fa-folder-open fa-3x"></i>
                <p>此目錄是空的</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="file-grid">';
    
    // 顯示資料夾
    if (result.folders) {
        result.folders.forEach(folder => {
            html += `
                <div class="file-item folder" ondblclick="navigateToFolder('${folder.path}')">
                    <i class="fas fa-folder"></i>
                    <div class="file-name">${folder.name}</div>
                </div>
            `;
        });
    }
    
    // 顯示檔案（只顯示 Excel 檔案）
    if (result.files) {
        result.files.forEach(file => {
            const isSelected = selectedServerFiles.some(f => f.path === file.path);
            html += `
                <div class="file-item file ${isSelected ? 'selected' : ''}" 
                     onclick="toggleServerFile('${file.path}', '${file.name}', ${file.size})">
                    ${isSelected ? '<div class="check-icon"><i></i></div>' : ''}
                    <i class="fas fa-file-excel"></i>
                    <div class="file-name">${file.name}</div>
                    <div class="file-size">${utils.formatFileSize(file.size)}</div>
                </div>
            `;
        });
    }
    
    html += '</div>';
    browserContent.innerHTML = html;
}

// 切換伺服器檔案選擇
function toggleServerFile(path, name, size) {
    const index = selectedServerFiles.findIndex(f => f.path === path);
    
    // 一步到位只能選擇一個檔案
    if (index === -1) {
        selectedServerFiles = [{path, name, size}];
    } else {
        selectedServerFiles = [];
    }
    
    updateServerFileSelection();
    checkExecuteButton();
}

// 更新伺服器檔案選擇顯示
function updateServerFileSelection() {
    const container = document.getElementById('serverSelectedFiles');
    
    if (selectedServerFiles.length === 0) {
        container.classList.add('hidden');
        selectedFile = null;
        return;
    }
    
    container.classList.remove('hidden');
    selectedFile = selectedServerFiles[0].path; // 使用第一個選擇的檔案
    
    let html = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h3 class="file-list-title">
                    <i class="fas fa-server"></i> 已選擇的伺服器檔案
                </h3>
                <span class="file-count-badge">1 個檔案</span>
            </div>
            <div class="file-items">
    `;
    
    const file = selectedServerFiles[0];
    html += `
        <div class="file-item-card">
            <div class="file-icon-wrapper">
                <i class="fas fa-file-excel"></i>
            </div>
            <div class="file-details">
                <div class="file-name">${file.name}</div>
                <div class="file-meta">
                    <span class="file-path">
                        <i class="fas fa-folder"></i> ${file.path}
                    </span>
                    <span class="file-size">${utils.formatFileSize(file.size)}</span>
                </div>
            </div>
            <button class="btn-remove-file" onclick="removeServerFile('${file.path}')">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    html += '</div></div>';
    container.innerHTML = html;
    
    // 重新載入檔案列表以更新選中狀態
    loadServerFiles();
}

// 移除伺服器檔案
function removeServerFile(path) {
    selectedServerFiles = [];
    updateServerFileSelection();
}

// 導航到資料夾
function navigateToFolder(path) {
    document.getElementById('serverPathInput').value = path;
    loadServerFiles();
}

// 前往指定路徑
function goToPath() {
    loadServerFiles();
}

// 重新整理伺服器檔案
function refreshServerFiles() {
    loadServerFiles();
}

// 初始化 SFTP 設定
function initializeSftpConfig() {
    const useDefaultConfig = document.getElementById('useDefaultConfig');
    const customConfig = document.getElementById('customConfig');
    
    useDefaultConfig.addEventListener('change', (e) => {
        if (e.target.checked) {
            customConfig.classList.add('disabled');
        } else {
            customConfig.classList.remove('disabled');
        }
    });
}

// 初始化事件監聽器
function initializeEventListeners() {
    // 監聽任務進度
    document.addEventListener('task-progress', (e) => {
        const data = e.detail;
        if (data.task_id === currentTaskId) {
            updateProgress(data);
        }
    });
}

// 檢查執行按鈕狀態
function checkExecuteButton() {
    const executeBtn = document.getElementById('executeBtn');
    executeBtn.disabled = !selectedFile;
    
    // 更新步驟狀態
    if (selectedFile) {
        updateStepIndicator('upload', 'completed');
        updateStepIndicator('config', 'active');
    } else {
        updateStepIndicator('upload', 'active');
        updateStepIndicator('config', 'pending');
    }
}

// 加入步驟指示器更新函數
function updateStepIndicator(step, status) {
    const stepElement = document.getElementById(`step-${step}`);
    if (!stepElement) return;
    
    // 移除所有狀態類別
    stepElement.classList.remove('active', 'completed');
    
    // 添加新狀態
    if (status === 'active') {
        stepElement.classList.add('active');
    } else if (status === 'completed') {
        stepElement.classList.add('completed');
    }
}

// 執行一步到位處理
async function executeOneStep() {
    if (!selectedFile) {
        utils.showNotification('請先選擇 Excel 檔案', 'error');
        return;
    }

    // 更新步驟狀態
    updateStepIndicator('upload', 'completed');
    updateStepIndicator('config', 'completed');
    updateStepIndicator('process', 'active');

    // 取得 SFTP 設定
    const sftpConfig = {};
    if (!document.getElementById('useDefaultConfig').checked) {
        sftpConfig.host = document.getElementById('sftpHost').value;
        sftpConfig.port = parseInt(document.getElementById('sftpPort').value) || 22;
        sftpConfig.username = document.getElementById('sftpUsername').value;
        sftpConfig.password = document.getElementById('sftpPassword').value;
        
        // 驗證必要欄位
        if (!sftpConfig.host || !sftpConfig.username || !sftpConfig.password) {
            utils.showNotification('請填寫完整的 SFTP 設定', 'error');
            return;
        }
    }
    
    // 隱藏表單，顯示進度
    document.getElementById('mainForm').classList.add('hidden');
    document.getElementById('progressContainer').classList.remove('hidden');
    
    // 發送請求
    try {
        const response = await utils.apiRequest('/api/one-step', {
            method: 'POST',
            body: JSON.stringify({
                excel_file: selectedFile,
                sftp_config: sftpConfig
            })
        });
        
        currentTaskId = response.task_id;
        
        // 加入任務房間
        if (socket) {
            socket.emit('join_task', { task_id: currentTaskId });
        }
        
        // 開始輪詢狀態（備用方案）
        pollTaskStatus();
        
    } catch (error) {
        console.error('Execute error:', error);
        utils.showNotification('執行失敗：' + error.message, 'error');
        resetToForm();
    }
}

// 更新進度
function updateProgress(data) {
    const { progress, status, message } = data;
    
    // 更新進度條
    document.getElementById('progressFill').style.width = `${progress}%`;
    document.getElementById('progressText').textContent = `${progress}%`;
    
    // 更新階段狀態
    if (status === 'downloading' || status === 'downloaded') {
        updateStageStatus('download', status === 'downloaded' ? 'completed' : 'active');
    } else if (status === 'comparing' || status === 'compared') {
        updateStageStatus('download', 'completed');
        updateStageStatus('compare', status === 'compared' ? 'completed' : 'active');
    } else if (status === 'packaging' || status === 'completed') {
        updateStageStatus('download', 'completed');
        updateStageStatus('compare', 'completed');
        updateStageStatus('package', status === 'completed' ? 'completed' : 'active');
    }
    
    // 添加日誌
    addLogEntry(message);
    
    // 處理完成或錯誤
    if (status === 'completed') {
        handleComplete(data.results);
    } else if (status === 'error') {
        handleError(message);
    }
}

// 更新階段狀態
function updateStageStatus(stage, status) {
    const stageElement = document.getElementById(`stage-${stage}`);
    if (!stageElement) return;
    
    const statusElement = stageElement.querySelector('.stage-status');
    
    stageElement.classList.remove('active', 'completed');
    
    if (status === 'active') {
        stageElement.classList.add('active');
        statusElement.textContent = '處理中...';
    } else if (status === 'completed') {
        stageElement.classList.add('completed');
        statusElement.textContent = '完成';
    }
}

// 添加日誌條目
function addLogEntry(message) {
    const logContent = document.getElementById('logContent');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    
    const time = new Date().toLocaleTimeString('zh-TW');
    entry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-icon"><i class="fas fa-info-circle"></i></span>
        <span class="log-message">${message}</span>
    `;
    
    logContent.appendChild(entry);
    logContent.scrollTop = logContent.scrollHeight;
}

// 處理完成
function handleComplete(results) {

    // 更新步驟狀態
    updateStepIndicator('process', 'completed');
    updateStepIndicator('complete', 'completed');
        
    // 顯示結果
    document.getElementById('progressContainer').classList.add('hidden');
    document.getElementById('resultContainer').classList.remove('hidden');
    
    // 生成結果摘要
    const summaryHtml = generateResultSummary(results);
    document.getElementById('resultSummary').innerHTML = summaryHtml;
    
    utils.showNotification('所有處理已完成！', 'success');
}

// 處理錯誤
function handleError(message) {
    utils.showNotification(`處理失敗：${message}`, 'error');
    
    // 顯示錯誤狀態
    document.getElementById('progressContainer').innerHTML = `
        <div class="error-container">
            <i class="fas fa-exclamation-circle"></i>
            <h2>處理失敗</h2>
            <p>${message}</p>
            <button class="btn btn-primary" onclick="resetToForm()">
                <i class="fas fa-redo"></i> 重新開始
            </button>
        </div>
    `;
}

// 生成結果摘要
function generateResultSummary(results) {
    const compareResults = results.compare_results || {};
    
    let html = '<div class="summary-grid">';
    
    // 下載統計
    if (results.download_report) {
        html += `
            <div class="summary-item">
                <div class="summary-icon">
                    <i class="fas fa-download"></i>
                </div>
                <div class="summary-content">
                    <div class="summary-label">下載報表</div>
                    <div class="summary-value">
                        <a href="/api/download-file/${results.download_report}" class="link">
                            查看報表
                        </a>
                    </div>
                </div>
            </div>
        `;
    }
    
    // 比對統計
    if (compareResults.master_vs_premp) {
        html += `
            <div class="summary-item">
                <div class="summary-icon">
                    <i class="fas fa-code-branch"></i>
                </div>
                <div class="summary-content">
                    <div class="summary-label">Master vs PreMP</div>
                    <div class="summary-value">${compareResults.master_vs_premp.success} 個模組</div>
                </div>
            </div>
        `;
    }
    
    if (compareResults.premp_vs_wave) {
        html += `
            <div class="summary-item">
                <div class="summary-icon">
                    <i class="fas fa-water"></i>
                </div>
                <div class="summary-content">
                    <div class="summary-label">PreMP vs Wave</div>
                    <div class="summary-value">${compareResults.premp_vs_wave.success} 個模組</div>
                </div>
            </div>
        `;
    }
    
    if (compareResults.wave_vs_backup) {
        html += `
            <div class="summary-item">
                <div class="summary-icon">
                    <i class="fas fa-database"></i>
                </div>
                <div class="summary-content">
                    <div class="summary-label">Wave vs Backup</div>
                    <div class="summary-value">${compareResults.wave_vs_backup.success} 個模組</div>
                </div>
            </div>
        `;
    }
    
    // 無法比對
    if (compareResults.failed > 0) {
        html += `
            <div class="summary-item error">
                <div class="summary-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="summary-content">
                    <div class="summary-label">無法比對</div>
                    <div class="summary-value">${compareResults.failed} 個模組</div>
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

// 查看結果
function viewResults() {
    if (currentTaskId) {
        window.location.href = `/results/${currentTaskId}`;
    }
}

// 下載所有檔案
function downloadAll() {
    if (currentTaskId) {
        window.location.href = `/api/export-zip/${currentTaskId}`;
    }
}

// 開始新的處理
function startNew() {
    resetToForm();
    currentTaskId = null;
    selectedFile = null;
    selectedServerFiles = [];
    removeLocalFile();
}

// 重置到表單
function resetToForm() {
    document.getElementById('mainForm').classList.remove('hidden');
    document.getElementById('progressContainer').classList.add('hidden');
    document.getElementById('resultContainer').classList.add('hidden');
    
    // 清空日誌
    document.getElementById('logContent').innerHTML = `
        <div class="log-entry">
            <span class="log-time">--:--:--</span>
            <span class="log-icon"><i class="fas fa-info-circle"></i></span>
            <span class="log-message">等待開始...</span>
        </div>
    `;
    
    // 重置進度
    document.getElementById('progressFill').style.width = '0%';
    document.getElementById('progressText').textContent = '0%';
}

// 輪詢任務狀態（備用方案）
async function pollTaskStatus() {
    if (!currentTaskId) return;
    
    try {
        const status = await utils.apiRequest(`/api/status/${currentTaskId}`);
        
        if (status.status !== 'not_found') {
            updateProgress(status);
        }
        
        // 如果任務未完成，繼續輪詢
        if (status.status !== 'completed' && status.status !== 'error') {
            setTimeout(pollTaskStatus, 1000);
        }
    } catch (error) {
        console.error('Poll status error:', error);
    }
}

// 匯出到全域
window.switchTab = switchTab;
window.removeLocalFile = removeLocalFile;
window.toggleServerFile = toggleServerFile;
window.removeServerFile = removeServerFile;
window.navigateToFolder = navigateToFolder;
window.goToPath = goToPath;
window.refreshServerFiles = refreshServerFiles;
window.executeOneStep = executeOneStep;
window.viewResults = viewResults;
window.downloadAll = downloadAll;
window.startNew = startNew;
window.resetToForm = resetToForm;