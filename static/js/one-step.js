// 一步到位頁面 JavaScript - 更新伺服器瀏覽功能

let selectedFile = null;
let currentTaskId = null;
let selectedServerFiles = [];
let currentServerPath = '/home/vince_lin/ai/preMP';
let serverFilesLoaded = false;
let pathInputTimer = null;

// 加入這三行（新增的全域變數）
let downloadedFilesList = [];
let skippedFilesList = [];
let failedFilesList = [];

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
    
    // 決定使用哪個檔案（本地或伺服器）
    let excelFile = selectedFile;
    if (!excelFile && selectedServerFiles.length > 0) {
        excelFile = selectedServerFiles[0].path;
    }
    
    console.log('Using Excel file:', excelFile);
    
    // 隱藏表單，顯示進度
    document.getElementById('mainForm').classList.add('hidden');
    document.getElementById('progressContainer').classList.remove('hidden');
    
    // 發送請求
    try {
        const response = await utils.apiRequest('/api/one-step', {
            method: 'POST',
            body: JSON.stringify({
                excel_file: excelFile,
                sftp_config: sftpConfig
            })
        });
        
        console.log('One-step API response:', response);
        
        currentTaskId = response.task_id;
        
        // 加入任務房間
        if (window.socket && socket.connected) {
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
    console.log('=== updateProgress called ===');
    console.log('Input data:', data);
    
    const { progress, status, message, stats, files, results } = data;
    
    // 更新進度條
    document.getElementById('progressFill').style.width = `${progress}%`;
    document.getElementById('progressText').textContent = `${progress}%`;
    
    // 保存檔案列表資料 - 檢查多個可能的位置
    let filesUpdated = false;
    
    if (files) {
        downloadedFilesList = files.downloaded || [];
        skippedFilesList = files.skipped || [];
        failedFilesList = files.failed || [];
        filesUpdated = true;
        console.log('Files updated from data.files');
    } else if (results && results.files) {
        downloadedFilesList = results.files.downloaded || [];
        skippedFilesList = results.files.skipped || [];
        failedFilesList = results.files.failed || [];
        filesUpdated = true;
        console.log('Files updated from data.results.files');
    } else if (results && results.download_results && results.download_results.files) {
        downloadedFilesList = results.download_results.files.downloaded || [];
        skippedFilesList = results.download_results.files.skipped || [];
        failedFilesList = results.download_results.files.failed || [];
        filesUpdated = true;
        console.log('Files updated from data.results.download_results.files');
    }
    
    if (filesUpdated) {
        console.log('Files updated in updateProgress:', {
            downloaded: downloadedFilesList.length,
            skipped: skippedFilesList.length,
            failed: failedFilesList.length
        });
    } else {
        console.log('No files data found in updateProgress');
    }
    
    // 更新階段狀態和添加詳細日誌
    if (status === 'downloading') {
        updateStageStatus('download', 'active');
        addLog(message, 'downloading');
        
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
        
        // 完成時再次嘗試保存檔案列表
        if (!filesUpdated) {
            console.log('Attempting to save files on completion...');
            if (results && results.files) {
                downloadedFilesList = results.files.downloaded || [];
                skippedFilesList = results.files.skipped || [];
                failedFilesList = results.files.failed || [];
                console.log('Files saved from results on completion');
            }
        }
    } else if (status === 'error') {
        addLog(message, 'error');
    } else {
        addLog(message, 'info');
    }

    // 處理完成或錯誤
    if (status === 'completed') {
        console.log('Calling handleComplete with:', results || data);
        handleComplete(results || data);
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
    console.log('=== handleComplete called ===');
    console.log('Results received:', results);
    
    // 保存檔案列表 - 檢查多個可能的位置
    let filesUpdated = false;
    
    if (results) {
        // 優先從 results.files 取得
        if (results.files) {
            downloadedFilesList = results.files.downloaded || [];
            skippedFilesList = results.files.skipped || [];
            failedFilesList = results.files.failed || [];
            filesUpdated = true;
        }
        // 如果沒有 files，嘗試從 download_results 取得
        else if (results.download_results && results.download_results.files) {
            downloadedFilesList = results.download_results.files.downloaded || [];
            skippedFilesList = results.download_results.files.skipped || [];
            failedFilesList = results.download_results.files.failed || [];
            filesUpdated = true;
        }
        
        console.log('Files updated in handleComplete:', {
            downloaded: downloadedFilesList.length,
            skipped: skippedFilesList.length,
            failed: failedFilesList.length,
            filesUpdated
        });
    }
    
    // 更新步驟狀態
    updateStepIndicator('process', 'completed');
    updateStepIndicator('complete', 'completed');
    
    // 顯示結果
    document.getElementById('progressContainer').classList.add('hidden');
    document.getElementById('resultContainer').classList.remove('hidden');
    
    // 強制生成結果摘要，即使沒有完整資料
    const summaryHtml = generateResultSummary(results, true); // 加入 forceDisplay 參數
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
function generateResultSummary(results, forceDisplay = false) {
    console.log('generateResultSummary - results:', results, 'forceDisplay:', forceDisplay);
    
    // 確保檔案列表有被保存
    if (results && results.files) {
        downloadedFilesList = results.files.downloaded || [];
        skippedFilesList = results.files.skipped || [];
        failedFilesList = results.files.failed || [];
    } else if (results && results.download_results && results.download_results.files) {
        downloadedFilesList = results.download_results.files.downloaded || [];
        skippedFilesList = results.download_results.files.skipped || [];
        failedFilesList = results.download_results.files.failed || [];
    }
    
    // 獲取統計資料
    const stats = results?.stats || results?.download_results?.stats || {};
    const compareResults = results?.compare_results || {};
    
    let html = `
        <div class="results-summary-container">
            <div class="results-summary-header">
                <h3 class="results-summary-title">
                    <i class="fas fa-chart-pie"></i> 處理結果摘要
                </h3>
                <p class="results-summary-subtitle">
                    一步到位處理完成 • ${new Date().toLocaleString('zh-TW')}
                </p>
            </div>
            
            <div class="results-summary-content">
    `;
    
    // 檢查是否有真實資料
    const hasStats = Object.keys(stats).length > 0;
    const hasCompareResults = Object.keys(compareResults).length > 0;
    const hasFileData = downloadedFilesList.length > 0 || skippedFilesList.length > 0 || failedFilesList.length > 0;
    
    if (hasStats || hasCompareResults || hasFileData || forceDisplay) {
        // 如果沒有統計資料但有檔案資料，生成基本統計
        let displayStats = stats;
        if (!hasStats && hasFileData) {
            displayStats = {
                total: downloadedFilesList.length + skippedFilesList.length + failedFilesList.length,
                downloaded: downloadedFilesList.length,
                skipped: skippedFilesList.length,
                failed: failedFilesList.length
            };
        }
        
        // 如果強制顯示但完全沒有資料，顯示完成狀態
        if (forceDisplay && !hasStats && !hasCompareResults && !hasFileData) {
            html += `
                <div class="stats-section">
                    <h4 class="stats-section-title">
                        <i class="fas fa-check-circle"></i>
                        處理完成
                    </h4>
                    
                    <div class="completion-status" style="text-align: center; padding: 40px;">
                        <div style="font-size: 4rem; color: #4CAF50; margin-bottom: 20px;">
                            <i class="fas fa-check-circle"></i>
                        </div>
                        <h3 style="color: #4CAF50; margin-bottom: 10px;">一步到位處理成功完成！</h3>
                        <p style="color: #666; margin-bottom: 30px;">所有流程已執行完畢</p>
                        
                        <div style="display: flex; justify-content: center; gap: 16px; margin-top: 30px; flex-wrap: wrap;">
                            <button class="btn btn-primary" onclick="viewResults()" style="min-width: 160px;">
                                <i class="fas fa-chart-line"></i> 查看詳細結果
                            </button>
                            <button class="btn btn-success" onclick="downloadAll()" style="min-width: 160px;">
                                <i class="fas fa-download"></i> 下載所有檔案
                            </button>
                            <button class="btn btn-secondary" onclick="startNew()" style="min-width: 160px;">
                                <i class="fas fa-redo"></i> 開始新的處理
                            </button>
                        </div>
                    </div>
                </div>
            `;
        } else {
            // 使用真實資料或生成的基本統計
            html += generateStatsSection(displayStats);
            html += generateCompareResultsSection(compareResults);
            
            // 操作按鈕區域
            html += `
                <div class="action-buttons" style="margin-top: 32px; text-align: center;">
                    <div style="display: flex; justify-content: center; gap: 16px; flex-wrap: wrap;">
                        <button class="btn btn-primary" onclick="viewResults()" style="min-width: 160px;">
                            <i class="fas fa-chart-line"></i> 查看詳細結果
                        </button>
                        <button class="btn btn-success" onclick="downloadAll()" style="min-width: 160px;">
                            <i class="fas fa-download"></i> 下載所有檔案
                        </button>
                        <button class="btn btn-secondary" onclick="startNew()" style="min-width: 160px;">
                            <i class="fas fa-redo"></i> 開始新的處理
                        </button>
                    </div>
                </div>
            `;
            
            // 提示區域
            html += `
                <div class="results-hint" style="margin-top: 24px;">
                    <i class="fas fa-lightbulb"></i>
                    <p class="results-hint-text">
                        💡 點擊統計卡片查看詳細檔案列表 • 點擊比對結果查看差異報告
                    </p>
                </div>
            `;
        }
    } else {
        // 沒有資料時顯示空狀態
        html += `
            <div class="no-results">
                <i class="fas fa-clock"></i>
                <h5>處理進行中</h5>
                <p>結果統計將在處理完成後顯示</p>
            </div>
        `;
    }
    
    html += `
            </div>
        </div>
    `;
    
    return html;
}

// 生成比對結果區域
function generateCompareResultsSection(compareResults) {
    let html = `
        <div class="stats-section" style="margin-top: 32px;">
            <h4 class="stats-section-title">
                <i class="fas fa-code-compare"></i>
                版本比對結果
            </h4>
    `;
    
    if (!compareResults || Object.keys(compareResults).length === 0) {
        html += `
            <div class="no-results">
                <i class="fas fa-search"></i>
                <h5>尚未執行比對</h5>
                <p>比對結果將在處理完成後顯示</p>
            </div>
        `;
    } else {
        html += '<div class="compare-results-grid">';
        
        // Master vs PreMP
        if (compareResults.master_vs_premp) {
            const data = compareResults.master_vs_premp;
            html += generateCompareCard(
                'Master vs PreMP',
                'fa-code-branch',
                data.success || 0,
                data.failed || 0,
                'master_vs_premp'
            );
        }
        
        // PreMP vs Wave
        if (compareResults.premp_vs_wave) {
            const data = compareResults.premp_vs_wave;
            html += generateCompareCard(
                'PreMP vs Wave',
                'fa-wave-square',
                data.success || 0,
                data.failed || 0,
                'premp_vs_wave'
            );
        }
        
        // Wave vs Backup
        if (compareResults.wave_vs_backup) {
            const data = compareResults.wave_vs_backup;
            html += generateCompareCard(
                'Wave vs Backup',
                'fa-database',
                data.success || 0,
                data.failed || 0,
                'wave_vs_backup'
            );
        }
        
        html += '</div>';
        
        // 總結資訊
        const totalSuccess = Object.values(compareResults).reduce((sum, result) => sum + (result.success || 0), 0);
        const totalFailed = Object.values(compareResults).reduce((sum, result) => sum + (result.failed || 0), 0);
        const totalModules = totalSuccess + totalFailed;
        const compareSuccessRate = totalModules > 0 ? Math.round((totalSuccess / totalModules) * 100) : 0;
        
        html += `
            <div class="compare-summary" style="margin-top: 24px; padding: 20px; background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%); border-radius: 12px; border: 1px solid #2196F3;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 20px; text-align: center;">
                    <div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #1976D2;">${totalModules}</div>
                        <div style="font-size: 0.875rem; color: #1565C0;">總模組數</div>
                    </div>
                    <div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #4CAF50;">${totalSuccess}</div>
                        <div style="font-size: 0.875rem; color: #2E7D32;">比對成功</div>
                    </div>
                    <div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #F44336;">${totalFailed}</div>
                        <div style="font-size: 0.875rem; color: #C62828;">比對失敗</div>
                    </div>
                    <div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #FF9800;">${compareSuccessRate}%</div>
                        <div style="font-size: 0.875rem; color: #F57C00;">比對成功率</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

// 生成比對卡片
function generateCompareCard(title, icon, successCount, failedCount, scenario) {
    const total = successCount + failedCount;
    const successRate = total > 0 ? Math.round((successCount / total) * 100) : 0;
    
    return `
        <div class="compare-result-card" onclick="viewScenarioResults('${scenario}')" style="cursor: pointer;" title="點擊查看 ${title} 詳細結果">
            <div class="compare-result-header">
                <div class="compare-result-icon">
                    <i class="fas ${icon}"></i>
                </div>
                <h5 class="compare-result-title">${title}</h5>
            </div>
            
            <div class="compare-result-stats">
                <div class="compare-stat">
                    <div class="compare-stat-value" style="color: #4CAF50;">${successCount}</div>
                    <div class="compare-stat-label">成功</div>
                </div>
                <div class="compare-stat">
                    <div class="compare-stat-value" style="color: #F44336;">${failedCount}</div>
                    <div class="compare-stat-label">失敗</div>
                </div>
                <div class="compare-stat">
                    <div class="compare-stat-value" style="color: #2196F3;">${successRate}%</div>
                    <div class="compare-stat-label">成功率</div>
                </div>
            </div>
            
            <!-- 進度條 -->
            <div style="margin-top: 16px; height: 6px; background: #EEEEEE; border-radius: 3px; overflow: hidden;">
                <div style="width: ${successRate}%; height: 100%; background: linear-gradient(90deg, #4CAF50 0%, #66BB6A 100%); transition: width 0.5s ease;"></div>
            </div>
        </div>
    `;
}

// 生成統計區域
function generateStatsSection(stats) {
    const total = stats.total || 0;
    const downloaded = stats.downloaded || 0;
    const skipped = stats.skipped || 0;
    const failed = stats.failed || 0;
    
    // 如果沒有統計資料，顯示空狀態
    if (total === 0) {
        return `
            <div class="stats-section">
                <h4 class="stats-section-title">
                    <i class="fas fa-download"></i>
                    檔案下載統計
                </h4>
                
                <div class="no-results">
                    <i class="fas fa-inbox"></i>
                    <h5>尚無下載統計</h5>
                    <p>統計資料將在下載完成後顯示</p>
                </div>
            </div>
        `;
    }
    
    // 計算成功率
    const successRate = total > 0 ? Math.round((downloaded / total) * 100) : 0;
    
    let html = `
        <div class="stats-section">
            <h4 class="stats-section-title">
                <i class="fas fa-download"></i>
                檔案下載統計
            </h4>
            
            <div class="stat-cards">
                <div class="stat-card clickable" onclick="showFilesList('total')" title="點擊查看所有檔案">
                    <div class="stat-icon info">
                        <i class="fas fa-files"></i>
                    </div>
                    <div class="stat-content">
                        <div class="stat-value">${total}</div>
                        <div class="stat-label">總檔案數</div>
                    </div>
                </div>
                
                <div class="stat-card clickable" onclick="showFilesList('downloaded')" title="點擊查看已下載檔案">
                    <div class="stat-icon success">
                        <i class="fas fa-check-circle"></i>
                    </div>
                    <div class="stat-content">
                        <div class="stat-value">${downloaded}</div>
                        <div class="stat-label">成功下載</div>
                    </div>
                </div>
                
                <div class="stat-card clickable" onclick="showFilesList('skipped')" title="點擊查看跳過的檔案">
                    <div class="stat-icon warning">
                        <i class="fas fa-forward"></i>
                    </div>
                    <div class="stat-content">
                        <div class="stat-value">${skipped}</div>
                        <div class="stat-label">跳過檔案</div>
                    </div>
                </div>
                
                <div class="stat-card clickable" onclick="showFilesList('failed')" title="點擊查看失敗的檔案">
                    <div class="stat-icon danger">
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                    <div class="stat-content">
                        <div class="stat-value">${failed}</div>
                        <div class="stat-label">下載失敗</div>
                    </div>
                </div>
            </div>
            
            <!-- 成功率指示器 -->
            <div class="success-rate-indicator" style="margin-top: 20px; padding: 16px; background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%); border-radius: 12px; border: 1px solid #4CAF50;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <i class="fas fa-chart-line" style="color: #4CAF50; font-size: 1.25rem;"></i>
                    <span style="color: #2E7D32; font-weight: 600;">成功率: ${successRate}%</span>
                    <div style="flex: 1; background: rgba(76, 175, 80, 0.2); height: 8px; border-radius: 4px; margin-left: 12px;">
                        <div style="width: ${successRate}%; height: 100%; background: linear-gradient(90deg, #4CAF50 0%, #66BB6A 100%); border-radius: 4px; transition: width 0.5s ease;"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
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
        
        console.log('Poll status response:', status);
        
        if (status.status !== 'not_found') {
            // 確保檔案資料有傳遞
            if (status.files) {
                downloadedFilesList = status.files.downloaded || [];
                skippedFilesList = status.files.skipped || [];
                failedFilesList = status.files.failed || [];
            }
            
            // 如果有 results，也要處理
            if (status.results) {
                if (status.results.files) {
                    downloadedFilesList = status.results.files.downloaded || [];
                    skippedFilesList = status.results.files.skipped || [];
                    failedFilesList = status.results.files.failed || [];
                }
                if (status.results.download_results && status.results.download_results.files) {
                    downloadedFilesList = status.results.download_results.files.downloaded || [];
                    skippedFilesList = status.results.download_results.files.skipped || [];
                    failedFilesList = status.results.download_results.files.failed || [];
                }
            }
            
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

function showFilesList(type) {
    console.log('showFilesList called:', type, {
        downloaded: downloadedFilesList.length,
        skipped: skippedFilesList.length,
        failed: failedFilesList.length
    });
    
    let files = [];
    let title = '';
    let modalClass = '';
    
    switch(type) {
        case 'downloaded':
            files = downloadedFilesList;
            title = '已下載的檔案';
            modalClass = 'success';
            break;
        case 'skipped':
            files = skippedFilesList;
            title = '已跳過的檔案';
            modalClass = 'info';
            break;
        case 'failed':
            files = failedFilesList;
            title = '下載失敗的檔案';
            modalClass = 'danger';
            break;
        case 'total':
            files = [
                ...downloadedFilesList.map(f => ({...f, status: 'downloaded'})),
                ...skippedFilesList.map(f => ({...f, status: 'skipped'})),
                ...failedFilesList.map(f => ({...f, status: 'failed'}))
            ];
            title = '所有檔案';
            break;
    }
    
    const modal = document.getElementById('filesListModal');
    const modalTitle = document.getElementById('filesModalTitle');
    const modalBody = document.getElementById('filesModalBody');
    
    if (!modal || !modalTitle || !modalBody) {
        console.error('Files list modal elements not found');
        return;
    }
    
    modalTitle.innerHTML = `<i class="fas fa-list"></i> ${title}`;
    modal.className = `modal ${modalClass}`;
    
    // 生成檔案列表 HTML - 使用與 download.js 完全相同的結構
    if (files.length === 0) {
        modalBody.innerHTML = '<div class="empty-message"><i class="fas fa-inbox fa-3x"></i><p>沒有檔案</p></div>';
    } else {
        let html = '<div class="table-wrapper">';
        html += '<table class="files-table">';
        html += '<thead><tr>';
        html += '<th style="width: 60px">#</th>';
        html += '<th style="min-width: 200px">檔案名稱</th>';
        html += '<th style="min-width: 300px">FTP 路徑</th>';
        html += '<th style="min-width: 300px">本地路徑</th>';
        
        if (type === 'total') {
            html += '<th style="width: 100px">狀態</th>';
        }
        
        if (type === 'skipped' || type === 'failed') {
            html += '<th style="min-width: 200px">原因</th>';
        }
        
        html += '<th style="width: 80px">操作</th>';
        html += '</tr></thead>';
        html += '<tbody>';
        
        files.forEach((file, index) => {
            html += '<tr>';
            html += `<td class="index-cell">${index + 1}</td>`;
            html += `<td class="file-name-cell">
                        <i class="fas fa-file-alt"></i> ${file.name || '未知'}
                     </td>`;
            html += `<td class="file-path-cell" title="${file.ftp_path || '-'}">${file.ftp_path || '-'}</td>`;
            html += `<td class="file-path-cell" title="${file.path || '-'}">${file.path || '-'}</td>`;
            
            if (type === 'total') {
                const statusClass = file.status === 'downloaded' ? 'success' : 
                                  file.status === 'skipped' ? 'info' : 'danger';
                const statusText = file.status === 'downloaded' ? '已下載' : 
                                 file.status === 'skipped' ? '已跳過' : '失敗';
                html += `<td><span class="status-badge ${statusClass}">${statusText}</span></td>`;
            }
            
            if (type === 'skipped' || type === 'failed') {
                html += `<td>${file.reason || '-'}</td>`;
            }
            
            html += '<td class="action-cell">-</td>';
            html += '</tr>';
        });
        
        html += '</tbody>';
        html += '</table>';
        html += '</div>';
        
        // 統計摘要
        html += `
            <div class="table-footer">
                <i class="fas fa-chart-bar"></i>
                共 ${files.length} 個檔案
            </div>
        `;
        
        modalBody.innerHTML = html;
    }
    
    modal.classList.remove('hidden');
}

function closeFilesModal() {
    const modal = document.getElementById('filesListModal');
    if (modal) {
        modal.classList.add('hidden');
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
window.showFilesList = showFilesList;
window.closeFilesModal = closeFilesModal;