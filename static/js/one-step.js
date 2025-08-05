// 一步到位頁面 JavaScript - 更新伺服器瀏覽功能

let selectedFile = null;
let currentTaskId = null;
let selectedServerFiles = [];
let currentServerPath = '/home/vince_lin/ai/preMP';
let serverFilesLoaded = false;
let pathInputTimer = null;

// 初始化頁面
document.addEventListener('DOMContentLoaded', () => {
    initializeUpload();
    initializeSftpConfig();
    initializeEventListeners();
    initializePathInput();
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
    if (tab === 'server' && !serverFilesLoaded) {
        loadServerFiles(currentServerPath);
        serverFilesLoaded = true;
    }
}

// 初始化路徑輸入功能 (與 download.js 一致)
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

// 顯示路徑建議 (與 download.js 一致)
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

// 顯示靜態建議
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

// 建立建議項目
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

// 更新選中的建議
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

// 選擇建議
function selectSuggestion(path) {
    const pathInput = document.getElementById('serverPathInput');
    pathInput.value = path;
    hideSuggestions();
    
    // 如果是資料夾，導航到該路徑
    goToPath();
}

// 隱藏建議
function hideSuggestions() {
    const suggestions = document.getElementById('pathSuggestions');
    if (suggestions) {
        suggestions.classList.remove('show');
    }
}

// 前往指定路徑
function goToPath() {
    const pathInput = document.getElementById('serverPathInput');
    const path = pathInput.value.trim();
    
    if (path) {
        currentServerPath = path;
        loadServerFiles(path);
    }
}

// 重新整理伺服器檔案
function refreshServerFiles() {
    loadServerFiles(currentServerPath);
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
    const validExtensions = ['.xlsx', '.xls', '.csv'];
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    
    if (!validExtensions.includes(fileExtension)) {
        utils.showNotification('請選擇 Excel (.xlsx, .xls) 或 CSV (.csv) 檔案', 'error');
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
    
    // 根據檔案類型決定圖標和顯示的類型文字
    let fileIcon = 'fa-file-excel';
    let fileType = 'Excel 檔案';
    
    if (file.name.endsWith('.csv')) {
        fileIcon = 'fa-file-csv';
        fileType = 'CSV 檔案';
    } else if (file.name.endsWith('.xls')) {
        fileType = 'Excel 97-2003';
    }
    
    fileList.innerHTML = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h3 class="file-list-title">
                    <i class="fas ${fileIcon}"></i> 已選擇的檔案
                </h3>
                <span class="file-count-badge">1 個檔案</span>
            </div>
            <div class="file-items">
                <div class="file-item-card">
                    <div class="file-icon-wrapper">
                        <i class="fas ${fileIcon}"></i>
                    </div>
                    <div class="file-details">
                        <div class="file-name">${file.name}</div>
                        <div class="file-meta">
                            <span>${fileType}</span>
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

// 載入伺服器檔案 (與 download.js 風格一致)
async function loadServerFiles(path) {
    const browser = document.getElementById('serverBrowser');
    if (!browser) return;
    
    browser.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><span> 載入中...</span></div>';
    
    try {
        const response = await utils.apiRequest(`/api/browse-server?path=${encodeURIComponent(path)}`);
        currentServerPath = path;
        displayServerFiles(response);
        
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

// 顯示伺服器檔案 (與 download.js 風格一致)
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
            <div class="file-item folder" onclick="navigateToFolder('${folder.path}')">
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
        const isSelected = selectedServerFiles.some(f => f.path === file.path);
        
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

// 導航到上層目錄
function navigateToParent() {
    const parentPath = currentServerPath.substring(0, currentServerPath.lastIndexOf('/')) || '/';
    loadServerFiles(parentPath);
}

// 導航到資料夾
function navigateToFolder(path) {
    loadServerFiles(path);
}

// 切換伺服器檔案選擇 - 修正為與 download.js 一致的多選邏輯
function toggleServerFile(path, name, size) {
    const index = selectedServerFiles.findIndex(f => f.path === path);
    
    if (index === -1) {
        // 如果檔案未選擇，添加到選擇列表
        selectedServerFiles.push({ path, name, size, type: 'server' });
    } else {
        // 如果檔案已選擇，從列表中移除
        selectedServerFiles.splice(index, 1);
    }
    
    // 更新顯示
    updateServerFileSelection();
    checkExecuteButton();
    
    // 重新載入檔案列表以更新選中狀態
    loadServerFiles(currentServerPath);
}

// 更新伺服器檔案選擇顯示 - 修正為支援多選
function updateServerFileSelection() {
    const container = document.getElementById('serverSelectedFiles');
    
    if (selectedServerFiles.length === 0) {
        container.classList.add('hidden');
        selectedFile = null;
        return;
    }
    
    container.classList.remove('hidden');
    
    // 使用第一個選擇的檔案作為主要檔案（保持向後相容）
    selectedFile = selectedServerFiles[0].path;
    
    // 使用與 download.js 相同的顯示格式
    let html = `
        <div class="file-list-container">
            <div class="file-list-header">
                <h3 class="file-list-title">
                    <i class="fas fa-check-circle"></i> 已選擇的檔案
                </h3>
                <span class="file-count-badge">${selectedServerFiles.length} 個檔案</span>
            </div>
            <div class="file-items">
    `;
    
    selectedServerFiles.forEach((file, index) => {
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

// 移除伺服器檔案 - 修正為支援索引參數
function removeServerFile(index) {
    selectedServerFiles.splice(index, 1);
    updateServerFileSelection();
    checkExecuteButton();
    
    // 重新載入檔案列表以更新選中狀態
    loadServerFiles(currentServerPath);
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

// 檢查執行按鈕狀態 - 修正為支援多選
function checkExecuteButton() {
    const executeBtn = document.getElementById('executeBtn');
    // 檢查是否有選擇本地檔案或伺服器檔案
    executeBtn.disabled = !selectedFile && selectedServerFiles.length === 0;
    
    // 更新步驟狀態
    if (selectedFile || selectedServerFiles.length > 0) {
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
    // 確保有選擇檔案
    if (!selectedFile && selectedServerFiles.length === 0) {
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
    const { progress, status, message, stats, files } = data;
    
    // 更新進度條
    document.getElementById('progressFill').style.width = `${progress}%`;
    document.getElementById('progressText').textContent = `${progress}%`;
    
    // 更新階段狀態和添加詳細日誌
    if (status === 'downloading') {
        updateStageStatus('download', 'active');
        addLog(message, 'downloading');
        
        // 如果有統計資料，顯示下載進度
        if (stats) {
            if (stats.downloaded > 0) {
                addLog(`已下載 ${stats.downloaded} 個檔案`, 'success');
            }
            if (stats.skipped > 0) {
                addLog(`已跳過 ${stats.skipped} 個檔案`, 'info');
            }
            if (stats.failed > 0) {
                addLog(`${stats.failed} 個檔案下載失敗`, 'error');
            }
        }
    } else if (status === 'downloaded') {
        updateStageStatus('download', 'completed');
        addLog('下載完成！', 'success');
        
        // 顯示最終統計
        if (stats) {
            addLog(`總計：${stats.total} 個檔案`, 'info');
            addLog(`成功下載：${stats.downloaded} 個`, 'success');
            if (stats.skipped > 0) {
                addLog(`跳過：${stats.skipped} 個`, 'info');
            }
            if (stats.failed > 0) {
                addLog(`失敗：${stats.failed} 個`, 'error');
            }
        }
    } else if (status === 'comparing') {
        updateStageStatus('download', 'completed');
        updateStageStatus('compare', 'active');
        addLog(message, 'info');
    } else if (status === 'compared') {
        updateStageStatus('compare', 'completed');
        addLog('比對完成！', 'success');
    } else if (status === 'packaging') {
        updateStageStatus('download', 'completed');
        updateStageStatus('compare', 'completed');
        updateStageStatus('package', 'active');
        addLog(message, 'info');
    } else if (status === 'completed') {
        updateStageStatus('package', 'completed');
        addLog('打包完成！', 'success');
        addLog('所有處理已完成！', 'completed');
    } else if (status === 'error') {
        addLog(message, 'error');
    } else {
        // 其他訊息
        addLog(message, 'info');
    }

    // 處理完成或錯誤
    if (status === 'completed') {
        handleComplete(data.results || data);
    } else if (status === 'error') {
        handleError(message);
    }
}

// 清除日誌
function clearLog() {
    const log = document.getElementById('downloadLog');
    if (log) {
        log.innerHTML = '';
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

// 處理完成
function handleComplete(results) {
    // 更新步驟狀態
    updateStepIndicator('process', 'completed');
    updateStepIndicator('complete', 'completed');
        
    // 顯示結果
    document.getElementById('progressContainer').classList.add('hidden');
    document.getElementById('resultContainer').classList.remove('hidden');
    
    // 生成結果摘要 - 確保調用正確
    const summaryHtml = generateResultSummary(results);
    const summaryElement = document.getElementById('resultSummary');
    if (summaryElement) {
        summaryElement.innerHTML = summaryHtml;
    }
    
    // 保存任務結果供後續使用
    if (currentTaskId && results) {
        window.lastTaskResults = {
            taskId: currentTaskId,
            results: results
        };
    }
    
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
    if (!results) {
        return '<div class="no-data">無結果資料</div>';
    }
    
    const stats = results.stats || {};
    const compareResults = results.compare_results || {};
    
    let html = '';
    
    // 下載統計部分
    if (stats && stats.total) {
        html += `
            <h3 style="margin-bottom: 20px; color: #1A237E; text-align: center;">
                <i class="fas fa-download"></i> 下載統計
            </h3>
            <div class="summary-grid" style="margin-bottom: 32px;">
                <div class="summary-item" style="background: #E3F2FD; border: 2px solid #2196F3;">
                    <i class="fas fa-file fa-3x" style="color: #2196F3;"></i>
                    <div class="summary-content">
                        <div class="summary-value">${stats.total || 0}</div>
                        <div class="summary-label">總檔案數</div>
                    </div>
                </div>
                
                <div class="summary-item" style="background: #E8F5E9; border: 2px solid #4CAF50;">
                    <i class="fas fa-check-circle fa-3x" style="color: #4CAF50;"></i>
                    <div class="summary-content">
                        <div class="summary-value">${stats.downloaded || 0}</div>
                        <div class="summary-label">已下載</div>
                    </div>
                </div>
                
                <div class="summary-item" style="background: #FFF3E0; border: 2px solid #FF9800;">
                    <i class="fas fa-forward fa-3x" style="color: #FF9800;"></i>
                    <div class="summary-content">
                        <div class="summary-value">${stats.skipped || 0}</div>
                        <div class="summary-label">已跳過</div>
                    </div>
                </div>
                
                <div class="summary-item" style="background: #FFEBEE; border: 2px solid #F44336;">
                    <i class="fas fa-times-circle fa-3x" style="color: #F44336;"></i>
                    <div class="summary-content">
                        <div class="summary-value">${stats.failed || 0}</div>
                        <div class="summary-label">失敗</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // 比對結果部分
    if (compareResults && Object.keys(compareResults).length > 0) {
        html += `
            <h3 style="margin: 32px 0 20px 0; color: #1A237E; text-align: center;">
                <i class="fas fa-code-compare"></i> 比對結果
            </h3>
            <div class="summary-grid">
        `;
        
        // Master vs PreMP
        if (compareResults.master_vs_premp) {
            const data = compareResults.master_vs_premp;
            html += `
                <div class="summary-item" style="background: #E8F4FD; border: 2px solid #64B5F6;">
                    <i class="fas fa-code-branch fa-3x" style="color: #1976D2;"></i>
                    <div class="summary-content">
                        <div class="summary-value">${data.success || 0}</div>
                        <div class="summary-label">Master vs PreMP</div>
                    </div>
                </div>
            `;
        }
        
        // PreMP vs Wave
        if (compareResults.premp_vs_wave) {
            const data = compareResults.premp_vs_wave;
            html += `
                <div class="summary-item" style="background: #E0F2F1; border: 2px solid #4DB6AC;">
                    <i class="fas fa-water fa-3x" style="color: #00897B;"></i>
                    <div class="summary-content">
                        <div class="summary-value">${data.success || 0}</div>
                        <div class="summary-label">PreMP vs Wave</div>
                    </div>
                </div>
            `;
        }
        
        // Wave vs Backup
        if (compareResults.wave_vs_backup) {
            const data = compareResults.wave_vs_backup;
            html += `
                <div class="summary-item" style="background: #F3E5F5; border: 2px solid #BA68C8;">
                    <i class="fas fa-database fa-3x" style="color: #7B1FA2;"></i>
                    <div class="summary-content">
                        <div class="summary-value">${data.success || 0}</div>
                        <div class="summary-label">Wave vs Backup</div>
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
    }
    
    // 其他結果資訊
    if (results.download_report || results.zip_file) {
        html += `
            <div style="margin-top: 32px; text-align: center; padding: 20px; background: #F5F9FF; border-radius: 12px;">
                <i class="fas fa-check-circle" style="color: #4CAF50; font-size: 2rem; margin-bottom: 12px;"></i>
                <h4 style="color: #1A237E; margin-bottom: 8px;">處理完成！</h4>
                <p style="color: #5C6BC0;">所有檔案已下載、比對並打包完成</p>
            </div>
        `;
    }
    
    return html;
}

// 查看結果
function viewResults() {
    if (currentTaskId) {
        window.location.href = `/results/${currentTaskId}`;
    } else if (window.lastTaskResults && window.lastTaskResults.taskId) {
        window.location.href = `/results/${window.lastTaskResults.taskId}`;
    } else {
        utils.showNotification('無可查看的結果', 'error');
    }
}

// 下載所有檔案
function downloadAll() {
    if (currentTaskId) {
        window.location.href = `/api/export-zip/${currentTaskId}`;
    } else if (window.lastTaskResults && window.lastTaskResults.taskId) {
        window.location.href = `/api/export-zip/${window.lastTaskResults.taskId}`;
    } else {
        utils.showNotification('無可下載的檔案', 'error');
    }
}
// 開始新的處理
function startNew() {
    // 重置所有變數
    currentTaskId = null;
    selectedFile = null;
    selectedServerFiles = [];
    serverFilesLoaded = false;
    
    // 清除檔案輸入
    const fileInput = document.getElementById('localFileInput');
    if (fileInput) {
        fileInput.value = '';
    }
    
    // 隱藏所有容器
    const resultContainer = document.getElementById('resultContainer');
    if (resultContainer) {
        resultContainer.classList.add('hidden');
    }
    
    const progressContainer = document.getElementById('progressContainer');
    if (progressContainer) {
        progressContainer.classList.add('hidden');
    }
    
    // 顯示主表單
    const mainForm = document.getElementById('mainForm');
    if (mainForm) {
        mainForm.classList.remove('hidden');
    }
    
    // 重置步驟指示器
    updateStepIndicator('upload', 'active');
    updateStepIndicator('config', 'pending');
    updateStepIndicator('process', 'pending');
    updateStepIndicator('complete', 'pending');
    
    // 重置階段狀態
    ['download', 'compare', 'package'].forEach(stage => {
        const stageElement = document.getElementById(`stage-${stage}`);
        if (stageElement) {
            stageElement.classList.remove('active', 'completed');
            const statusElement = stageElement.querySelector('.stage-status');
            if (statusElement) {
                statusElement.textContent = '等待中...';
            }
        }
    });
    
    // 清除日誌
    clearLog();
    
    // 重置進度條
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    if (progressFill) progressFill.style.width = '0%';
    if (progressText) progressText.textContent = '0%';
    
    // 隱藏檔案列表
    const localFileList = document.getElementById('localFileList');
    if (localFileList) {
        localFileList.classList.add('hidden');
        localFileList.innerHTML = '';
    }
    
    const serverSelectedFiles = document.getElementById('serverSelectedFiles');
    if (serverSelectedFiles) {
        serverSelectedFiles.classList.add('hidden');
        serverSelectedFiles.innerHTML = '';
    }
    
    // 重置執行按鈕
    const executeBtn = document.getElementById('executeBtn');
    if (executeBtn) {
        executeBtn.disabled = true;
    }
    
    // 重置標籤到本地上傳
    const localTab = document.querySelector('.tab-btn[onclick*="local"]');
    const serverTab = document.querySelector('.tab-btn[onclick*="server"]');
    if (localTab && serverTab) {
        localTab.classList.add('active');
        serverTab.classList.remove('active');
        
        const localContent = document.getElementById('local-tab');
        const serverContent = document.getElementById('server-tab');
        if (localContent) localContent.classList.add('active');
        if (serverContent) serverContent.classList.remove('active');
    }
    
    // 顯示成功訊息
    utils.showNotification('已重置，可以開始新的處理', 'success');
}

// 重置到表單
function resetToForm() {
    // 確保元素存在再設定
    const elements = {
        uploadArea: document.getElementById('uploadArea'),
        configForm: document.getElementById('configForm'),
        processingSteps: document.getElementById('processingSteps'),
        completedResults: document.getElementById('completedResults'),
        recentActivities: document.getElementById('recentActivities')
    };
    
    // 顯示上傳區域和配置表單
    if (elements.uploadArea) {
        elements.uploadArea.classList.remove('hidden');
    }
    if (elements.configForm) {
        elements.configForm.classList.remove('hidden');
    }
    
    // 隱藏處理步驟和結果
    if (elements.processingSteps) {
        elements.processingSteps.classList.add('hidden');
    }
    if (elements.completedResults) {
        elements.completedResults.classList.add('hidden');
    }
    
    // 重置最近活動
    if (elements.recentActivities) {
        elements.recentActivities.innerHTML = '<p class="text-muted">暫無活動記錄</p>';
    }
    
    // 重置變數
    currentTaskId = null;
    uploadedFile = null;
    currentStep = null;
    
    // 重置文件資訊
    const fileInfo = document.getElementById('fileInfo');
    if (fileInfo) {
        fileInfo.classList.add('hidden');
    }
    
    // 重置處理按鈕
    const processBtn = document.getElementById('processBtn');
    if (processBtn) {
        processBtn.disabled = true;
    }
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
window.navigateToParent = navigateToParent;
window.goToPath = goToPath;
window.refreshServerFiles = refreshServerFiles;
window.executeOneStep = executeOneStep;
window.viewResults = viewResults;
window.downloadAll = downloadAll;
window.startNew = startNew;
window.resetToForm = resetToForm;
window.hideSuggestions = hideSuggestions;
window.selectSuggestion = selectSuggestion;