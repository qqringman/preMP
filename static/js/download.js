// 下載頁面 JavaScript - 修正版（統一檔案顯示格式）

// 頁面變數
let selectedSource = 'local';
let selectedFiles = [];  // 當前選擇的檔案
let localSelectedFiles = []; // 本地選擇的檔案
let serverSelectedFiles = []; // 伺服器選擇的檔案  
let downloadTaskId = null;
let currentServerPath = '/home/vince_lin/ai/preMP'; // 使用 config.py 的預設路徑
let serverFilesLoaded = false;
let pathInputTimer = null;
let downloadedFilesList = [];
let skippedFilesList = [];
let failedFilesList = [];
let previewSource = null; // 記錄預覽是從哪裡開啟的

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
    window.showFilesList = showFilesList;
    window.closeFilesModal = closeFilesModal;
    window.previewFileFromList = previewFileFromList;
    window.copyPreviewContent = copyPreviewContent;
    window.fallbackCopyToClipboard = fallbackCopyToClipboard;    

    // 初始化功能
    initializeTabs();
    initializeUploadAreas();
    initializeConfigToggles();
    initializePathInput();
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

function showFilesList(type) {
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
            // 合併所有檔案
            files = [
                ...downloadedFilesList.map(f => ({...f, status: 'downloaded'})),
                ...skippedFilesList.map(f => ({...f, status: 'skipped'})),
                ...failedFilesList.map(f => ({...f, status: 'failed'}))
            ];
            title = '所有檔案';
            modalClass = 'info';
            break;
    }
    
    // 顯示模態框
    const modal = document.getElementById('filesListModal');
    const modalTitle = document.getElementById('filesModalTitle');
    const modalBody = document.getElementById('filesModalBody');
    
    if (!modal || !modalTitle || !modalBody) {
        console.error('Files list modal elements not found');
        return;
    }
    
    modalTitle.innerHTML = `<i class="fas fa-list"></i> ${title}`;
    modal.className = `modal ${modalClass}`;
    
    // 生成檔案列表 HTML
    if (files.length === 0) {
        modalBody.innerHTML = '<div class="empty-message">沒有檔案</div>';
    } else {
        let html = '<div class="files-table-container"><table class="files-table">';
        html += '<thead><tr>';
        html += '<th style="width: 50px">#</th>';
        html += '<th>檔案名稱</th>';
        html += '<th>FTP 路徑</th>';
        html += '<th>本地路徑</th>';
        
        if (type === 'total') {
            html += '<th style="width: 100px">狀態</th>';
        }
        
        if (type === 'skipped' || type === 'failed') {
            html += '<th>原因</th>';
        }
        
        html += '<th style="width: 80px">操作</th>';
        html += '</tr></thead><tbody>';
        
        files.forEach((file, index) => {
            html += '<tr>';
            html += `<td class="index-cell">${index + 1}</td>`;
            html += `<td class="file-name-cell">
                        <i class="fas fa-file-alt"></i> ${file.name}
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
            
            // 操作按鈕
            html += '<td class="action-cell">';
            if ((type === 'downloaded' || (type === 'total' && file.status === 'downloaded')) && file.path) {
                // 確保路徑格式正確
                const cleanPath = file.path.replace(/\\/g, '/');
                html += `<button class="btn-icon" onclick="previewFileFromList('${cleanPath}')" title="預覽">
                            <i class="fas fa-eye"></i>
                         </button>`;
            }
            html += '</td>';
            
            html += '</tr>';
        });
        
        html += '</tbody></table></div>';
        
        // 添加統計摘要
        if (files.length > 0) {
            html += `<div class="files-summary">
                        <i class="fas fa-chart-bar"></i>
                        共 ${files.length} 個檔案
                     </div>`;
        }
        
        modalBody.innerHTML = html;
    }
    
    modal.classList.remove('hidden');
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

// 定義備用的複製方法
function fallbackCopyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-999999px';
    document.body.appendChild(textarea);
    
    try {
        textarea.select();
        const successful = document.execCommand('copy');
        if (successful) {
            utils.showNotification('內容已複製到剪貼簿', 'success');
        } else {
            utils.showNotification('複製失敗', 'error');
        }
    } catch (err) {
        console.error('複製失敗:', err);
        utils.showNotification('複製失敗', 'error');
    } finally {
        document.body.removeChild(textarea);
    }
}

// 先定義 closeFilesModal 函數
function closeFilesModal() {
    const modal = document.getElementById('filesListModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

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
        // 確保伺服器瀏覽器顯示載入中而非空訊息
        const browser = document.getElementById('serverBrowser');
        if (browser) {
            browser.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><span> 載入中...</span></div>';
        }
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

// 更新下載進度
function updateDownloadProgress(data) {
    const { progress, status, message, stats, files, results } = data;
    
    // 更新進度條
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    if (progressFill && progressText) {
        progressFill.style.width = `${progress}%`;
        progressText.textContent = `${Math.round(progress)}%`;
    }
    
    // 更新統計 - 確保統計資料存在
    if (stats && typeof stats === 'object') {
        console.log('Updating stats:', stats); // 除錯用
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
    
    // 處理完成或錯誤
    if (status === 'completed') {
        // 確保 results 包含最新的檔案列表
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

function debugStats() {
    console.log('Current stats:', {
        total: document.getElementById('totalFiles').textContent,
        downloaded: document.getElementById('downloadedFiles').textContent,
        skipped: document.getElementById('skippedFiles').textContent,
        failed: document.getElementById('failedFiles').textContent
    });
}

// 更新統計數據
function updateStats(stats) {
    if (!stats) return;
    
    const elements = {
        totalFiles: stats.total || 0,
        downloadedFiles: stats.downloaded || 0,
        skippedFiles: stats.skipped || 0,
        failedFiles: stats.failed || 0
    };
    
    for (const [id, value] of Object.entries(elements)) {
        const element = document.getElementById(id);
        if (element) {
            // 直接更新數值，不要動畫效果避免亂跳
            element.textContent = value;
            
            // 讓統計卡片可點擊
            const card = element.closest('.stat-card');
            if (card && value > 0) {
                card.style.cursor = 'pointer';
                card.onclick = () => showFilesList(id.replace('Files', ''));
                card.title = '點擊查看檔案列表';
            }
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
    
    // 確保檔案列表資料被保存
    if (results.files) {
        downloadedFilesList = results.files.downloaded || [];
        skippedFilesList = results.files.skipped || [];
        failedFilesList = results.files.failed || [];
    }
    
    // 生成摘要 - 使用北歐藍配色並添加點擊功能
    const stats = results.stats || {};
    const summary = `
        <div class="summary-grid">
            <div class="summary-item clickable" onclick="showFilesList('downloaded')" title="點擊查看已下載檔案">
                <i class="fas fa-check-circle text-success"></i>
                <div class="summary-content">
                    <div class="summary-value">${stats.downloaded || 0}</div>
                    <div class="summary-label">成功下載</div>
                </div>
            </div>
            <div class="summary-item clickable" onclick="showFilesList('skipped')" title="點擊查看跳過的檔案">
                <i class="fas fa-forward text-info"></i>
                <div class="summary-content">
                    <div class="summary-value">${stats.skipped || 0}</div>
                    <div class="summary-label">跳過檔案</div>
                </div>
            </div>
            ${stats.failed > 0 ? `
                <div class="summary-item clickable" onclick="showFilesList('failed')" title="點擊查看失敗的檔案">
                    <i class="fas fa-times-circle text-danger"></i>
                    <div class="summary-content">
                        <div class="summary-value">${stats.failed}</div>
                        <div class="summary-label">下載失敗</div>
                    </div>
                </div>
            ` : ''}
            <div class="summary-item clickable" onclick="showFilesList('total')" title="點擊查看所有檔案">
                <i class="fas fa-folder-tree text-info"></i>
                <div class="summary-content">
                    <div class="summary-value">${stats.total || 0}</div>
                    <div class="summary-label">總檔案數</div>
                </div>
            </div>
        </div>
        
        <!-- 添加提示文字 -->
        <div class="summary-hint">
            <i class="fas fa-info-circle"></i>
            <span>提示：點擊上方統計數字可查看詳細的檔案列表</span>
        </div>
    `;
    
    document.getElementById('resultSummary').innerHTML = summary;
    
    // 生成資料夾樹
    if (results.folder_structure) {
        generateFolderTree(results.folder_structure);
    }
}

// 生成資料夾樹 - 改善顏色配色
function generateFolderTree(structure) {
    const treeContainer = document.getElementById('folderTree');
    
    if (!structure || Object.keys(structure).length === 0) {
        treeContainer.innerHTML = '<div class="empty-message">沒有檔案</div>';
        return;
    }
    
    const tree = buildTreeHTML(structure, '', '');
    treeContainer.innerHTML = tree;
}

// 建立樹狀結構 HTML - 改善顏色
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
    if (!previewSource) {
        previewSource = null;
    }
    
    const modal = document.getElementById('filePreviewModal');
    const content = document.getElementById('previewContent');
    const filename = document.getElementById('previewFilename');
    
    // 顯示檔名和檔案類型
    const fileName = path.split('/').pop();
    const fileExt = fileName.split('.').pop().toLowerCase();
    
    if (filename) {
        filename.textContent = fileName;
        filename.className = `preview-filename ${fileExt}`;
    }
    
    content.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><span>載入中...</span></div>';
    modal.classList.remove('hidden');
    
    try {
        const response = await utils.apiRequest(`/api/preview-file?path=${encodeURIComponent(path)}`);
        
        // 根據檔案類型處理內容
        if (response.type === 'xml') {
            // 改進的 XML 語法高亮
            let formattedContent = response.content
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                // 處理 XML 標籤
                .replace(/(&lt;\/?)([a-zA-Z0-9\-:]+)(.*?)(&gt;)/g, 
                    '<span class="xml-bracket">$1</span><span class="xml-tag">$2</span>$3<span class="xml-bracket">$4</span>')
                // 處理屬性
                .replace(/(\s)([a-zA-Z0-9\-:]+)(=)(".*?")/g, 
                    '$1<span class="xml-attr">$2</span><span class="xml-bracket">$3</span><span class="xml-value">$4</span>')
                // 處理註釋
                .replace(/(&lt;!--.*?--&gt;)/g, 
                    '<span class="xml-comment">$1</span>');
            
            content.innerHTML = formattedContent;
            content.className = 'preview-content xml';
        } else {
            content.textContent = response.content;
            content.className = 'preview-content';
        }
    } catch (error) {
        content.innerHTML = `<div class="error"><i class="fas fa-exclamation-circle"></i> 無法預覽檔案：${error.message}</div>`;
        content.className = 'preview-content';
    }
}

// 複製預覽內容
function copyPreviewContent() {
    const content = document.getElementById('previewContent');
    if (!content) {
        utils.showNotification('找不到預覽內容', 'error');
        return;
    }
    
    const text = content.textContent || content.innerText;
    
    // 檢查瀏覽器是否支援 clipboard API
    if (navigator.clipboard && window.isSecureContext) {
        // 使用新的 Clipboard API
        navigator.clipboard.writeText(text).then(() => {
            utils.showNotification('內容已複製到剪貼簿', 'success');
        }).catch(err => {
            console.error('複製失敗:', err);
            fallbackCopyToClipboard(text);
        });
    } else {
        // 使用傳統方法
        fallbackCopyToClipboard(text);
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