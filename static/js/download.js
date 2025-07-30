// 下載頁面 JavaScript

let downloadFile = null;
let downloadTaskId = null;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initializeDownloadUpload();
    initializeDownloadConfig();
});

// 初始化上傳功能
function initializeDownloadUpload() {
    const uploadArea = document.getElementById('downloadUploadArea');
    const fileInput = document.getElementById('downloadFileInput');
    const selectBtn = document.getElementById('selectFileBtn');
    
    // 點擊選擇按鈕
    selectBtn.addEventListener('click', () => {
        fileInput.click();
    });
    
    // 點擊上傳區域
    uploadArea.addEventListener('click', (e) => {
        // 如果點擊的不是按鈕，則觸發檔案選擇
        if (!e.target.classList.contains('btn') && !e.target.closest('.btn')) {
            fileInput.click();
        }
    });
    
    // 拖放事件
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.add('dragging');
    });
    
    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.remove('dragging');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        uploadArea.classList.remove('dragging');
        
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleDownloadFileSelect(files[0]);
        }
    });
    
    // 檔案選擇
    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleDownloadFileSelect(e.target.files[0]);
        }
    });
}

// 處理檔案選擇
async function handleDownloadFileSelect(file) {
    if (!file.name.endsWith('.xlsx')) {
        utils.showNotification('請選擇 Excel (.xlsx) 檔案', 'error');
        return;
    }
    
    document.getElementById('downloadUploadArea').classList.add('hidden');
    document.getElementById('downloadFileInfo').classList.remove('hidden');
    document.getElementById('downloadFileName').textContent = 
        `${file.name} (${utils.formatFileSize(file.size)})`;
    
    try {
        const result = await utils.uploadFile(file);
        downloadFile = result.filepath;
        checkDownloadButton();
    } catch (error) {
        console.error('Upload error:', error);
        removeDownloadFile();
    }
}

// 移除檔案
function removeDownloadFile() {
    downloadFile = null;
    document.getElementById('downloadFileInfo').classList.add('hidden');
    document.getElementById('downloadUploadArea').classList.remove('hidden');
    document.getElementById('downloadFileInput').value = '';
    checkDownloadButton();
}

// 初始化 SFTP 設定
function initializeDownloadConfig() {
    const useDefault = document.getElementById('downloadUseDefault');
    const customConfig = document.getElementById('downloadCustomConfig');
    
    useDefault.addEventListener('change', (e) => {
        if (e.target.checked) {
            customConfig.classList.add('disabled');
            // 停用所有輸入欄位
            customConfig.querySelectorAll('input').forEach(input => {
                input.disabled = true;
            });
        } else {
            customConfig.classList.remove('disabled');
            // 啟用所有輸入欄位
            customConfig.querySelectorAll('input').forEach(input => {
                input.disabled = false;
            });
        }
    });
    
    // 初始化時停用自訂設定
    if (useDefault.checked) {
        customConfig.querySelectorAll('input').forEach(input => {
            input.disabled = true;
        });
    }
}

// 檢查下載按鈕
function checkDownloadButton() {
    const downloadBtn = document.getElementById('downloadBtn');
    downloadBtn.disabled = !downloadFile;
}

// 測試連線
async function testConnection() {
    const config = getDownloadConfig();
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

// 取得下載設定
function getDownloadConfig() {
    const config = {};
    
    if (!document.getElementById('downloadUseDefault').checked) {
        config.host = document.getElementById('downloadHost').value;
        config.port = parseInt(document.getElementById('downloadPort').value) || 22;
        config.username = document.getElementById('downloadUsername').value;
        config.password = document.getElementById('downloadPassword').value;
        
        // 驗證必要欄位
        if (!config.host || !config.username || !config.password) {
            throw new Error('請填寫完整的 SFTP 設定');
        }
    }
    
    return config;
}

// 執行下載
async function executeDownload() {
    if (!downloadFile) {
        utils.showNotification('請先上傳 Excel 檔案', 'error');
        return;
    }
    
    try {
        const sftpConfig = getDownloadConfig();
        
        // 隱藏表單，顯示進度
        document.querySelector('.download-form').classList.add('hidden');
        document.getElementById('downloadProgress').classList.remove('hidden');
        
        const response = await utils.apiRequest('/api/download', {
            method: 'POST',
            body: JSON.stringify({
                excel_file: downloadFile,
                sftp_config: sftpConfig,
                options: {
                    skip_existing: document.getElementById('skipExisting').checked,
                    recursive_search: document.getElementById('recursiveSearch').checked,
                    search_depth: parseInt(document.getElementById('searchDepth').value)
                }
            })
        });
        
        downloadTaskId = response.task_id;
        
        // 加入任務房間以接收即時更新
        if (socket) {
            socket.emit('join_task', { task_id: downloadTaskId });
        }
        
        // 監聽進度更新
        document.addEventListener('task-progress', handleDownloadProgress);
        
        // 開始輪詢狀態（備用方案）
        pollDownloadStatus();
        
    } catch (error) {
        console.error('Download error:', error);
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
    
    document.getElementById('downloadProgressFill').style.width = `${progress}%`;
    document.getElementById('downloadProgressText').textContent = `${Math.round(progress)}%`;
    
    // 更新統計
    if (stats) {
        document.getElementById('totalFiles').textContent = stats.total || '0';
        document.getElementById('downloadedFiles').textContent = stats.downloaded || '0';
        document.getElementById('skippedFiles').textContent = stats.skipped || '0';
        document.getElementById('failedFiles').textContent = stats.failed || '0';
    }
    
    // 添加日誌
    addDownloadLog(message);
    
    // 處理完成或錯誤
    if (status === 'completed') {
        showDownloadResults(data.results);
    } else if (status === 'error') {
        utils.showNotification(`下載失敗：${message}`, 'error');
        resetDownloadForm();
    }
}

// 添加下載日誌
function addDownloadLog(message) {
    const log = document.getElementById('downloadLog');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <span class="log-time">${new Date().toLocaleTimeString('zh-TW')}</span>
        <span class="log-message">${message}</span>
    `;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

// 顯示下載結果
function showDownloadResults(results) {
    document.getElementById('downloadProgress').classList.add('hidden');
    document.getElementById('downloadResults').classList.remove('hidden');
    
    // 生成摘要
    const stats = results.stats || {};
    const summary = `
        <div class="summary-grid">
            <div class="summary-item success">
                <i class="fas fa-check"></i>
                <span>成功下載 ${stats.downloaded || 0} 個檔案</span>
            </div>
            <div class="summary-item info">
                <i class="fas fa-forward"></i>
                <span>跳過 ${stats.skipped || 0} 個已存在檔案</span>
            </div>
            ${stats.failed > 0 ? `
                <div class="summary-item error">
                    <i class="fas fa-times"></i>
                    <span>${stats.failed} 個檔案下載失敗</span>
                </div>
            ` : ''}
        </div>
    `;
    document.getElementById('downloadSummary').innerHTML = summary;
    
    // 生成資料夾樹
    if (results.folder_structure) {
        generateFolderTree(results.folder_structure);
    }
}

// 生成資料夾樹狀結構
function generateFolderTree(structure) {
    const tree = buildTreeHTML(structure, 'downloads');
    document.getElementById('folderTree').innerHTML = tree;
}

// 建立樹狀結構 HTML
function buildTreeHTML(node, name) {
    if (typeof node === 'string') {
        return `<div class="tree-node"><i class="fas fa-file"></i> ${name}</div>`;
    }
    
    let html = `
        <div class="tree-node">
            <i class="fas fa-folder-open"></i> ${name}/
            <div class="tree-children">
    `;
    
    for (const [key, value] of Object.entries(node)) {
        html += buildTreeHTML(value, key);
    }
    
    html += '</div></div>';
    return html;
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
        }
    } catch (error) {
        console.error('Poll status error:', error);
    }
}

// 重置下載表單
function resetDownloadForm() {
    document.querySelector('.download-form').classList.remove('hidden');
    document.getElementById('downloadProgress').classList.add('hidden');
    document.getElementById('downloadResults').classList.add('hidden');
    
    // 清空日誌
    document.getElementById('downloadLog').innerHTML = '';
    
    // 重置進度
    document.getElementById('downloadProgressFill').style.width = '0%';
    document.getElementById('downloadProgressText').textContent = '0%';
}

// 查看下載報表
function viewDownloadReport() {
    if (downloadTaskId) {
        window.location.href = `/api/download-report/${downloadTaskId}`;
    }
}

// 繼續比對
function proceedToCompare() {
    window.location.href = '/compare';
}

// 開始新的下載
function startNewDownload() {
    location.reload();
}

// 匯出函數
window.removeDownloadFile = removeDownloadFile;
window.testConnection = testConnection;
window.executeDownload = executeDownload;
window.viewDownloadReport = viewDownloadReport;
window.proceedToCompare = proceedToCompare;
window.startNewDownload = startNewDownload;